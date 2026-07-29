from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
import uuid

from .adapters import GitAdapter, GitHubAdapter, HerdrAdapter
from .agent_runner import HerdrAgentRunner, issue_payload
from .clarification import authorized_answer, comment_body, marker
from .config import ControllerConfig, reject_legacy_sandbox_layers
from .gitleaks import GitleaksDocker
from .models import ControllerState, IssueState, Phase
from .plan_schema import deterministic_plan, validate_plan
from .policy import (
    LowRiskInput,
    build_pr_body,
    check_paths,
    inspect_changes,
    low_risk_reasons,
)
from .process_runner import ProcessRunner
from .reconciliation import reconcile
from .result_parser import review_result, worker_result
from .state import StateStore
from .validation import (
    branch,
    commit_message,
    issue_number,
    sha,
    worktree_path,
    worktree_root,
)


class Controller:
    def __init__(
        self,
        repository: Path,
        config: ControllerConfig,
        runner: ProcessRunner | None = None,
    ):
        self.repo = repository.resolve(strict=True)
        self.config = config
        self.runner = runner or ProcessRunner()
        self.state_root = (
            self.repo.parent / ".herdr-issue-controller" / self.repo.name
        )
        self.store = StateStore(self.state_root)
        self.git = GitAdapter(
            self.runner,
            self.repo,
            remote=self.config.remote,
        )
        self.gh = GitHubAdapter(self.runner)
        self.herdr = HerdrAdapter(self.runner)
        image_lock = Path(self.config.image_lock)
        if not image_lock.is_absolute():
            image_lock = self.repo / image_lock
        self.gitleaks = GitleaksDocker(
            self.config.docker,
            image_lock,
            self.state_root,
            self.runner,
            timeout=self.config.gitleaks_timeout,
        )
        self.agents = HerdrAgentRunner(
            self.herdr,
            self.state_root / "logs",
        )

    def doctor(self) -> list[str]:
        failures: list[str] = []
        if os.environ.get("HERDR_ENV") != "1":
            failures.append("HERDR_ENV=1 is required")
        for argv, name in (
            (["git", "--version"], "git"),
            (["gh", "--version"], "gh"),
            (["herdr", "--help"], "herdr"),
            ([self.config.docker, "--version"], "docker"),
            (["codex", "--help"], "codex"),
        ):
            if self.runner.run(argv).returncode:
                failures.append(f"missing required {name}")
        try:
            self.git.verify_repository()
        except RuntimeError:
            failures.append("invalid repository")
        if os.environ.get("HERDR_ENV") == "1":
            try:
                if any(result.returncode for result in self.herdr.help_commands()):
                    failures.append("required Herdr subcommand is unavailable")
                self.herdr.current_pane()
                self.herdr.panes()
                self.herdr.agents()
            except RuntimeError:
                failures.append("cannot inspect current Herdr layout")
        try:
            worktree_root(self.repo)
        except (OSError, ValueError):
            failures.append("unsafe worktree root")
        try:
            self.gh.repo()
        except RuntimeError:
            failures.append("GitHub repository is unavailable")
        try:
            self.gitleaks.verify_image_is_local()
        except RuntimeError as exc:
            failures.append(str(exc))
        try:
            reject_legacy_sandbox_layers(self.repo)
        except RuntimeError as exc:
            failures.append(str(exc))
        return list(dict.fromkeys(failures))

    def plan(
        self,
        numbers: list[int],
        raw_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidates = {issue_number(number) for number in numbers}
        if not candidates:
            raise ValueError("at least one Issue is required")
        plan = (
            validate_plan(raw_plan, candidates, self.config.max_parallel)
            if raw_plan is not None
            else deterministic_plan(
                sorted(candidates),
                self.config.max_parallel,
            )
        )
        digest = hashlib.sha256(
            json.dumps(
                sorted(candidates),
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        with self.store.lock():
            state = self.store.load()
            state.run_id = state.run_id or self._new_run_id()
            state.plan = plan
            state.planner_input_digest = digest
            state.planner_fallback = raw_plan is None
            self.store.save(state)
        return plan

    def status(self, number: int | None = None) -> dict[str, Any]:
        with self.store.lock():
            state = self.store.load()
            if state.issues:
                reconcile(state, self.git)
                # This is deliberately detection only.  A merge performed in
                # the GitHub UI is surfaced as cleanup pending, never cleaned
                # up as a side effect of a read-only status command.
                for item in state.issues.values():
                    self._reconcile_pr(item)
                self.store.save(state)
            if number is None:
                return state.to_dict()
            item = state.issues.get(str(issue_number(number)))
            return item.to_dict() if item else {}

    def start(
        self,
        numbers: list[int],
        *,
        no_publish: bool,
    ) -> dict[str, Any]:
        requested = [issue_number(number) for number in numbers]
        if not requested:
            raise ValueError("at least one Issue is required")
        if len(set(requested)) != len(requested):
            raise ValueError("duplicate Issue selection")
        failures = self.doctor()
        if failures:
            raise RuntimeError("doctor failed: " + "; ".join(failures))
        with self.store.lock():
            state = self.store.load()
            if any(
                item.phase
                not in {Phase.DONE, Phase.CLEANED, Phase.BLOCKED, Phase.FAILED}
                for item in state.issues.values()
            ):
                raise RuntimeError("an unfinished run already exists; use resume")
            state = ControllerState(run_id=self._new_run_id())
            issues = [self.gh.issue(number) for number in requested]
            self._plan_with_planner(state, issues)
            clarifications = {
                int(value["issue"]): value
                for value in state.plan["clarifications"]
            }
            base_sha: str | None = None
            for issue in issues:
                item = self._prepare_issue(
                    issue,
                    base_sha,
                    publish_requested=not no_publish,
                )
                state.issues[str(item.issue_number)] = item
                self.store.save(state)
                clarification = clarifications.get(item.issue_number)
                if clarification is not None:
                    self._request_clarification(state, item, clarification)
                    self.store.save(state)
                    continue
                if base_sha is None:
                    base_sha = self.git.fetch_base(self.config.base_branch)
                    item.base_sha = base_sha
                else:
                    item.base_sha = base_sha
                self.git.add_worktree(
                    Path(item.worktree),
                    item.branch,
                    base_sha,
                )
            self._run_batches(state, issues)
            self.store.save(state)
            return state.to_dict()

    def validate(self, number: int) -> dict[str, Any]:
        with self.store.lock():
            state = self.store.load()
            item = self._item(state, number)
            issue = self.gh.issue(item.issue_number)
            self._validate_and_commit(state, item, issue)
            self.store.save(state)
            return item.to_dict()

    def publish(self, number: int) -> dict[str, Any]:
        with self.store.lock():
            state = self.store.load()
            item = self._item(state, number)
            self._publish(state, item)
            self.store.save(state)
            return item.to_dict()

    def resume(self, number: int | None = None) -> dict[str, Any]:
        with self.store.lock():
            state = self.store.load()
            reconcile(state, self.git)
            items = (
                [self._item(state, number)]
                if number is not None
                else list(state.issues.values())
            )
            for item in items:
                if item.phase is Phase.AWAITING_INPUT:
                    self._resume_clarification(state, item)
                elif item.phase is Phase.COMMITTED and item.publish_requested:
                    self._publish(state, item)
                elif item.phase in {Phase.RUNNING, Phase.VALIDATING}:
                    issue = self.gh.issue(item.issue_number)
                    self._continue_worker(state, item, issue)
                elif item.phase in {
                    Phase.PUBLISHED,
                    Phase.MERGE_EVALUATION,
                    Phase.AWAITING_MERGE_APPROVAL,
                }:
                    self._evaluate_merge(state, item)
                if item.phase is Phase.DONE and item.cleanup_status != "cleaned":
                    self._cleanup_after_merge(state, item, merge_confirmed=False)
                self.store.save(state)
            return state.to_dict()

    def cleanup(self, number: int) -> dict[str, Any]:
        with self.store.lock():
            state = self.store.load()
            item = self._item(state, number)
            if item.phase not in {
                Phase.COMMITTED,
                Phase.PUBLISHED,
                Phase.DONE,
                Phase.BLOCKED,
                Phase.CLEANED,
            }:
                raise RuntimeError("Issue is not eligible for cleanup")
            # DONE is already a successful delivery. Its cleanup helper turns
            # a GitHub verification outage into a warning rather than making
            # the CLI fail. Legacy explicit cleanup remains available when a
            # published/blocked PR cannot be queried.
            if item.phase in {Phase.DONE, Phase.CLEANED}:
                merged = False
            else:
                try:
                    merged = self._merge_is_confirmed(item)
                except RuntimeError:
                    merged = False
            if merged and item.phase is not Phase.DONE and item.phase is not Phase.CLEANED:
                item.phase = Phase.DONE
                item.ended_at = item.ended_at or self._now()
            if item.phase in {Phase.DONE, Phase.CLEANED} or merged:
                self._cleanup_after_merge(state, item, merge_confirmed=merged)
            else:
                if item.phase is Phase.COMMITTED and not item.pr_url:
                    raise RuntimeError("unpublished commit must be preserved")
                self._manual_cleanup_unmerged(item)
            self.store.save(state)
            return item.to_dict()

    def merge(
        self,
        number: int,
        head_sha: str,
    ) -> dict[str, Any]:
        expected_sha = sha(head_sha)
        with self.store.lock():
            state = self.store.load()
            item = self._item(state, number)
            if not item.pr_url:
                raise RuntimeError("PR is not available")
            pr = self.gh.pr(item.pr_url)
            if (
                pr.get("headRefOid") != expected_sha
                or item.commit_sha != expected_sha
                or pr.get("headRefName") != item.branch
                or pr.get("baseRefName") != self.config.base_branch
            ):
                item.phase = Phase.BLOCKED
                item.last_error = "blocked:head-changed"
                self.store.save(state)
                raise RuntimeError("PR head or branch does not match state")
            blockers = self._pr_blockers(pr)
            if blockers:
                item.phase = Phase.AWAITING_MERGE_APPROVAL
                item.last_error = "; ".join(blockers)
                self.store.save(state)
                raise RuntimeError("PR is not merge-ready")
            self.gh.merge(item.pr_url, expected_sha)
            item.phase = Phase.DONE
            item.ended_at = self._now()
            item.last_error = None
            self._cleanup_after_merge(state, item, merge_confirmed=True)
            self.store.save(state)
            return item.to_dict()

    def pr_body(self, number: int, draft: dict[str, Any]) -> str:
        state = self.store.load()
        item = self._item(state, number)
        if not item.commit_sha:
            raise RuntimeError("commit required")
        return build_pr_body(
            item.issue_number,
            item.commit_sha,
            item.changed_paths,
            item.tests,
            draft,
            state.run_id,
        )

    def merge_gate(
        self,
        number: int,
        evidence: LowRiskInput,
    ) -> list[str]:
        with self.store.lock():
            state = self.store.load()
            item = self._item(state, number)
            reasons = low_risk_reasons(evidence, self.config)
            item.phase = (
                Phase.MERGE_EVALUATION
                if not reasons
                else Phase.AWAITING_MERGE_APPROVAL
            )
            item.last_error = "; ".join(reasons) if reasons else None
            self.store.save(state)
        return reasons

    def _run_batches(
        self,
        state: ControllerState,
        issues: list[dict[str, Any]],
    ) -> None:
        issue_by_number = {
            int(issue["number"]): issue
            for issue in issues
        }
        assert state.plan is not None
        for batch in state.plan["batches"]:
            launched: list[tuple[IssueState, dict[str, Any], float]] = []
            for number in batch["issues"]:
                item = state.issues[str(number)]
                if item.phase is not Phase.PREPARING:
                    continue
                issue = issue_by_number[number]
                started = self._launch_worker(item, issue)
                launched.append((item, issue, started))
                self.store.save(state)
            for item, issue, started in launched:
                try:
                    self._collect_worker(state, item, issue, started)
                except (RuntimeError, ValueError) as exc:
                    item.phase = Phase.BLOCKED
                    item.last_error = f"blocked:worker:{type(exc).__name__}"
                    item.ended_at = self._now()
                self.store.save(state)

    def _prepare_issue(
        self,
        issue: dict[str, Any],
        base_sha: str | None,
        *,
        publish_requested: bool,
    ) -> IssueState:
        number = issue_number(issue["number"])
        title = str(issue.get("title", ""))
        branch_name = branch(
            number,
            title,
            base=self.config.base_branch,
            template=self.config.branch_template,
            runner=self.runner,
        )
        path = worktree_path(self.repo, number)
        return IssueState(
            issue_number=number,
            issue_url=str(issue.get("url", "")),
            title=title,
            branch=branch_name,
            worktree=str(path),
            agent_name=f"issue-{number}-worker",
            phase=Phase.PREPARING,
            base_sha=base_sha,
            log_path=str(
                self.state_root / "logs" / f"issue-{number}-worker.log"
            ),
            publish_requested=publish_requested,
        )

    def _launch_worker(
        self,
        item: IssueState,
        issue: dict[str, Any],
        answer: dict[str, str] | None = None,
    ) -> float:
        payload = dict(issue)
        if answer is not None:
            payload["controller_clarification_answer"] = answer
        prompt = self._prompt("worker.md").replace(
            "{{ISSUE_JSON}}",
            issue_payload(payload),
        )
        pane_id, started_at = self.agents.start(
            cwd=Path(item.worktree),
            name=item.agent_name,
            model=self.config.worker_model,
            reasoning_effort=self.config.worker_reasoning,
            permission_profile="workspace",
            prompt=prompt,
        )
        item.pane_id = pane_id
        self._record_pane(item, pane_id)
        item.phase = Phase.RUNNING
        item.started_at = started_at
        return time.monotonic()

    def _collect_worker(
        self,
        state: ControllerState,
        item: IssueState,
        issue: dict[str, Any],
        started: float,
    ) -> None:
        run = self.agents.collect(
            name=item.agent_name,
            timeout_seconds=self.config.worker_timeout,
            started_monotonic=started,
            log_name=f"issue-{item.issue_number}-worker.log",
        )
        result = worker_result(run.result)
        item.worker_result = result
        item.ended_at = run.ended_at
        if result["status"] == "needs_clarification":
            self._request_clarification(state, item, result["clarification"])
            return
        if result["status"] != "done" or result["remaining_work"]:
            item.phase = Phase.BLOCKED
            item.last_error = "blocked:worker-result"
            return
        self._validate_and_commit(state, item, issue)
        if item.phase is Phase.COMMITTED and item.publish_requested:
            self._publish(state, item)

    def _continue_worker(
        self,
        state: ControllerState,
        item: IssueState,
        issue: dict[str, Any],
        answer: dict[str, str] | None = None,
    ) -> None:
        item.attempt += 1
        item.agent_name = f"issue-{item.issue_number}-worker-{item.attempt}"
        started = self._launch_worker(item, issue, answer)
        self.store.save(state)
        self._collect_worker(state, item, issue, started)

    def _validate_and_commit(
        self,
        state: ControllerState,
        item: IssueState,
        issue: dict[str, Any],
    ) -> None:
        worktree = self._owned_worktree(item)
        if self.git.current_branch(worktree) != item.branch:
            raise RuntimeError("worktree branch mismatch")
        changes = self.git.changes(worktree)
        if not changes:
            raise RuntimeError("worker produced no changes")
        actual_paths = sorted({change.path for change in changes})
        reported_paths = sorted(
            set((item.worker_result or {}).get("changed_files", []))
        )
        if reported_paths and reported_paths != actual_paths:
            raise RuntimeError("worker changed-file report mismatch")
        reasons = inspect_changes(worktree, changes, self.config)
        if reasons:
            raise RuntimeError("; ".join(reasons))
        conflicts = [
            other.issue_number
            for other in state.issues.values()
            if other.issue_number != item.issue_number
            and other.phase
            in {
                Phase.VALIDATING,
                Phase.REVIEWING,
                Phase.COMMITTED,
                Phase.PUBLISHED,
                Phase.DONE,
            }
            and set(actual_paths).intersection(other.changed_paths)
        ]
        if conflicts:
            raise RuntimeError("blocked:path-conflict")
        item.phase = Phase.VALIDATING
        item.changed_paths = actual_paths
        diff = self.git.diff_for_scan(worktree)
        self._record_gitleaks_artifact(state, item)
        scan = self.gitleaks.scan(
            diff,
            state.run_id,
            item.issue_number,
            item.attempt,
            self._gitleaks_config(),
        )
        if not scan.clean:
            raise RuntimeError("blocked:secret-finding")
        item.tests = []
        for command in self.config.verify_commands:
            result = self.runner.run(
                list(command.argv),
                cwd=worktree,
                timeout=command.timeout_seconds,
            )
            test = {
                "name": command.name,
                "result": "passed" if result.returncode == 0 else "failed",
                "summary": f"exit {result.returncode}",
            }
            item.tests.append(test)
            self.agents._save_log(
                self.state_root
                / "logs"
                / f"issue-{item.issue_number}-test-{command.name}.log",
                result.stdout + result.stderr,
            )
            if result.returncode:
                raise RuntimeError("blocked:test-failed")
        self._review(state, item, issue)
        if (item.reviewer_result or {}).get("verdict") != "OK":
            raise RuntimeError("blocked:review")
        item.phase = Phase.READY_TO_COMMIT
        self.git.stage(worktree)
        staged = self.git.staged_diff_for_scan(worktree)
        self._record_gitleaks_artifact(state, item)
        staged_scan = self.gitleaks.scan(
            staged,
            state.run_id,
            item.issue_number,
            item.attempt,
            self._gitleaks_config(),
        )
        if not staged_scan.clean:
            raise RuntimeError("blocked:secret-finding")
        message = commit_message(
            self.config.commit_template,
            item.issue_number,
            item.title,
        )
        item.commit_sha = self.git.commit(worktree, message)
        item.phase = Phase.COMMITTED
        item.last_error = None

    def _review(
        self,
        state: ControllerState,
        item: IssueState,
        issue: dict[str, Any],
    ) -> None:
        item.phase = Phase.REVIEWING
        name = f"issue-{item.issue_number}-review-{item.attempt}"
        prompt = self._prompt("reviewer.md").replace(
            "{{ISSUE_JSON}}",
            issue_payload(issue),
        )
        started = time.monotonic()
        pane, _started_at = self.agents.start(
            cwd=Path(item.worktree),
            name=name,
            model=self.config.reviewer_model,
            reasoning_effort=self.config.reviewer_reasoning,
            permission_profile="read-only",
            prompt=prompt,
        )
        self._record_pane(item, pane)
        self.store.save(state)
        run = self.agents.collect(
            name=name,
            timeout_seconds=self.config.reviewer_timeout,
            started_monotonic=started,
            log_name=f"issue-{item.issue_number}-review-{item.attempt}.log",
        )
        item.reviewer_result = review_result(run.result)

    def _publish(
        self,
        state: ControllerState,
        item: IssueState,
    ) -> None:
        if item.phase is not Phase.COMMITTED or not item.commit_sha:
            raise RuntimeError("only a committed Issue can be published")
        worktree = self._owned_worktree(item)
        if not self.git.is_clean(worktree):
            raise RuntimeError("worktree is not clean")
        if (
            self.git.head(worktree) != item.commit_sha
            or self.git.current_branch(worktree) != item.branch
        ):
            raise RuntimeError("commit or branch changed after validation")
        current_base = self.git.fetch_base(self.config.base_branch)
        if current_base != item.base_sha:
            item.phase = Phase.BLOCKED
            item.last_error = "blocked:base-updated"
            return
        existing = self.gh.existing_pr(item.branch)
        if existing is not None:
            if (
                existing.get("headRefName") != item.branch
                or existing.get("headRefOid") != item.commit_sha
                or existing.get("state") != "OPEN"
            ):
                raise RuntimeError("existing PR does not match expected branch")
            item.pr_url = str(existing["url"])
            item.phase = Phase.PUBLISHED
            self._evaluate_merge(state, item)
            return
        self.git.push(item.branch, self.config.base_branch)
        draft = (item.worker_result or {}).get("pr_draft", {})
        body = build_pr_body(
            item.issue_number,
            item.commit_sha,
            item.changed_paths,
            item.tests,
            draft,
            state.run_id,
        )
        item.pr_url = self.gh.create_pr(
            item.branch,
            self.config.base_branch,
            item.title,
            body,
        )
        item.phase = Phase.PUBLISHED
        item.last_error = None
        self._evaluate_merge(state, item)

    def _request_clarification(
        self,
        state: ControllerState,
        item: IssueState,
        clarification: dict[str, Any],
    ) -> None:
        marker_value = item.clarification_marker or marker(
            state.run_id,
            item.issue_number,
        )
        item.clarification_marker = marker_value
        body = comment_body(
            marker_value,
            clarification["question"],
            clarification["why_blocking"],
            clarification["options"],
        )
        if item.clarification_comment_url is None:
            self.gh.comment_issue(item.issue_number, body)
            item.clarification_comment_url = item.issue_url
        item.phase = Phase.AWAITING_INPUT
        item.last_error = "awaiting_input"

    def _resume_clarification(
        self,
        state: ControllerState,
        item: IssueState,
    ) -> None:
        if not item.clarification_marker:
            raise RuntimeError("clarification marker is missing")
        issue = self.gh.issue(item.issue_number)
        answer = authorized_answer(
            issue.get("comments"),
            item.clarification_marker,
            self.config.allowed_author_associations,
        )
        if answer is None:
            return
        item.clarification_answer = answer
        item.clarification_marker = None
        item.clarification_comment_url = None
        item.last_error = None
        issues = [self.gh.issue(existing.issue_number) for existing in state.issues.values()]
        self._plan_with_planner(state, issues)
        clarifications = {
            int(value["issue"]): value
            for value in state.plan["clarifications"]
        }
        for candidate in issues:
            pending = state.issues[str(candidate["number"])]
            clarification = clarifications.get(pending.issue_number)
            if clarification is not None:
                self._request_clarification(state, pending, clarification)
                continue
            if pending.phase is not Phase.AWAITING_INPUT:
                continue
            if pending.base_sha is None:
                pending.base_sha = self.git.fetch_base(self.config.base_branch)
            self.git.add_worktree(
                Path(pending.worktree),
                pending.branch,
                pending.base_sha,
            )
            pending.phase = Phase.PREPARING
        self._run_batches(state, issues)

    def _plan_with_planner(
        self,
        state: ControllerState,
        issues: list[dict[str, Any]],
    ) -> None:
        candidates = {issue_number(issue["number"]) for issue in issues}
        payload: list[dict[str, Any]] = []
        for issue in issues:
            value = dict(issue)
            existing = state.issues.get(str(issue_number(issue["number"])))
            if existing and existing.clarification_answer:
                value["controller_clarification_answer"] = existing.clarification_answer
            payload.append(value)
        state.planner_input_digest = hashlib.sha256(
            json.dumps(
                [json.loads(issue_payload(value)) for value in payload],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        state.planner_fallback = False
        state.planner_error = None
        self.store.save(state)
        name = f"issue-plan-{state.run_id}"
        prompt = self._prompt("planner.md").replace(
            "{{ISSUES_JSON}}",
            json.dumps(
                [json.loads(issue_payload(value)) for value in payload],
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        pane_id: str | None = None
        try:
            pane_id, started_at = self.agents.start(
                cwd=self.repo,
                name=name,
                model=self.config.planner_model,
                reasoning_effort=self.config.planner_reasoning,
                permission_profile="read-only",
                prompt=prompt,
            )
            run = self.agents.collect(
                name=name,
                timeout_seconds=self.config.planner_timeout,
                started_monotonic=time.monotonic(),
                log_name=f"{name}.log",
            )
        except RuntimeError as exc:
            if "timeout" in str(exc).lower() and self.config.planner_fallback == "deterministic":
                state.plan = deterministic_plan(sorted(candidates), self.config.max_parallel)
                state.planner_fallback = True
                self.store.save(state)
                return
            state.planner_error = (
                "failed:planner-timeout"
                if "timeout" in str(exc).lower()
                else "blocked:planner-failed"
            )
            self.store.save(state)
            raise RuntimeError(state.planner_error) from exc
        finally:
            if pane_id:
                self.herdr.close_pane(pane_id)
        try:
            state.plan = validate_plan(run.result, candidates, self.config.max_parallel)
        except (TypeError, ValueError) as exc:
            state.planner_error = "blocked:invalid-plan"
            self.store.save(state)
            raise RuntimeError(state.planner_error) from exc
        self.store.save(state)

    def _reconcile_pr(self, item: IssueState) -> None:
        if not item.pr_url:
            return
        pr = self.gh.pr(item.pr_url)
        if pr.get("state") == "MERGED":
            item.phase = Phase.DONE
            item.ended_at = self._now()
            item.last_error = None
        elif pr.get("headRefOid") != item.commit_sha:
            item.phase = Phase.BLOCKED
            item.last_error = "blocked:head-changed"

    def _evaluate_merge(
        self,
        state: ControllerState,
        item: IssueState,
    ) -> None:
        if not item.pr_url or not item.commit_sha or not item.base_sha:
            raise RuntimeError("published state is incomplete")
        pr = self.gh.pr(item.pr_url)
        if pr.get("state") == "MERGED":
            item.phase = Phase.DONE
            item.ended_at = self._now()
            item.last_error = None
            self._cleanup_after_merge(state, item, merge_confirmed=False)
            return
        if (
            pr.get("headRefOid") != item.commit_sha
            or pr.get("headRefName") != item.branch
        ):
            item.phase = Phase.BLOCKED
            item.last_error = "blocked:head-changed"
            return
        labels = {
            label.get("name")
            for label in (pr.get("labels") or [])
            if isinstance(label, dict)
        }
        human_elevated = bool(labels & {"risk:medium", "risk:high"})
        previous_risk = item.risk
        risk_result = self._risk_review(state, item)
        item.risk = risk_result["risk"]
        item.risk_head_sha = risk_result["head_sha"]
        changes = self.git.committed_changes(item.base_sha, item.commit_sha)
        paths = tuple(sorted({change.path for change in changes}))
        changed_lines, binary = self.git.committed_numstat(
            item.base_sha,
            item.commit_sha,
        )
        symlink, submodule = self.git.unsafe_tree_paths(
            item.commit_sha,
            list(paths),
        )
        ci_blockers = self._pr_blockers(pr)
        evidence = LowRiskInput(
            paths=paths,
            changed_files=len(paths),
            changed_lines=changed_lines,
            risk=risk_result["risk"],
            reviewer_ok=risk_result["verdict"] == "OK",
            current_head=risk_result["head_sha"] == item.commit_sha,
            ci_ok=not ci_blockers,
            human_elevated=human_elevated,
            has_delete=any(change.deleted for change in changes),
            has_rename=any(change.renamed for change in changes),
            has_binary=binary,
            has_symlink=symlink,
            has_submodule=submodule,
            unresolved=bool(
                (item.reviewer_result or {}).get("findings")
                or (item.worker_result or {}).get("remaining_work")
            ),
        )
        reasons = low_risk_reasons(evidence, self.config)
        if not human_elevated:
            new_label = f"risk:{risk_result['risk']}"
            previous = f"risk:{previous_risk}" if previous_risk else None
            remove = (
                (previous,)
                if previous
                and previous != new_label
                and previous in {"risk:low", "risk:medium", "risk:high"}
                else ()
            )
            self.gh.set_risk_label(item.pr_url, new_label, remove)
        if reasons:
            item.phase = Phase.AWAITING_MERGE_APPROVAL
            item.last_error = "; ".join(ci_blockers + reasons)
            return
        item.phase = Phase.MERGE_EVALUATION
        try:
            self.gh.merge(item.pr_url, item.commit_sha)
        except RuntimeError:
            item.phase = Phase.AWAITING_MERGE_APPROVAL
            item.last_error = "automatic merge was not accepted"
            return
        item.phase = Phase.DONE
        item.ended_at = self._now()
        item.last_error = None
        self._cleanup_after_merge(state, item, merge_confirmed=True)

    def _risk_review(
        self,
        state: ControllerState,
        item: IssueState,
    ) -> dict[str, Any]:
        assert item.commit_sha is not None
        issue = self.gh.issue(item.issue_number)
        suffix = str(int(time.time() * 1000))[-10:]
        name = f"issue-{item.issue_number}-risk-{suffix}"
        prompt = (
            self._prompt("risk-reviewer.md")
            .replace("{{ISSUE_JSON}}", issue_payload(issue))
            .replace("{{HEAD_SHA}}", item.commit_sha)
        )
        started = time.monotonic()
        pane, _started_at = self.agents.start(
            cwd=Path(item.worktree),
            name=name,
            model=self.config.reviewer_model,
            reasoning_effort=self.config.reviewer_reasoning,
            permission_profile="read-only",
            prompt=prompt,
        )
        self._record_pane(item, pane)
        # Persist before waiting so a crashed risk reviewer remains an owned
        # resource that a later recovery can safely inspect and close.
        self.store.save(state)
        run = self.agents.collect(
            name=name,
            timeout_seconds=self.config.reviewer_timeout,
            started_monotonic=started,
            log_name=f"issue-{item.issue_number}-risk-{suffix}.log",
        )
        return review_result(run.result, require_risk=True)

    def _pr_blockers(self, pr: dict[str, Any]) -> list[str]:
        blockers: list[str] = []
        if pr.get("isDraft"):
            blockers.append("PR is draft")
        if pr.get("mergeable") != "MERGEABLE":
            blockers.append("PR is not mergeable")
        checks = pr.get("statusCheckRollup") or []
        if not checks:
            blockers.append("required CI result is absent")
        for check in checks:
            if not isinstance(check, dict):
                blockers.append("invalid CI result")
                continue
            if "conclusion" in check:
                if check.get("conclusion") not in {
                    "SUCCESS",
                    "NEUTRAL",
                    "SKIPPED",
                }:
                    blockers.append("required CI is not successful")
            elif "state" in check:
                if check.get("state") != "SUCCESS":
                    blockers.append("required CI is not successful")
            else:
                blockers.append("invalid CI result")
        for review in pr.get("reviews") or []:
            if (
                isinstance(review, dict)
                and review.get("state") == "CHANGES_REQUESTED"
            ):
                blockers.append("review changes are requested")
        return list(dict.fromkeys(blockers))

    def _record_pane(self, item: IssueState, pane_id: str) -> None:
        """Persist only opaque pane identifiers returned by Herdr for this Issue."""
        if not pane_id:
            raise RuntimeError("agent did not return a pane id")
        if pane_id not in item.owned_panes:
            item.owned_panes.append(pane_id)

    def _record_gitleaks_artifact(
        self,
        state: ControllerState,
        item: IssueState,
    ) -> None:
        # Persist the deterministic identifiers before a scan so an abnormal
        # Docker exit leaves a recoverable, but still ownership-checked, trail.
        name = getattr(self.gitleaks, "name", None)
        cidfile = getattr(self.gitleaks, "cidfile", None)
        if not callable(name) or not callable(cidfile):
            return
        item.secret_scan_container_name = name(
            state.run_id, item.issue_number, item.attempt
        )
        item.secret_scan_cidfile = str(
            cidfile(state.run_id, item.issue_number, item.attempt)
        )
        self.store.save(state)

    def _merge_is_confirmed(self, item: IssueState) -> bool:
        """Confirm that deleting a local branch cannot discard an unmerged PR."""
        if not item.pr_url or not item.commit_sha:
            return False
        pr = self.gh.pr(item.pr_url)
        return (
            pr.get("state") == "MERGED"
            and pr.get("headRefOid") == item.commit_sha
            and pr.get("headRefName") == item.branch
        )

    def _cleanup_after_merge(
        self,
        state: ControllerState,
        item: IssueState,
        *,
        merge_confirmed: bool,
    ) -> None:
        """Best-effort local cleanup.  It never changes a successful merge."""
        if item.phase not in {Phase.DONE, Phase.CLEANED}:
            return
        errors: list[str] = []
        try:
            confirmed = merge_confirmed or self._merge_is_confirmed(item)
        except RuntimeError as exc:
            confirmed = False
            errors.append(f"merge verification failed: {exc}")
        if not confirmed:
            errors.append("merged PR/head ownership could not be confirmed")

        pane_ids = list(dict.fromkeys([
            *item.owned_panes,
            *([item.pane_id] if item.pane_id else []),
        ]))
        panes_safe = True
        try:
            panes = {
                str(pane.get("pane_id")): pane for pane in self.herdr.panes()
            }
            for pane_id in pane_ids:
                pane = panes.get(pane_id)
                if pane is None:
                    continue
                if pane.get("agent_status") == "working":
                    errors.append(f"owned pane is still working: {pane_id}")
                    panes_safe = False
                    continue
                self.herdr.close_pane(pane_id)
        except (RuntimeError, AttributeError) as exc:
            errors.append(f"pane cleanup failed: {exc}")
            panes_safe = False

        worktree_removed = False
        if item.worktree and panes_safe:
            try:
                worktree = self._owned_worktree(item)
                if not self.git.is_clean(worktree):
                    errors.append("worktree is not clean")
                elif not confirmed:
                    errors.append("worktree retained until merge is confirmed")
                else:
                    self.git.remove_worktree(worktree)
                    worktree_removed = True
            except (OSError, RuntimeError) as exc:
                # A missing canonical worktree after an earlier successful
                # cleanup is benign; any other ownership failure is retained.
                expected = worktree_path(self.repo, item.issue_number)
                if Path(item.worktree).resolve() == expected.resolve() and not expected.exists():
                    worktree_removed = True
                else:
                    errors.append(f"worktree cleanup failed: {exc}")

        if panes_safe and confirmed and (worktree_removed or not item.worktree):
            try:
                branch_exists = getattr(self.git, "branch_exists")
                branch_head = getattr(self.git, "branch_head")
                if branch_exists(item.branch):
                    if branch_head(item.branch) != item.commit_sha:
                        raise RuntimeError("local branch head does not match recorded commit")
                    # The caller confirmed MERGED and this exact local head,
                    # so force-delete only this local branch. No remote ref
                    # is ever touched.
                    self.git.delete_branch(item.branch, force=True)
            except (AttributeError, RuntimeError) as exc:
                errors.append(f"local branch cleanup failed: {exc}")

        cleanup = getattr(self.gitleaks, "cleanup", None)
        if callable(cleanup) and (
            item.secret_scan_container_name or item.secret_scan_cidfile
        ):
            try:
                cleanup(
                    state.run_id,
                    item.issue_number,
                    item.attempt,
                    item.secret_scan_container_name,
                    item.secret_scan_cidfile,
                )
                item.secret_scan_container_name = None
                item.secret_scan_cidfile = None
            except RuntimeError as exc:
                errors.append(f"gitleaks cleanup failed: {exc}")

        if errors:
            item.cleanup_status = "warning"
            item.cleanup_error = "; ".join(dict.fromkeys(errors))
            return
        item.cleanup_status = "cleaned"
        item.cleanup_error = None
        item.cleanup_completed_at = self._now()
        # Do not write CLEANED for new states: DONE describes delivery and
        # cleanup_status describes local resource reclamation.
        if item.phase is Phase.CLEANED:
            item.phase = Phase.DONE

    def _manual_cleanup_unmerged(self, item: IssueState) -> None:
        """Retain the legacy explicit-cleanup path for published local work."""
        worktree = self._owned_worktree(item)
        if not self.git.is_clean(worktree):
            raise RuntimeError("worktree is not a clean owned resource")
        panes = {
            str(pane.get("pane_id")): pane for pane in self.herdr.panes()
        }
        pane_ids = list(dict.fromkeys([
            *item.owned_panes,
            *([item.pane_id] if item.pane_id else []),
        ]))
        for pane_id in pane_ids:
            pane = panes.get(pane_id)
            if pane is None:
                continue
            if pane.get("agent_status") == "working":
                raise RuntimeError("owned agent is still running")
        for pane_id in pane_ids:
            if pane_id in panes:
                self.herdr.close_pane(pane_id)
        self.git.remove_worktree(worktree)
        # Legacy explicit cleanup deliberately keeps Git's non-force safety:
        # an unmerged local branch remains for recovery.
        self.git.delete_branch(item.branch, force=False)
        item.phase = Phase.CLEANED
        item.ended_at = self._now()
        item.cleanup_status = "cleaned"
        item.cleanup_error = None
        item.cleanup_completed_at = item.ended_at

    def _owned_worktree(self, item: IssueState) -> Path:
        expected = worktree_path(self.repo, item.issue_number)
        actual = Path(item.worktree).resolve(strict=True)
        if actual != expected.resolve():
            raise RuntimeError("worktree ownership mismatch")
        matches = [
            record
            for record in self.git.worktrees()
            if record.path == actual and record.branch == item.branch
        ]
        if len(matches) != 1:
            raise RuntimeError("worktree registration mismatch")
        return actual

    def _gitleaks_config(self) -> Path | None:
        path = self.repo / ".gitleaks.toml"
        return path if path.is_file() else None

    def _prompt(self, name: str) -> str:
        path = Path(__file__).parent / "prompts" / name
        return path.read_text(encoding="utf-8")

    def _item(self, state: ControllerState, number: int) -> IssueState:
        key = str(issue_number(number))
        try:
            return state.issues[key]
        except KeyError as exc:
            raise RuntimeError("Issue is not owned by this controller") from exc

    @staticmethod
    def _new_run_id() -> str:
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

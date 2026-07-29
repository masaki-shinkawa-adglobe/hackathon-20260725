from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .process_runner import ProcessResult, ProcessRunner
from .validation import relative_path, safe_name, sha


def _json_object(result: ProcessResult, source: str) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{source} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{source} returned non-object JSON")
    return value


@dataclass(frozen=True, slots=True)
class WorktreeRecord:
    path: Path
    head: str
    branch: str | None
    bare: bool = False
    detached: bool = False


@dataclass(frozen=True, slots=True)
class Change:
    path: str
    index_status: str
    worktree_status: str
    original_path: str | None = None

    @property
    def deleted(self) -> bool:
        return "D" in (self.index_status, self.worktree_status)

    @property
    def renamed(self) -> bool:
        return "R" in (self.index_status, self.worktree_status)


class GitAdapter:
    def __init__(self, runner: ProcessRunner, repo: Path, remote: str = "origin"):
        self.runner = runner
        self.repo = repo
        self.remote = remote

    def run(self, *args: str, cwd: Path | None = None) -> ProcessResult:
        return self.runner.run(["git", *args], cwd=cwd or self.repo)

    def checked(self, *args: str, cwd: Path | None = None) -> ProcessResult:
        return self.runner.checked(["git", *args], cwd=cwd or self.repo)

    def head(self, cwd: Path | None = None) -> str:
        return sha(self.checked("rev-parse", "HEAD", cwd=cwd).stdout.strip())

    def current_branch(self, cwd: Path | None = None) -> str:
        value = self.checked(
            "symbolic-ref",
            "--quiet",
            "--short",
            "HEAD",
            cwd=cwd,
        ).stdout.strip()
        if not value:
            raise RuntimeError("detached HEAD is not allowed")
        return value

    def verify_repository(self) -> None:
        root = Path(
            self.checked("rev-parse", "--show-toplevel").stdout.strip()
        ).resolve()
        if root != self.repo.resolve():
            raise RuntimeError("repository root mismatch")

    def fetch_base(self, base: str) -> str:
        self.checked(
            "fetch",
            "--no-tags",
            self.remote,
            f"refs/heads/{base}:refs/remotes/{self.remote}/{base}",
        )
        return sha(
            self.checked(
                "rev-parse",
                "--verify",
                f"refs/remotes/{self.remote}/{base}",
            ).stdout.strip()
        )

    def remote_base_sha(self, base: str) -> str:
        return sha(
            self.checked(
                "rev-parse",
                "--verify",
                f"refs/remotes/{self.remote}/{base}",
            ).stdout.strip()
        )

    def branch_exists(self, branch: str) -> bool:
        return (
            self.run(
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            ).returncode
            == 0
        )

    def branch_head(self, branch: str) -> str:
        return sha(
            self.checked(
                "rev-parse", "--verify", f"refs/heads/{branch}"
            ).stdout.strip()
        )

    def add_worktree(self, path: Path, branch: str, base_sha: str) -> None:
        if path.exists() or self.branch_exists(branch):
            raise RuntimeError("branch or worktree already exists")
        self.checked(
            "worktree",
            "add",
            "-b",
            branch,
            "--",
            str(path),
            sha(base_sha),
        )

    def worktrees(self) -> list[WorktreeRecord]:
        output = self.checked("worktree", "list", "--porcelain", "-z").stdout
        records: list[WorktreeRecord] = []
        fields: dict[str, str] = {}
        flags: set[str] = set()
        for token in output.split("\0"):
            if not token:
                if fields:
                    records.append(
                        WorktreeRecord(
                            path=Path(fields["worktree"]).resolve(),
                            head=sha(fields["HEAD"]),
                            branch=fields.get("branch", "").removeprefix(
                                "refs/heads/"
                            )
                            or None,
                            bare="bare" in flags,
                            detached="detached" in flags,
                        )
                    )
                    fields = {}
                    flags = set()
                continue
            key, separator, value = token.partition(" ")
            if separator:
                fields[key] = value
            else:
                flags.add(key)
        return records

    def changes(self, cwd: Path) -> list[Change]:
        output = self.checked(
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            cwd=cwd,
        ).stdout
        tokens = output.split("\0")
        changes: list[Change] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if not token:
                continue
            if len(token) < 4 or token[2] != " ":
                raise RuntimeError("unexpected git status record")
            index_status, worktree_status = token[0], token[1]
            path = relative_path(token[3:])
            original: str | None = None
            if "R" in (index_status, worktree_status) or "C" in (
                index_status,
                worktree_status,
            ):
                if index >= len(tokens) or not tokens[index]:
                    raise RuntimeError("incomplete rename status")
                original = relative_path(tokens[index])
                index += 1
            changes.append(
                Change(
                    path=path,
                    index_status=index_status,
                    worktree_status=worktree_status,
                    original_path=original,
                )
            )
        return changes

    def diff_for_scan(self, cwd: Path) -> str:
        tracked = self.checked(
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "HEAD",
            "--",
            cwd=cwd,
        ).stdout
        sections = [tracked]
        for change in self.changes(cwd):
            if change.index_status != "?" or change.worktree_status != "?":
                continue
            path = cwd / change.path
            if path.is_symlink() or not path.is_file():
                continue
            if path.stat().st_size > 5 * 1024 * 1024:
                raise RuntimeError(f"untracked file is too large: {change.path}")
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                sections.append(f"Binary file {change.path}\n")
            else:
                sections.append(
                    f"diff --git a/{change.path} b/{change.path}\n"
                    f"--- /dev/null\n+++ b/{change.path}\n"
                    + "".join(f"+{line}\n" for line in content.splitlines())
                )
        return "\n".join(sections)

    def numstat(self, cwd: Path) -> tuple[int, bool]:
        output = self.checked("diff", "--numstat", "HEAD", "--", cwd=cwd).stdout
        changed_lines = 0
        binary = False
        for line in output.splitlines():
            added, deleted, _path = line.split("\t", 2)
            if added == "-" or deleted == "-":
                binary = True
            else:
                changed_lines += int(added) + int(deleted)
        for change in self.changes(cwd):
            if change.index_status == "?" and change.worktree_status == "?":
                path = cwd / change.path
                try:
                    changed_lines += len(path.read_text(encoding="utf-8").splitlines())
                except (UnicodeDecodeError, OSError):
                    binary = True
        return changed_lines, binary

    def committed_changes(
        self,
        base_sha: str,
        head_sha: str,
    ) -> list[Change]:
        output = self.checked(
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            sha(base_sha),
            sha(head_sha),
            "--",
        ).stdout
        tokens = output.split("\0")
        changes: list[Change] = []
        index = 0
        while index < len(tokens):
            status = tokens[index]
            index += 1
            if not status:
                continue
            code = status[0]
            if code in {"R", "C"}:
                if index + 1 >= len(tokens):
                    raise RuntimeError("incomplete committed rename")
                original = relative_path(tokens[index])
                path = relative_path(tokens[index + 1])
                index += 2
            else:
                if index >= len(tokens):
                    raise RuntimeError("incomplete committed change")
                original = None
                path = relative_path(tokens[index])
                index += 1
            changes.append(
                Change(
                    path=path,
                    index_status=code,
                    worktree_status=" ",
                    original_path=original,
                )
            )
        return changes

    def committed_numstat(
        self,
        base_sha: str,
        head_sha: str,
    ) -> tuple[int, bool]:
        output = self.checked(
            "diff",
            "--numstat",
            sha(base_sha),
            sha(head_sha),
            "--",
        ).stdout
        changed_lines = 0
        binary = False
        for line in output.splitlines():
            added, deleted, _path = line.split("\t", 2)
            if added == "-" or deleted == "-":
                binary = True
            else:
                changed_lines += int(added) + int(deleted)
        return changed_lines, binary

    def unsafe_tree_paths(
        self,
        head_sha: str,
        paths: list[str],
    ) -> tuple[bool, bool]:
        if not paths:
            return False, False
        output = self.checked(
            "ls-tree",
            "-z",
            sha(head_sha),
            "--",
            *paths,
        ).stdout
        symlink = False
        submodule = False
        for record in output.split("\0"):
            if not record:
                continue
            metadata, _separator, _path = record.partition("\t")
            mode, kind, _object = metadata.split(" ", 2)
            symlink = symlink or mode == "120000"
            submodule = submodule or mode == "160000" or kind == "commit"
        return symlink, submodule

    def stage(self, cwd: Path) -> None:
        self.checked("add", "-A", "--", ".", cwd=cwd)

    def staged_diff_for_scan(self, cwd: Path) -> str:
        return self.checked(
            "diff",
            "--cached",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "--",
            cwd=cwd,
        ).stdout

    def commit(self, cwd: Path, message: str) -> str:
        self.checked(
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            message,
            cwd=cwd,
        )
        return self.head(cwd)

    def is_clean(self, cwd: Path) -> bool:
        return not self.changes(cwd)

    def push(self, branch: str, base: str) -> None:
        if branch in {"main", "master", base}:
            raise ValueError("refusing base branch push")
        self.checked(
            "push",
            "--porcelain",
            self.remote,
            f"refs/heads/{branch}:refs/heads/{branch}",
        )

    def remove_worktree(self, path: Path) -> None:
        self.checked("worktree", "remove", "--", str(path))

    def delete_branch(self, branch: str, *, force: bool = False) -> None:
        # `force=True` is used only after the Controller has confirmed a
        # merged PR and the exact recorded local head. Squash merges do not
        # make the original commit an ancestor of the base. This never
        # addresses a remote ref.
        self.checked("branch", "-D" if force else "-d", "--", branch)


class GitHubAdapter:
    def __init__(self, runner: ProcessRunner):
        self.runner = runner

    def _json(self, argv: list[str]) -> Any:
        result = self.runner.checked(["gh", *argv])
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("gh returned invalid JSON") from exc

    def repo(self) -> dict[str, Any]:
        value = self._json(
            [
                "repo",
                "view",
                "--json",
                "nameWithOwner,defaultBranchRef,url",
            ]
        )
        if not isinstance(value, dict):
            raise RuntimeError("gh repo view returned non-object JSON")
        return value

    def issue(self, number: int) -> dict[str, Any]:
        value = self._json(
            [
                "issue",
                "view",
                str(number),
                "--json",
                "number,title,url,body,labels,comments",
            ]
        )
        if not isinstance(value, dict) or value.get("number") != number:
            raise RuntimeError("unexpected issue response")
        return value

    def list_issues(self, limit: int = 100) -> list[dict[str, Any]]:
        value = self._json(
            [
                "issue",
                "list",
                "--state",
                "open",
                "--limit",
                str(limit),
                "--json",
                "number,title,url,body,labels",
            ]
        )
        if not isinstance(value, list) or not all(
            isinstance(item, dict) for item in value
        ):
            raise RuntimeError("unexpected issue list response")
        return value

    def comment_issue(self, number: int, body: str) -> None:
        self.runner.checked(
            ["gh", "issue", "comment", str(number), "--body", body]
        )

    def existing_pr(self, branch: str) -> dict[str, Any] | None:
        value = self._json(
            [
                "pr",
                "list",
                "--state",
                "all",
                "--head",
                branch,
                "--limit",
                "2",
                "--json",
                "number,url,headRefName,headRefOid,state,isDraft",
            ]
        )
        if not isinstance(value, list):
            raise RuntimeError("unexpected PR list response")
        if len(value) > 1:
            raise RuntimeError("multiple PRs use the expected branch")
        return value[0] if value else None

    def create_pr(
        self,
        branch: str,
        base: str,
        title: str,
        body: str,
    ) -> str:
        result = self.runner.checked(
            [
                "gh",
                "pr",
                "create",
                "--head",
                branch,
                "--base",
                base,
                "--title",
                title,
                "--body",
                body,
            ]
        )
        url = result.stdout.strip()
        if not url.startswith("https://"):
            raise RuntimeError("gh pr create returned an invalid URL")
        return url

    def pr(self, value: str | int) -> dict[str, Any]:
        result = self._json(
            [
                "pr",
                "view",
                str(value),
                "--json",
                (
                    "number,url,state,isDraft,headRefName,headRefOid,baseRefName,"
                    "mergeable,mergeStateStatus,statusCheckRollup,labels,reviews"
                ),
            ]
        )
        if not isinstance(result, dict):
            raise RuntimeError("unexpected PR response")
        return result

    def set_risk_label(
        self,
        pr: str,
        label: str,
        remove: tuple[str, ...] = (),
    ) -> None:
        recognized = {"risk:low", "risk:medium", "risk:high"}
        if label not in recognized or any(old not in recognized for old in remove):
            raise ValueError("invalid risk label")
        argv = ["gh", "pr", "edit", pr, "--add-label", label]
        for old in remove:
            argv.extend(["--remove-label", old])
        self.runner.checked(argv)

    def merge(self, pr: str, head_sha: str) -> None:
        self.runner.checked(
            [
                "gh",
                "pr",
                "merge",
                pr,
                "--squash",
                "--match-head-commit",
                sha(head_sha),
            ]
        )


class HerdrAdapter:
    def __init__(self, runner: ProcessRunner):
        self.runner = runner

    def _json(self, argv: list[str]) -> dict[str, Any]:
        return _json_object(self.runner.checked(["herdr", *argv]), "herdr")

    def help_commands(self) -> list[ProcessResult]:
        return [
            self.runner.run(["herdr", "--help"]),
            self.runner.run(["herdr", "pane", "--help"]),
            self.runner.run(["herdr", "agent", "--help"]),
            self.runner.run(["herdr", "worktree", "--help"]),
        ]

    def current_pane(self) -> dict[str, Any]:
        value = self._json(["pane", "current"])
        pane = value.get("result", {}).get("pane")
        if not isinstance(pane, dict):
            raise RuntimeError("invalid current pane response")
        return pane

    def panes(self) -> list[dict[str, Any]]:
        value = self._json(["pane", "list"])
        panes = value.get("result", {}).get("panes")
        if not isinstance(panes, list):
            raise RuntimeError("invalid pane list response")
        return panes

    def agents(self) -> list[dict[str, Any]]:
        value = self._json(["agent", "list"])
        agents = value.get("result", {}).get("agents")
        if not isinstance(agents, list):
            raise RuntimeError("invalid agent list response")
        return agents

    def split(self, cwd: Path) -> str:
        value = self._json(
            [
                "pane",
                "split",
                "--current",
                "--direction",
                "right",
                "--ratio",
                "0.5",
                "--cwd",
                str(cwd),
                "--no-focus",
            ]
        )
        result = value.get("result", {})
        pane = result.get("pane")
        if isinstance(pane, dict):
            pane_id = pane.get("pane_id")
        else:
            pane_id = result.get("pane_id")
        if not isinstance(pane_id, str) or not pane_id:
            raise RuntimeError("invalid opaque pane id")
        return pane_id

    def start(
        self,
        pane_id: str,
        name: str,
        codex_args: list[str],
        timeout_ms: int = 60_000,
    ) -> None:
        safe_name(name, "agent name")
        self.runner.checked(
            [
                "herdr",
                "agent",
                "start",
                name,
                "--kind",
                "codex",
                "--pane",
                pane_id,
                "--timeout",
                str(timeout_ms),
                "--",
                *codex_args,
            ]
        )

    def prompt(self, name: str, text: str) -> None:
        safe_name(name, "agent name")
        self.runner.checked(
            [
                "herdr",
                "agent",
                "prompt",
                name,
                text,
                "--wait",
                "--until",
                "working",
                "--until",
                "idle",
                "--until",
                "done",
                "--until",
                "blocked",
                "--timeout",
                "30000",
            ]
        )

    def get(self, name: str) -> dict[str, Any]:
        safe_name(name, "agent name")
        value = self._json(["agent", "get", name])
        agent = value.get("result", {}).get("agent")
        if not isinstance(agent, dict):
            raise RuntimeError("invalid agent response")
        return agent

    def read(self, name: str, lines: int = 4000) -> str:
        safe_name(name, "agent name")
        result = self.runner.checked(
            [
                "herdr",
                "agent",
                "read",
                name,
                "--source",
                "recent-unwrapped",
                "--lines",
                str(lines),
            ]
        )
        return result.stdout

    def close_pane(self, pane_id: str) -> None:
        if not pane_id or any(character.isspace() for character in pane_id):
            raise ValueError("invalid pane id")
        self.runner.checked(["herdr", "pane", "close", pane_id])

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import Any


class Phase(StrEnum):
    DISCOVERED = "discovered"
    PLANNING = "planning"
    AWAITING_INPUT = "awaiting_input"
    PREPARING = "preparing"
    RUNNING = "running"
    VALIDATING = "validating"
    REVIEWING = "reviewing"
    READY_TO_COMMIT = "ready_to_commit"
    COMMITTED = "committed"
    PUBLISHED = "published"
    MERGE_EVALUATION = "merge_evaluation"
    AWAITING_MERGE_APPROVAL = "awaiting_merge_approval"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    CLEANED = "cleaned"


@dataclass(slots=True)
class TestResult:
    name: str
    result: str
    summary: str = ""


@dataclass(slots=True)
class IssueState:
    issue_number: int
    issue_url: str = ""
    title: str = ""
    branch: str = ""
    worktree: str = ""
    pane_id: str | None = None
    # `pane_id` is retained for states written by older controllers.  New
    # controllers record every non-planner pane they own here.
    owned_panes: list[str] = field(default_factory=list)
    agent_name: str = ""
    phase: Phase = Phase.DISCOVERED
    attempt: int = 1
    base_sha: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    log_path: str | None = None
    changed_paths: list[str] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    secret_scan_container_name: str | None = None
    secret_scan_cidfile: str | None = None
    commit_sha: str | None = None
    pr_url: str | None = None
    last_error: str | None = None
    risk: str | None = None
    risk_head_sha: str | None = None
    worker_result: dict[str, Any] | None = None
    reviewer_result: dict[str, Any] | None = None
    clarification_marker: str | None = None
    clarification_comment_url: str | None = None
    clarification_answer: dict[str, str] | None = None
    publish_requested: bool = True
    # Cleanup is deliberately independent from delivery.  In particular, a
    # successfully merged PR remains DONE when a local cleanup needs recovery.
    cleanup_status: str = "pending"
    cleanup_error: str | None = None
    cleanup_completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["phase"] = self.phase.value
        return data

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "IssueState":
        value = dict(value)
        value["phase"] = Phase(value.get("phase", "discovered"))
        # State version 1 predates cleanup metadata and only had pane_id.
        value.setdefault("owned_panes", [])
        value.setdefault("cleanup_status", "cleaned" if value["phase"] is Phase.CLEANED else "pending")
        value.setdefault("cleanup_error", None)
        value.setdefault("cleanup_completed_at", None)
        return cls(**value)


@dataclass(slots=True)
class ControllerState:
    version: int = 1
    run_id: str = ""
    issues: dict[str, IssueState] = field(default_factory=dict)
    plan: dict[str, Any] | None = None
    planner_input_digest: str | None = None
    planner_fallback: bool = False
    planner_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "issues": {key: value.to_dict() for key, value in self.issues.items()},
            "plan": self.plan,
            "planner_input_digest": self.planner_input_digest,
            "planner_fallback": self.planner_fallback,
            "planner_error": self.planner_error,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ControllerState":
        if value.get("version", 1) != 1:
            raise ValueError("unsupported state version")
        raw_issues = value.get("issues", {})
        if not isinstance(raw_issues, dict):
            raise ValueError("invalid issues state")
        return cls(
            version=1,
            run_id=value.get("run_id", ""),
            plan=value.get("plan"),
            planner_input_digest=value.get("planner_input_digest"),
            planner_fallback=bool(value.get("planner_fallback", False)),
            planner_error=value.get("planner_error"),
            issues={
                key: IssueState.from_dict(item)
                for key, item in raw_issues.items()
            },
        )

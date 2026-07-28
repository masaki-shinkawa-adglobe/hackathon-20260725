from __future__ import annotations

from pathlib import Path

from .adapters import GitAdapter
from .models import ControllerState, Phase


def reconcile(state: ControllerState, git: GitAdapter) -> list[str]:
    """Reconcile read-only facts; never adopt or delete unknown resources."""
    records = {record.path: record for record in git.worktrees()}
    warnings: list[str] = []
    terminal = {
        Phase.COMMITTED,
        Phase.PUBLISHED,
        Phase.DONE,
        Phase.CLEANED,
    }
    for item in state.issues.values():
        if not item.worktree or item.phase is Phase.CLEANED:
            continue
        path = Path(item.worktree).resolve()
        record = records.get(path)
        if record is None:
            if item.phase not in terminal:
                item.phase = Phase.BLOCKED
                item.last_error = "blocked:ownership"
                warnings.append(str(item.issue_number))
            continue
        if record.branch != item.branch:
            item.phase = Phase.BLOCKED
            item.last_error = "blocked:ownership"
            warnings.append(str(item.issue_number))
            continue
        if item.commit_sha and record.head != item.commit_sha:
            item.phase = Phase.BLOCKED
            item.last_error = "blocked:head-changed"
            warnings.append(str(item.issue_number))
    return warnings

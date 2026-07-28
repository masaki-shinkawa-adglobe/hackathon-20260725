from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path

from .adapters import Change
from .config import ControllerConfig
from .validation import relative_path


def _matches(path: str, pattern: str) -> bool:
    normalized = pattern.rstrip("/")
    return (
        fnmatch.fnmatchcase(path, pattern)
        or path == normalized
        or path.startswith(f"{normalized}/")
    )


def check_paths(paths: list[str], config: ControllerConfig) -> list[str]:
    reasons: list[str] = []
    for raw in paths:
        path = relative_path(raw)
        if any(_matches(path, pattern) for pattern in config.forbidden_paths):
            reasons.append(f"forbidden path: {path}")
        if any(_matches(path, pattern) for pattern in config.protected_paths):
            reasons.append(f"protected path: {path}")
    return reasons


def inspect_changes(
    worktree: Path,
    changes: list[Change],
    config: ControllerConfig,
) -> list[str]:
    reasons = check_paths([change.path for change in changes], config)
    seen: set[str] = set()
    for change in changes:
        if change.path in seen:
            reasons.append(f"duplicate changed path: {change.path}")
        seen.add(change.path)
        target = worktree / change.path
        if target.is_symlink():
            reasons.append(f"symlink change: {change.path}")
        if target.exists() and target.is_file() and target.stat().st_size > 5 * 1024 * 1024:
            reasons.append(f"large file: {change.path}")
        if change.original_path:
            reasons.extend(check_paths([change.original_path], config))
    return reasons


@dataclass(frozen=True, slots=True)
class LowRiskInput:
    paths: tuple[str, ...]
    changed_files: int
    changed_lines: int
    risk: str
    reviewer_ok: bool
    current_head: bool
    ci_ok: bool
    human_elevated: bool
    has_delete: bool = False
    has_rename: bool = False
    has_binary: bool = False
    has_symlink: bool = False
    has_submodule: bool = False
    unresolved: bool = False


def low_risk_reasons(
    evidence: LowRiskInput,
    config: ControllerConfig,
) -> list[str]:
    reasons: list[str] = []
    if (
        evidence.risk != "low"
        or not evidence.reviewer_ok
        or not evidence.current_head
    ):
        reasons.append("fresh low-risk review required")
    if not evidence.ci_ok:
        reasons.append("CI not successful")
    if evidence.human_elevated:
        reasons.append("human risk elevation")
    if (
        evidence.changed_files > config.max_changed_files
        or evidence.changed_lines > config.max_changed_lines
    ):
        reasons.append("change size exceeds policy")
    if any(
        not any(_matches(path, allowed) for allowed in config.allowed_paths)
        for path in evidence.paths
    ):
        reasons.append("path not allowlisted")
    denied = config.denied_paths + config.protected_paths + config.forbidden_paths
    if any(
        any(_matches(path, pattern) for pattern in denied)
        for path in evidence.paths
    ):
        reasons.append("denied or protected path")
    if any(
        (
            evidence.has_delete,
            evidence.has_rename,
            evidence.has_binary,
            evidence.has_symlink,
            evidence.has_submodule,
            evidence.unresolved,
        )
    ):
        reasons.append("unsafe diff metadata")
    return reasons


def _safe_bullets(values: object, fallback: str) -> str:
    if not isinstance(values, list):
        return f"- {fallback}"
    bullets: list[str] = []
    for value in values[:20]:
        if not isinstance(value, str):
            continue
        line = " ".join(value.split())
        if line:
            bullets.append(f"- {line[:500]}")
    return "\n".join(bullets) or f"- {fallback}"


def build_pr_body(
    issue: int,
    commit: str,
    changed: list[str],
    tests: list[dict],
    draft: dict,
    run_id: str,
) -> str:
    actual_tests = [
        f"{item.get('name', 'test')}: {item.get('result', 'unknown')}"
        for item in tests
        if isinstance(item, dict)
    ]
    fallback_summary = (
        "Controller verified changes: " + ", ".join(changed[:20])
        if changed
        else "Controller verified the committed diff."
    )
    return (
        f"Closes #{issue}\n\n"
        f"## Summary\n{_safe_bullets(draft.get('summary'), fallback_summary)}\n\n"
        f"## Assumptions\n{_safe_bullets(draft.get('assumptions'), 'なし')}\n\n"
        f"## Tests\n{_safe_bullets(actual_tests, 'not run')}\n\n"
        "## Controller\n"
        f"- Run: {run_id}\n"
        f"- Commit: {commit}\n"
    )

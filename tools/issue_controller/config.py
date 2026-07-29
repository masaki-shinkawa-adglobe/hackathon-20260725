from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any
import tomllib


DEFAULT_FORBIDDEN = (".git", ".env", ".env.*", "*.pem", "*.key")
DEFAULT_PROTECTED = (
    ".github/workflows",
    "AGENTS.md",
    ".agents",
    ".gitleaks.toml",
    ".gitleaksignore",
    "tools/issue_controller",
)
DEFAULT_ALLOWED = ("docs/**", "README.md")
DEFAULT_DENIED = (
    ".github/**",
    "config/**",
    "migrations/**",
    "**/package.json",
    "**/package-lock.json",
    "**/pnpm-lock.yaml",
    "**/yarn.lock",
    "**/bun.lock*",
)


@dataclass(frozen=True, slots=True)
class VerifyCommand:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    base_branch: str = "main"
    remote: str = "origin"
    max_parallel: int = 2
    branch_template: str = "issue/{number}-{slug}"
    commit_template: str = "issue #{number}: {title}"
    worker_model: str = "gpt-5.6-terra"
    worker_reasoning: str = "medium"
    reviewer_model: str = "gpt-5.6-sol"
    reviewer_reasoning: str = "high"
    worker_timeout: int = 3600
    reviewer_timeout: int = 1200
    planner_timeout: int = 300
    planner_model: str = "gpt-5.6-sol"
    planner_reasoning: str = "medium"
    planner_fallback: str = "blocked"
    docker: str = "docker"
    image_lock: str = "tools/gitleaks-image.lock"
    gitleaks_timeout: int = 120
    forbidden_paths: tuple[str, ...] = DEFAULT_FORBIDDEN
    protected_paths: tuple[str, ...] = DEFAULT_PROTECTED
    allowed_paths: tuple[str, ...] = DEFAULT_ALLOWED
    denied_paths: tuple[str, ...] = DEFAULT_DENIED
    max_changed_files: int = 5
    max_changed_lines: int = 50
    allowed_author_associations: tuple[str, ...] = (
        "OWNER",
        "MEMBER",
        "COLLABORATOR",
    )
    verify_commands: tuple[VerifyCommand, ...] = field(default_factory=tuple)


def _table(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a table")
    return value


def _strings(value: object, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ValueError(f"{name} must be a non-empty string list")
    return tuple(value)


def _positive_int(value: object, name: str, maximum: int = 86_400) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= maximum
    ):
        raise ValueError(f"{name} is out of range")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or any(
        ord(character) < 32 for character in value
    ):
        raise ValueError(f"{name} must be a non-empty printable string")
    return value


def _planner_fallback(value: object) -> str:
    fallback = _string(value, "planner.fallback")
    if fallback not in {"deterministic", "blocked"}:
        raise ValueError("planner.fallback must be deterministic or blocked")
    return fallback


def load_config(path: Path) -> ControllerConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if raw.get("version") != 1:
        raise ValueError("unsupported config version")

    repository = _table(raw, "repository")
    secret_scan = _table(raw, "secret_scan")
    scheduler = _table(raw, "scheduler")
    policy = _table(raw, "policy")
    merge = _table(raw, "merge")
    branch = _table(raw, "branch")
    commit = _table(raw, "commit")
    timeouts = _table(raw, "timeouts")
    worker = _table(raw, "worker")
    reviewer = _table(raw, "reviewer")
    planner = _table(raw, "planner")
    clarification = _table(raw, "clarification")

    # Old Codex sandbox/permission knobs are not a security boundary for this
    # controller.  Rejecting them avoids silently accepting a configuration
    # that could make a worker broader than the verified launch contract.
    legacy_keys = {"sandbox_mode", "default_permissions", "permissions", "add_dir"}
    for table_name, table in (("root", raw), ("worker", worker), ("reviewer", reviewer)):
        if legacy_keys & set(table):
            raise ValueError(f"legacy permission setting in {table_name}")

    if secret_scan.get("required", True) is not True:
        raise ValueError("secret_scan.required must be true")

    commands: list[VerifyCommand] = []
    verify = _table(raw, "verify")
    raw_commands = verify.get("commands", [])
    if not isinstance(raw_commands, list):
        raise ValueError("verify.commands must be an array")
    for command in raw_commands:
        if not isinstance(command, dict):
            raise ValueError("verify command must be a table")
        commands.append(
            VerifyCommand(
                _string(command.get("name"), "verify.name"),
                _strings(command.get("argv"), "verify.argv"),
                _positive_int(
                    command.get("timeout_seconds"),
                    "verify.timeout_seconds",
                ),
            )
        )

    return ControllerConfig(
        base_branch=_string(repository.get("base_branch", "main"), "base_branch"),
        remote=_string(repository.get("remote", "origin"), "remote"),
        max_parallel=_positive_int(
            scheduler.get("max_parallel", 2),
            "scheduler.max_parallel",
            maximum=32,
        ),
        branch_template=_string(
            branch.get("template", "issue/{number}-{slug}"),
            "branch.template",
        ),
        commit_template=_string(
            commit.get("template", "issue #{number}: {title}"),
            "commit.template",
        ),
        worker_model=_string(
            worker.get("model", "gpt-5.6-terra"),
            "worker.model",
        ),
        worker_reasoning=_string(
            worker.get("reasoning_effort", "medium"),
            "worker.reasoning_effort",
        ),
        reviewer_model=_string(
            reviewer.get("model", "gpt-5.6-sol"),
            "reviewer.model",
        ),
        reviewer_reasoning=_string(
            reviewer.get("reasoning_effort", "high"),
            "reviewer.reasoning_effort",
        ),
        worker_timeout=_positive_int(
            timeouts.get("worker_seconds", 3600),
            "timeouts.worker_seconds",
        ),
        reviewer_timeout=_positive_int(
            timeouts.get("reviewer_seconds", 1200),
            "timeouts.reviewer_seconds",
        ),
        planner_timeout=_positive_int(
            timeouts.get("planner_seconds", 300),
            "timeouts.planner_seconds",
        ),
        planner_model=_string(
            planner.get("model", "gpt-5.6-sol"),
            "planner.model",
        ),
        planner_reasoning=_string(
            planner.get("reasoning_effort", "medium"),
            "planner.reasoning_effort",
        ),
        planner_fallback=_planner_fallback(
            planner.get("fallback", "blocked"),
        ),
        docker=_string(
            secret_scan.get("runtime", "docker"),
            "secret_scan.runtime",
        ),
        image_lock=_string(
            secret_scan.get("image_lock", "tools/gitleaks-image.lock"),
            "secret_scan.image_lock",
        ),
        gitleaks_timeout=_positive_int(
            secret_scan.get("timeout_seconds", 120),
            "secret_scan.timeout_seconds",
        ),
        forbidden_paths=_strings(
            policy.get("forbidden_paths", list(DEFAULT_FORBIDDEN)),
            "policy.forbidden_paths",
        ),
        protected_paths=_strings(
            policy.get("protected_paths", list(DEFAULT_PROTECTED)),
            "policy.protected_paths",
        ),
        allowed_paths=_strings(
            merge.get("allowed_paths", list(DEFAULT_ALLOWED)),
            "merge.allowed_paths",
        ),
        denied_paths=_strings(
            merge.get("denied_paths", list(DEFAULT_DENIED)),
            "merge.denied_paths",
        ),
        max_changed_files=_positive_int(
            merge.get("max_changed_files", 5),
            "merge.max_changed_files",
            maximum=10_000,
        ),
        max_changed_lines=_positive_int(
            merge.get("max_changed_lines", 50),
            "merge.max_changed_lines",
            maximum=10_000_000,
        ),
        allowed_author_associations=_strings(
            clarification.get(
                "allowed_author_associations",
                ["OWNER", "MEMBER", "COLLABORATOR"],
            ),
            "clarification.allowed_author_associations",
        ),
        verify_commands=tuple(commands),
    )


def codex_config_layers(repository: Path) -> tuple[Path, ...]:
    """Known Codex layers that can enable the legacy sandbox mode.

    This is deliberately read-only and conservative: an unreadable existing
    layer blocks launch rather than allowing an unknown effective policy.
    """
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return (codex_home / "config.toml", repository / ".codex" / "config.toml")


def reject_legacy_sandbox_layers(repository: Path) -> None:
    for path in codex_config_layers(repository):
        if not path.exists():
            continue
        try:
            value = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise RuntimeError(f"cannot safely read Codex config layer: {path}") from exc
        if "sandbox_mode" in value or "sandbox_workspace_write" in value:
            raise RuntimeError(f"legacy Codex sandbox setting in: {path}")
        profiles = value.get("profiles", {})
        if isinstance(profiles, dict):
            for profile in profiles.values():
                if isinstance(profile, dict) and (
                    "sandbox_mode" in profile
                    or "sandbox_workspace_write" in profile
                ):
                    raise RuntimeError(f"legacy Codex profile setting in: {path}")

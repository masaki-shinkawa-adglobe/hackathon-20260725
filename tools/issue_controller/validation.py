from __future__ import annotations

import os
from pathlib import Path
import re
import unicodedata

from .process_runner import ProcessRunner


_NUMBER = re.compile(r"^[1-9][0-9]*$")
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def issue_number(value: int | str) -> int:
    if isinstance(value, bool) or not _NUMBER.fullmatch(str(value)):
        raise ValueError("issue number must be a positive decimal integer")
    return int(value)


def slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    result = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    result = result[:48].rstrip("-")
    return result or "issue"


def branch(
    number: int | str,
    title: str,
    *,
    base: str,
    template: str = "issue/{number}-{slug}",
    runner: ProcessRunner | None = None,
) -> str:
    number = issue_number(number)
    if set(re.findall(r"{([^{}]+)}", template)) - {"number", "slug"}:
        raise ValueError("branch template contains an unsupported field")
    result = template.format(number=number, slug=slug(title))
    if result in {"main", "master", base} or result.startswith("-"):
        raise ValueError("unsafe branch")
    if any(ord(character) < 32 for character in result) or len(result) > 200:
        raise ValueError("unsafe branch")
    if runner:
        check = runner.run(["git", "check-ref-format", "--branch", result])
        if check.returncode:
            raise ValueError("invalid Git branch")
    return result


def commit_message(template: str, number: int | str, title: str) -> str:
    number = issue_number(number)
    clean_title = " ".join(title.split())
    if set(re.findall(r"{([^{}]+)}", template)) - {"number", "title"}:
        raise ValueError("commit template contains an unsupported field")
    message = template.format(number=number, title=clean_title)
    if not message or len(message.encode("utf-8")) > 240:
        raise ValueError("commit message is empty or too long")
    if "\n" in message or "\r" in message or any(ord(c) < 32 for c in message):
        raise ValueError("commit message contains control characters")
    return message


def sha(value: str) -> str:
    if not _SHA.fullmatch(value):
        raise ValueError("expected a 40-char lowercase SHA")
    return value


def safe_name(value: str, label: str = "name") -> str:
    if not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"unsafe {label}")
    return value


def worktree_root(repository: Path) -> Path:
    repository = repository.resolve(strict=True)
    root = repository.parent / ".worktrees" / repository.name
    for ancestor in (root.parent, root):
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError("symlinked worktree root")
    resolved_parent = root.parent.resolve()
    if os.path.commonpath((str(resolved_parent), str(root.resolve()))) != str(
        resolved_parent
    ):
        raise ValueError("worktree root escapes repository parent")
    return root


def worktree_path(repository: Path, number: int | str) -> Path:
    number = issue_number(number)
    root = worktree_root(repository)
    expected = root / f"issue-{number}"
    if expected.exists() and expected.is_symlink():
        raise ValueError("symlinked worktree path")
    if expected.parent.resolve() != root.resolve():
        raise ValueError("worktree escapes root")
    return expected


def relative_path(value: str) -> str:
    if "\x00" in value or "\\" in value:
        raise ValueError("unsafe changed path")
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("unsafe changed path")
    normalized = path.as_posix()
    if normalized.startswith("-"):
        raise ValueError("unsafe changed path")
    return normalized

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
import uuid


_MARKER = re.compile(
    r"<!-- issue-controller:clarification:"
    r"(?P<run>[a-z0-9-]+):(?P<issue>[1-9][0-9]*):(?P<token>[a-f0-9]{16}) -->"
)


def sanitize_text(value: str, maximum: int = 1000) -> str:
    clean = " ".join(value.replace("<!--", "").replace("-->", "").split())
    if not clean:
        raise ValueError("clarification text is empty")
    return clean[:maximum]


def marker(run_id: str, issue: int) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", run_id):
        raise ValueError("invalid run id")
    return (
        f"<!-- issue-controller:clarification:{run_id}:{issue}:"
        f"{uuid.uuid4().hex[:16]} -->"
    )


def comment_body(
    marker_value: str,
    question: str,
    why_blocking: str,
    options: list[str],
) -> str:
    if not _MARKER.fullmatch(marker_value):
        raise ValueError("invalid clarification marker")
    safe_options = [sanitize_text(value, 300) for value in options]
    if not 1 <= len(safe_options) <= 2:
        raise ValueError("clarification must have one or two options")
    option_lines = "\n".join(f"- {value}" for value in safe_options)
    return (
        f"{marker_value}\n"
        "自律実装を開始する前に、1点確認が必要です。\n\n"
        f"**質問:** {sanitize_text(question)}\n\n"
        f"**判断が必要な理由:** {sanitize_text(why_blocking)}\n\n"
        f"**選択肢:**\n{option_lines}\n\n"
        "このコメントへ回答してください。回答後、Controllerの"
        "`resume`で再開します。"
    )


def authorized_answer(
    comments: object,
    marker_value: str,
    allowed_associations: tuple[str, ...],
) -> dict[str, str] | None:
    if not isinstance(comments, list):
        raise ValueError("comments must be a list")
    marker_index = -1
    marker_time = ""
    for index, comment in enumerate(comments):
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        if isinstance(body, str) and marker_value in body:
            marker_index = index
            marker_time = str(comment.get("createdAt", ""))
    if marker_index < 0:
        return None
    for comment in comments[marker_index + 1 :]:
        if not isinstance(comment, dict):
            continue
        association = comment.get("authorAssociation")
        body = comment.get("body")
        if association not in allowed_associations or not isinstance(body, str):
            continue
        clean = sanitize_text(body, 4000)
        return {
            "body": clean,
            "author": str((comment.get("author") or {}).get("login", "")),
            "created_at": str(comment.get("createdAt", marker_time)),
            "accepted_at": datetime.now(UTC).isoformat(),
        }
    return None

from __future__ import annotations

import json
from typing import Any

from .validation import relative_path, sha


RESULT_MARKER = "ISSUE_CONTROLLER_RESULT:"


def _object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON output") from exc
    if not isinstance(value, dict):
        raise ValueError("result must be an object")
    return value


def marked_object(output: str) -> dict[str, Any]:
    position = output.rfind(RESULT_MARKER)
    if position < 0:
        raise ValueError("result marker not found")
    remainder = output[position + len(RESULT_MARKER) :].lstrip()
    try:
        value, _end = json.JSONDecoder().raw_decode(remainder)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid marked JSON output") from exc
    if not isinstance(value, dict):
        raise ValueError("marked result must be an object")
    return value


def _string_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"invalid {name}")
    return value


def worker_result(value: str | dict[str, Any]) -> dict[str, Any]:
    result = _object(value) if isinstance(value, str) else dict(value)
    required = {
        "schema_version",
        "status",
        "changed_files",
        "tests",
        "remaining_work",
        "clarification",
        "pr_draft",
    }
    if (
        set(result) != required
        or result["schema_version"] != 1
        or result["status"] not in {"done", "blocked", "needs_clarification"}
    ):
        raise ValueError("invalid worker result")
    result["changed_files"] = [
        relative_path(path)
        for path in _string_list(result["changed_files"], "changed files")
    ]
    _string_list(result["remaining_work"], "remaining work")
    if not isinstance(result["tests"], list):
        raise ValueError("invalid worker tests")
    for test in result["tests"]:
        if (
            not isinstance(test, dict)
            or set(test) != {"name", "result", "summary"}
            or not all(isinstance(test[key], str) for key in test)
            or test["result"] not in {"passed", "failed", "skipped"}
        ):
            raise ValueError("invalid worker test")
    if result["status"] == "needs_clarification":
        clarification = result["clarification"]
        if (
            not isinstance(clarification, dict)
            or set(clarification) != {"question", "why_blocking", "options"}
            or not isinstance(clarification["question"], str)
            or not isinstance(clarification["why_blocking"], str)
            or not 1 <= len(_string_list(clarification["options"], "options")) <= 2
        ):
            raise ValueError("invalid worker clarification")
    elif result["clarification"] is not None:
        raise ValueError("unexpected clarification")
    draft = result["pr_draft"]
    if not isinstance(draft, dict) or set(draft) != {
        "summary",
        "assumptions",
        "tests",
    }:
        raise ValueError("invalid PR draft")
    for key in draft:
        _string_list(draft[key], f"PR draft {key}")
    return result


def review_result(
    value: str | dict[str, Any],
    require_risk: bool = False,
) -> dict[str, Any]:
    result = _object(value) if isinstance(value, str) else dict(value)
    required = (
        {"verdict", "risk", "head_sha", "reasons"}
        if require_risk
        else {"verdict", "findings"}
    )
    if set(result) != required or result.get("verdict") not in {
        "OK",
        "NG",
        "BLOCKED",
    }:
        raise ValueError("invalid reviewer result")
    if require_risk:
        if result["risk"] not in {"low", "medium", "high"}:
            raise ValueError("invalid risk result")
        _string_list(result["reasons"], "risk reasons")
        result["head_sha"] = sha(result["head_sha"])
    else:
        findings = result["findings"]
        if not isinstance(findings, list):
            raise ValueError("invalid findings")
        for finding in findings:
            if (
                not isinstance(finding, dict)
                or set(finding) != {"severity", "path", "line", "message"}
                or finding["severity"] not in {"low", "medium", "high"}
                or not isinstance(finding["line"], int)
                or not isinstance(finding["message"], str)
            ):
                raise ValueError("invalid finding")
            finding["path"] = relative_path(finding["path"])
    return result

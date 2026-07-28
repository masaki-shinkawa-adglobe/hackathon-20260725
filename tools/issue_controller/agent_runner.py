from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any

from .adapters import HerdrAdapter
from .config import reject_legacy_sandbox_layers
from .result_parser import marked_object


@dataclass(frozen=True, slots=True)
class AgentRun:
    pane_id: str
    agent_name: str
    output: str
    result: dict[str, Any]
    started_at: str
    ended_at: str


class HerdrAgentRunner:
    def __init__(self, herdr: HerdrAdapter, logs_root: Path):
        self.herdr = herdr
        self.logs_root = logs_root

    def start(
        self,
        *,
        cwd: Path,
        name: str,
        model: str,
        reasoning_effort: str,
        permission_profile: str,
        prompt: str,
    ) -> tuple[str, str]:
        reject_legacy_sandbox_layers(cwd)
        if permission_profile not in {"workspace", "read-only"}:
            raise ValueError("invalid agent role")
        pane_id = self.herdr.split(cwd)
        permissions = ":workspace" if permission_profile == "workspace" else ":read-only"
        codex_args = [
            "-C",
            str(cwd),
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "-c",
            f'default_permissions="{permissions}"',
            "--ask-for-approval",
            "never",
        ]
        self.herdr.start(pane_id, name, codex_args)
        started_at = datetime.now(UTC).isoformat()
        self.herdr.prompt(name, prompt)
        return pane_id, started_at

    def collect(
        self,
        *,
        name: str,
        timeout_seconds: int,
        started_monotonic: float,
        log_name: str,
    ) -> AgentRun:
        deadline = started_monotonic + timeout_seconds
        while True:
            agent = self.herdr.get(name)
            status = agent.get("agent_status")
            if status in {"idle", "done", "blocked", "unknown"}:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("agent timeout")
            time.sleep(min(2.0, max(0.1, deadline - time.monotonic())))
        output = self.herdr.read(name)
        log_path = self.logs_root / log_name
        self._save_log(log_path, output)
        result = marked_object(output)
        return AgentRun(
            pane_id=str(agent.get("pane_id", "")),
            agent_name=name,
            output=output,
            result=result,
            started_at="",
            ended_at=datetime.now(UTC).isoformat(),
        )

    def _save_log(self, path: Path, output: str) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        content = output[-2_000_000:]
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)


def issue_payload(issue: dict[str, Any]) -> str:
    safe = {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "url": issue.get("url"),
        "body": issue.get("body"),
        "labels": issue.get("labels"),
    }
    answer = issue.get("controller_clarification_answer")
    if isinstance(answer, dict) and all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in answer.items()
    ):
        safe["controller_clarification_answer"] = answer
    return json.dumps(safe, ensure_ascii=False, sort_keys=True)

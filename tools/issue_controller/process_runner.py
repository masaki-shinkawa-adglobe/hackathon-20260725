from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ProcessResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class ProcessError(RuntimeError):
    def __init__(self, executable: str, returncode: int):
        super().__init__(f"process failed: {executable} ({returncode})")
        self.executable = executable
        self.returncode = returncode


class ProcessRunner:
    """External process boundary: argv only, never a shell."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        timeout: int | float | None = None,
        input_text: str | None = None,
        env: Mapping[str, str] | None = None,
        inherit_env: bool = True,
    ) -> ProcessResult:
        if not argv or not all(isinstance(value, str) and value for value in argv):
            raise ValueError("argv must contain non-empty strings")
        process_env = None
        if env is not None:
            process_env = os.environ.copy() if inherit_env else {}
            process_env.update(env)
        try:
            completed = subprocess.run(
                list(argv),
                cwd=cwd,
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                shell=False,
                env=process_env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"process timed out: {argv[0]}") from exc
        except OSError as exc:
            raise RuntimeError(f"cannot execute: {argv[0]}") from exc
        return ProcessResult(
            tuple(argv),
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    def checked(self, argv: Sequence[str], **kwargs: object) -> ProcessResult:
        result = self.run(argv, **kwargs)
        if result.returncode:
            raise ProcessError(argv[0], result.returncode)
        return result

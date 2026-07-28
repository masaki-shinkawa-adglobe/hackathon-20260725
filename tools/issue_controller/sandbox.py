from __future__ import annotations

import os
from pathlib import Path

from .process_runner import ProcessResult, ProcessRunner


class BubblewrapRunner:
    """Run configured verifier argv with no network and one writable worktree."""

    def __init__(
        self,
        executable: str,
        runner: ProcessRunner,
        state_root: Path | None = None,
    ):
        self.executable = executable
        self.runner = runner
        self.state_root = state_root

    def available(self) -> bool:
        result = self.runner.run([self.executable, "--version"])
        return result.returncode == 0

    def _masked_directories(self) -> list[Path]:
        home = Path.home()
        candidates = [
            home / ".ssh",
            home / ".aws",
            home / ".config" / "gh",
            home / ".config" / "herdr",
            home / ".codex",
        ]
        if self.state_root is not None:
            candidates.append(self.state_root)
        return [path.resolve() for path in candidates if path.is_dir()]

    def run(
        self,
        worktree: Path,
        argv: list[str],
        timeout: int,
    ) -> ProcessResult:
        if not self.available():
            raise RuntimeError("bubblewrap unavailable; fail closed")
        resolved = worktree.resolve(strict=True)
        command = [
            self.executable,
            "--die-with-parent",
            "--new-session",
            "--unshare-net",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--ro-bind",
            "/",
            "/",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/tmp/home",
            "--bind",
            str(resolved),
            str(resolved),
        ]
        for path in self._masked_directories():
            command.extend(["--tmpfs", str(path)])
        command.extend(
            [
                "--chdir",
                str(resolved),
                "--setenv",
                "HOME",
                "/tmp/home",
                "--setenv",
                "TMPDIR",
                "/tmp",
                "--setenv",
                "CI",
                "1",
                "--",
                *argv,
            ]
        )
        safe_env = {
            "PATH": os.environ.get(
                "PATH",
                "/usr/local/bin:/usr/bin:/bin",
            ),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        return self.runner.run(
            command,
            timeout=timeout,
            env=safe_env,
            inherit_env=False,
        )

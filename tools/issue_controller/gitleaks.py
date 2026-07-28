from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .process_runner import ProcessResult, ProcessRunner
from .validation import issue_number, safe_name


_IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ScanResult:
    clean: bool
    finding: bool
    returncode: int


class GitleaksDocker:
    def __init__(
        self,
        docker: str,
        image_lock: Path,
        state_root: Path,
        runner: ProcessRunner,
        timeout: int = 120,
    ):
        self.docker = docker
        self.image_lock = image_lock
        self.state_root = state_root
        self.runner = runner
        self.timeout = timeout

    def image(self) -> str:
        try:
            image = self.image_lock.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError("gitleaks image lock is unavailable") from exc
        if not _IMAGE.fullmatch(image):
            raise RuntimeError("invalid digest-pinned gitleaks image")
        return image

    def verify_image_is_local(self) -> None:
        image = self.image()
        result = self.runner.run(
            [
                self.docker,
                "image",
                "inspect",
                "--format",
                "{{json .RepoDigests}}",
                image,
            ]
        )
        if result.returncode:
            raise RuntimeError("pinned gitleaks image is not available locally")
        if image not in result.stdout:
            raise RuntimeError("local gitleaks image digest mismatch")

    def name(self, run_id: str, issue: int, attempt: int) -> str:
        issue = issue_number(issue)
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError("invalid attempt")
        safe_name(run_id, "run id")
        return safe_name(
            f"issue-controller-gitleaks-{run_id}-{issue}-{attempt}",
            "gitleaks container name",
        )

    def scan(
        self,
        diff: str,
        run_id: str,
        issue: int,
        attempt: int,
        config: Path | None = None,
    ) -> ScanResult:
        name = self.name(run_id, issue, attempt)
        cidfile = self.state_root / f"gitleaks-{run_id}-{issue}-{attempt}.cid"
        self.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if cidfile.exists():
            raise RuntimeError("gitleaks cidfile already exists")
        # Docker inspect is the ownership source.  A failed inspect means no
        # container exists; never infer ownership from a cidfile alone.
        if self.runner.run([self.docker, "container", "inspect", name]).returncode == 0:
            raise RuntimeError("gitleaks container name is already owned")

        argv = [
            self.docker,
            "run",
            "--name",
            name,
            "--rm",
            "--interactive",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory",
            "256m",
            "--pids-limit",
            "128",
            "--label",
            f"io.issue-controller.run={run_id}",
            "--label",
            f"io.issue-controller.issue={issue}",
            "--cidfile",
            str(cidfile),
        ]
        gitleaks_args = ["--no-banner", "--redact"]
        if config is not None:
            resolved = config.resolve(strict=True)
            if not resolved.is_file() or "," in str(resolved):
                raise RuntimeError("invalid gitleaks config")
            argv.extend(
                [
                    "--mount",
                    (
                        f"type=bind,src={resolved},"
                        "dst=/gitleaks-config/gitleaks.toml,readonly"
                    ),
                ]
            )
            gitleaks_args.extend(
                ["--config", "/gitleaks-config/gitleaks.toml"]
            )
        argv.extend([self.image(), *gitleaks_args, "stdin"])
        result: ProcessResult = self.runner.run(
            argv,
            input_text=diff,
            timeout=self.timeout,
        )
        try:
            cidfile.unlink(missing_ok=True)
        except OSError:
            pass
        if result.returncode not in {0, 1}:
            raise RuntimeError("gitleaks execution failed")
        return ScanResult(
            clean=result.returncode == 0,
            finding=result.returncode == 1,
            returncode=result.returncode,
        )

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import venv


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class IsolatedLauncherTests(unittest.TestCase):
    def test_installed_module_starts_in_isolated_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory) / "controller-venv"
            venv.EnvBuilder(with_pip=True, system_site_packages=True).create(
                environment
            )
            python = environment / "bin" / "python"
            subprocess.run(
                [
                    python,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--no-build-isolation",
                    REPOSITORY_ROOT,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            result = subprocess.run(
                [
                    python,
                    "-I",
                    "-m",
                    "issue_controller",
                    "--config",
                    REPOSITORY_ROOT / "config" / "issue-controller.example.toml",
                    "--repository",
                    REPOSITORY_ROOT,
                    "doctor",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertIn(result.returncode, (0, 1), result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("ok", output)
        self.assertIn("failures", output)

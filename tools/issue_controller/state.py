from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from .models import ControllerState

class StateStore:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "state.json"
        self.lock_path = root / "controller.lock"

    def load(self) -> ControllerState:
        if not self.path.exists():
            return ControllerState()
        try:
            return ControllerState.from_dict(
                json.loads(self.path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError("state.json is invalid; refusing recovery") from exc

    def save(self, state: ControllerState) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, name=tempfile.mkstemp(prefix=".state-", dir=self.root)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, ensure_ascii=False, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
            directory = os.open(self.root, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name): os.unlink(name)
    @contextmanager
    def lock(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_file = self.lock_path.open("a+")
        try:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another controller owns this repository") from exc
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()

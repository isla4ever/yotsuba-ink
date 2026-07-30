from __future__ import annotations

import fcntl
import json
import os
import threading
from pathlib import Path
from typing import IO


class RunStreamLeaseStoreMixin:
    """Owns the process/cross-process lease that guards one active run stream."""

    def _init_stream_leases(self) -> None:
        self._stream_leases: dict[str, tuple[str, IO[str]]] = {}
        self._stream_leases_guard = threading.Lock()

    def claim_stream(self, run_id: str, lease_id: str) -> bool:
        self._validate_run_id(run_id)
        if not isinstance(lease_id, str) or not lease_id:
            raise ValueError("Invalid stream lease_id")
        with self._stream_leases_guard:
            if run_id in self._stream_leases:
                return False
            run_dir = self.run_dir(run_id)
            if not (run_dir / "run.json").exists():
                raise FileNotFoundError(run_id)
            lock_path = run_dir / ".stream.lock"
            handle = lock_path.open("a+", encoding="utf-8")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                handle.close()
                return False
            handle.seek(0)
            handle.truncate()
            json.dump(
                {"lease_id": lease_id, "pid": os.getpid()},
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            handle.flush()
            os.fsync(handle.fileno())
            self._stream_leases[run_id] = (lease_id, handle)
            return True

    def release_stream(self, run_id: str, lease_id: str) -> bool:
        self._validate_run_id(run_id)
        with self._stream_leases_guard:
            current = self._stream_leases.get(run_id)
            if not current or current[0] != lease_id:
                return False
            self._stream_leases.pop(run_id, None)
            handle = current[1]
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
            return True

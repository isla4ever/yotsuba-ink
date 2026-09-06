"""Cross-process execution locks for one Phase 32 Run thread."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

try:  # pragma: no cover - production runs on POSIX; fallback keeps imports portable.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from novel_workflow.storage.atomic_json import require_safe_id


class Phase32ExecutionLockTimeout(TimeoutError):
    code = "phase32_execution_lock_timeout"


class Phase32RunExecutionLock:
    """Acquire a per-Run advisory file lock without blocking the event loop."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def acquire(
        self,
        run_id: str,
        *,
        timeout_seconds: float = 30.0,
        poll_seconds: float = 0.05,
    ) -> AsyncIterator[None]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        if timeout_seconds <= 0:
            raise ValueError("Execution lock timeout must be positive")
        if poll_seconds <= 0:
            raise ValueError("Execution lock poll interval must be positive")
        path = self.root / f"{hashlib.sha256(safe_run_id.encode('utf-8')).hexdigest()}.lock"
        handle = path.open("a+", encoding="utf-8")
        acquired = fcntl is None
        try:
            await self._wait_for_lock(
                handle,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )
            acquired = True
            yield
        finally:
            if fcntl is not None and acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    async def _wait_for_lock(
        self,
        handle,
        *,
        timeout_seconds: float,
        poll_seconds: float,
    ) -> None:
        if fcntl is None:
            return
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                if asyncio.get_running_loop().time() >= deadline:
                    raise Phase32ExecutionLockTimeout(
                        "Another process is already executing this Phase 32 Run"
                    )
                await asyncio.sleep(poll_seconds)


__all__ = ["Phase32ExecutionLock", "Phase32ExecutionLockTimeout", "Phase32RunExecutionLock"]

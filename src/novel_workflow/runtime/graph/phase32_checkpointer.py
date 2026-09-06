"""Dormant Phase 32 durable checkpoint context manager."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from novel_workflow.runtime.graph.checkpoint_lifecycle import (
    open_async_sqlite_checkpointer,
)


@asynccontextmanager
async def open_phase32_checkpointer(root: Path) -> AsyncIterator[AsyncSqliteSaver]:
    """Open the checkpoint namespace reserved for Phase 32 route Runs."""

    async with open_async_sqlite_checkpointer(root / "checkpoints.sqlite") as checkpointer:
        yield checkpointer


__all__ = ["open_phase32_checkpointer"]

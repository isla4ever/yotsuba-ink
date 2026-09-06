"""Shared durable LangGraph checkpoint lifecycle helpers."""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@asynccontextmanager
async def open_async_sqlite_checkpointer(path: Path) -> AsyncIterator[AsyncSqliteSaver]:
    """Open one prepared SQLite checkpointer and close it on exit."""

    path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(path)) as checkpointer:
        await prepare_async_sqlite_checkpointer(checkpointer)
        yield checkpointer


async def prepare_async_sqlite_checkpointer(checkpointer: AsyncSqliteSaver) -> None:
    """Prepare the shared schema without racing another graph connection."""

    await checkpointer.conn.execute("PRAGMA busy_timeout=30000")
    for attempt in range(10):
        async with checkpointer.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name IN ('checkpoints', 'writes')"
        ) as cursor:
            row = await cursor.fetchone()
        if row is not None and int(row[0]) == 2:
            checkpointer.is_setup = True
            return
        try:
            await checkpointer.setup()
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).casefold() or attempt == 9:
                raise
            await checkpointer.conn.rollback()
            await asyncio.sleep(0.02 * (attempt + 1))


__all__ = [
    "open_async_sqlite_checkpointer",
    "prepare_async_sqlite_checkpointer",
]

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

from novel_workflow.storage.event_projection import EventProjection, RunEventEnvelope


def sse_payload(event: dict[str, Any]) -> str:
    return f"id: {event['sequence']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def observe_run_events(
    request: Request,
    events: EventProjection,
    run_id: str,
    *,
    after: int,
) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(request, events, run_id, after=after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _event_stream(
    request: Request,
    events: EventProjection,
    run_id: str,
    *,
    after: int,
) -> AsyncIterator[str]:
    sequence = after
    while not await request.is_disconnected():
        batch = events.read(run_id, after=sequence)
        for event in batch:
            sequence = event.sequence
            yield sse_payload(event.model_dump(mode="json"))
        if _batch_reaches_terminal(batch):
            return
        await asyncio.sleep(0.25)


def _batch_reaches_terminal(batch: list[RunEventEnvelope]) -> bool:
    terminal = False
    for event in batch:
        if event.type in {"run.completed", "run.failed", "decision.required"}:
            terminal = True
        elif event.type == "decision.resolved":
            terminal = False
    return terminal


__all__ = ["observe_run_events", "sse_payload"]

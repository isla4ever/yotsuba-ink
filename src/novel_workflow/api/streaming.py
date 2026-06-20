from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

from novel_workflow.workflows.runner import NovelWorkflowRunner


def sse_payload(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_response(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(events, media_type="text/event-stream")


async def stream_runner_events(app: Any, workflow: Any, run_id: str, inputs: dict[str, Any]) -> AsyncIterator[str]:
    for rag_event in inputs.get("rag_events", []):
        event = {"run_id": run_id, **rag_event}
        app.state.run_store.append_event(run_id, event)
        yield sse_payload(event)

    runner = NovelWorkflowRunner(
        providers=app.state.providers,
        wiki_store=app.state.wiki_store,
        run_store=app.state.run_store,
    )
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            yield sse_payload(event)
            await asyncio.sleep(0)
    except Exception as exc:  # pragma: no cover
        error = {"type": "run_error", "run_id": run_id, "error": str(exc)}
        app.state.run_store.append_event(run_id, error)
        yield sse_payload(error)

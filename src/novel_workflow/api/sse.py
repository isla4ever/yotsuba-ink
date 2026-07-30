from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi.responses import StreamingResponse

from novel_workflow.workflows.runner import NovelWorkflowRunner


def sse_payload(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_response(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(events, media_type="text/event-stream")


class RunStreamLeaseConflict(RuntimeError):
    pass


def leased_stream_response(
    app: Any,
    workflow: Any,
    run_id: str,
    inputs: dict[str, Any],
    *,
    emit_input_events: bool = True,
) -> StreamingResponse:
    lease_id = f"stream-{uuid4().hex}"
    try:
        claimed = app.state.run_store.claim_stream(run_id, lease_id)
    except FileNotFoundError:
        raise
    if not claimed:
        raise RunStreamLeaseConflict(run_id)
    try:
        return stream_response(
            stream_runner_events(
                app,
                workflow,
                run_id,
                inputs,
                emit_input_events=emit_input_events,
                lease_id=lease_id,
            )
        )
    except BaseException:
        app.state.run_store.release_stream(run_id, lease_id)
        raise


async def stream_runner_events(
    app: Any,
    workflow: Any,
    run_id: str,
    inputs: dict[str, Any],
    *,
    emit_input_events: bool = True,
    lease_id: str = "",
) -> AsyncIterator[str]:
    try:
        if emit_input_events:
            for rag_event in inputs.get("rag_events", []):
                event = {"run_id": run_id, **rag_event}
                app.state.run_store.append_event(run_id, event)
                yield sse_payload(event)

        runner = NovelWorkflowRunner(
            providers=app.state.providers,
            wiki_store=app.state.wiki_store,
            run_store=app.state.run_store,
        )
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            yield sse_payload(event)
    except Exception as exc:  # pragma: no cover
        error = {"type": "run_error", "run_id": run_id, "error": str(exc)}
        app.state.run_store.append_event(run_id, error)
        yield sse_payload(error)
    finally:
        if lease_id:
            app.state.run_store.release_stream(run_id, lease_id)
        # Stream end (completion, failure, or disconnect) is the single writeback
        # point that refreshes the owning project's latest_run_id / updated_at.
        project_store = getattr(app.state, "project_store", None)
        if project_store is not None:
            project_store.touch_run(str(inputs.get("project_id") or ""), run_id)

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from novel_workflow.api.sse import (
    _event_stream,
    observe_run_events,
)
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_event import create_route_run_event
from novel_workflow.storage.route_run_read_model import initial_route_run_read_model
from novel_workflow.workflows.route_specs import SHORT_NOVEL_ROUTE
from tests.test_phase32_route_graph import _definition


NOW = "2026-08-23T12:00:00+08:00"


class _ConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


def _repository(tmp_path: Path):
    definition = _definition(SHORT_NOVEL_ROUTE)
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    repository.create(
        definition,
        state=initial_route_run_state(definition),
        read_model=initial_route_run_read_model(definition, updated_at=NOW),
    )
    return repository, definition


def _append(
    repository: Phase32RunRepository,
    definition,
    *,
    event_id: str,
    sequence: int,
    event_type: str,
    stage_id: str,
):
    return repository.append_event(
        create_route_run_event(
            definition,
            event_id=event_id,
            sequence=sequence,
            occurred_at=NOW,
            type=event_type,
            stage_id=stage_id,
        )
    )


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


@pytest.mark.anyio
async def test_phase32_sse_emits_route_aware_events_and_stops_at_export(
    tmp_path: Path,
) -> None:
    repository, definition = _repository(tmp_path)
    _append(
        repository,
        definition,
        event_id="event-1",
        sequence=1,
        event_type="stage.started",
        stage_id="brief",
    )
    _append(
        repository,
        definition,
        event_id="event-2",
        sequence=2,
        event_type="candidate.created",
        stage_id="brief",
    )
    _append(
        repository,
        definition,
        event_id="event-3",
        sequence=3,
        event_type="export.ready",
        stage_id="export",
    )

    chunks = await _collect(
        _event_stream(
            _ConnectedRequest(),
            Phase32EventProjection(repository),
            definition.run_id,
            after=0,
        )
    )

    assert len(chunks) == 3
    assert chunks[0].startswith("id: 1\ndata: ")
    assert '"creation_route_id": "short_novel"' in chunks[0]
    assert '"type": "export.ready"' in chunks[-1]
    assert chunks[-1].endswith("\n\n")


@pytest.mark.anyio
async def test_phase32_sse_reconnects_from_cursor_without_replaying_history(
    tmp_path: Path,
) -> None:
    repository, definition = _repository(tmp_path)
    _append(
        repository,
        definition,
        event_id="event-1",
        sequence=1,
        event_type="stage.started",
        stage_id="brief",
    )
    _append(
        repository,
        definition,
        event_id="event-2",
        sequence=2,
        event_type="export.ready",
        stage_id="export",
    )

    chunks = await _collect(
        _event_stream(
            _ConnectedRequest(),
            Phase32EventProjection(repository),
            definition.run_id,
            after=1,
        )
    )

    assert len(chunks) == 1
    assert chunks[0].startswith("id: 2\ndata: ")


def test_observe_phase32_run_events_returns_sse_response(tmp_path: Path) -> None:
    repository, definition = _repository(tmp_path)
    response = observe_run_events(
        _ConnectedRequest(),
        Phase32EventProjection(repository),
        definition.run_id,
        after=0,
    )

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"


@pytest.mark.anyio
async def test_phase32_sse_rejects_negative_cursor(tmp_path: Path) -> None:
    repository, definition = _repository(tmp_path)

    with pytest.raises(ValueError, match="cursor"):
        await _collect(
            _event_stream(
                _ConnectedRequest(),
                Phase32EventProjection(repository),
                definition.run_id,
                after=-1,
            )
        )


def test_phase32_sse_source_does_not_import_legacy_event_adapters() -> None:
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/api/sse.py"
    ).read_text(encoding="utf-8")
    assert "storage.event_projection" not in source
    assert "from novel_workflow.storage.event_projection" not in source

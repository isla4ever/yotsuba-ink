from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_event import create_route_run_event
from novel_workflow.storage.route_run_read_model import initial_route_run_read_model
from novel_workflow.workflows.route_specs import SHORT_NOVEL_ROUTE
from tests.test_phase32_route_graph import _definition


NOW = "2026-08-23T12:00:00+08:00"


def _repository(tmp_path: Path):
    definition = _definition(SHORT_NOVEL_ROUTE)
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    repository.create(
        definition,
        state=initial_route_run_state(definition),
        read_model=initial_route_run_read_model(definition, updated_at=NOW),
    )
    return repository, definition


def _append(repository, definition, *, event_id: str, sequence: int, event_type: str, stage_id: str):
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


def test_phase32_event_pages_keep_route_identity_and_cursor_contiguous(tmp_path: Path) -> None:
    repository, definition = _repository(tmp_path)
    _append(repository, definition, event_id="event-1", sequence=1, event_type="stage.started", stage_id="brief")
    _append(repository, definition, event_id="event-2", sequence=2, event_type="candidate.created", stage_id="brief")
    _append(repository, definition, event_id="event-3", sequence=3, event_type="decision.required", stage_id="brief")
    _append(repository, definition, event_id="event-4", sequence=4, event_type="decision.resolved", stage_id="brief")
    _append(repository, definition, event_id="event-5", sequence=5, event_type="export.ready", stage_id="export")

    projection = Phase32EventProjection(repository)
    first = projection.page(definition.run_id, limit=2)
    assert first.event_sequences == (1, 2)
    assert first.next_cursor == 2
    assert first.has_more is True
    assert first.terminal is False

    second = projection.page(definition.run_id, after=2, limit=2)
    assert second.event_sequences == (3, 4)
    assert second.terminal is False

    tail = projection.page(definition.run_id, after=4)
    assert tail.event_sequences == (5,)
    assert tail.terminal is True
    assert tail.creation_route_id == definition.creation_route_id
    assert tail.route_manifest_digest == definition.route_contract.route_manifest_digest
    assert projection.page(definition.run_id, after=5).terminal is True


def test_phase32_event_projection_rejects_invalid_cursor_and_page_size(tmp_path: Path) -> None:
    repository, definition = _repository(tmp_path)
    projection = Phase32EventProjection(repository)

    with pytest.raises(ValueError, match="cursor"):
        projection.page(definition.run_id, after=-1)
    with pytest.raises(ValueError, match="between 1 and 500"):
        projection.page(definition.run_id, limit=501)


def test_phase32_event_projection_source_has_no_retired_event_reader() -> None:
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/storage/phase32_event_projection.py"
    ).read_text(encoding="utf-8")
    assert "storage.event_projection" not in source
    assert "STAGE_ORDER" not in source
    assert "quality_mode" not in source

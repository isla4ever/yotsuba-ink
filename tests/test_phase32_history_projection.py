from __future__ import annotations

from pathlib import Path

from novel_workflow.storage.phase32_history_projection import Phase32HistoryProjection
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_read_model import PendingDecisionProjection
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.workflows.route_specs import SHORT_NOVEL_ROUTE
from tests.test_phase32_route_graph import _definition


NOW = "2026-08-23T12:00:00+08:00"


def test_phase32_history_uses_dynamic_manifest_and_route_identity(tmp_path: Path) -> None:
    definition = _definition(SHORT_NOVEL_ROUTE)
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    state = initial_route_run_state(definition)
    read_model = repository_read_model(definition)
    repository.create(definition, state=state, read_model=read_model)

    projection = Phase32HistoryProjection(repository)
    item = projection.latest(definition.project_id)

    assert item is not None
    assert item["creation_route_id"] == "short_novel"
    assert item["route_label"] == "短中篇小说"
    assert item["active_stage"] == {
        "stage_id": "brief",
        "label": "小说立项",
        "ordinal": 0,
        "total": 7,
    }
    assert item["progress"] == {"completed": 0, "total": 7, "ratio": 0}
    assert "quality_mode" not in item
    assert "stage_pointer" not in item


def test_phase32_history_projects_pending_decisions_without_fixed_stage_fields(
    tmp_path: Path,
) -> None:
    definition = _definition(SHORT_NOVEL_ROUTE)
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    state = initial_route_run_state(definition)
    read_model = repository_read_model(definition)
    repository.create(definition, state=state, read_model=read_model)

    running_status = dict(state.stage_status)
    running_status["brief"] = "awaiting_decision"
    next_state = state.model_copy(update={"status": "awaiting_decision", "stage_status": running_status})
    next_read_model = read_model.model_copy(
        update={
            "status": "awaiting_decision",
            "stage_status": running_status,
            "pending_decisions": (
                PendingDecisionProjection(
                    decision_id="decision:brief:1",
                    stage_id="brief",
                    artifact_ref="candidate:brief:1",
                    kind="stage_artifact_decision",
                ),
            ),
            "checkpoint_id": "checkpoint-1",
            "updated_at": "2026-08-23T12:01:00+08:00",
        }
    )
    repository.commit_projection(
        definition.run_id,
        state=next_state,
        read_model=next_read_model,
    )

    item = Phase32HistoryProjection(repository).latest(definition.project_id)
    assert item is not None
    assert item["can_branch"] is True
    assert item["pending_decisions"][0]["stage_id"] == "brief"
    assert item["checkpoint_id"] == "checkpoint-1"


def test_phase32_history_projection_source_has_no_retired_mode_or_stage_order() -> None:
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/storage/phase32_history_projection.py"
    ).read_text(encoding="utf-8")
    assert "quality_mode" not in source
    assert "STAGE_ORDER" not in source


def repository_read_model(definition):
    from novel_workflow.storage.route_run_read_model import initial_route_run_read_model

    return initial_route_run_read_model(definition, updated_at=NOW)

from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_run_fixture import (
    create_phase32_run_fixture,
)
from novel_workflow.workflows.phase32_scale import ScaleProfile
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)


OFFICIAL_ROUTES = (
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    LONG_NOVEL_ROUTE,
)


@pytest.mark.parametrize("route", OFFICIAL_ROUTES, ids=lambda route: route.route_id)
def test_create_phase32_run_fixture_freezes_route_scale_and_first_event(
    tmp_path: Path,
    route,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / route.route_id,
        route=route,
        run_id=f"fixture-{route.route_id}",
        project_id="project-phase32-fixture",
        creative_intent="验证三条路线都能在无 Provider 情况下建立可恢复 Run。",
    )

    profile = ScaleProfile.model_validate(fixture.definition.scale_profile.payload)
    assert fixture.definition.creation_route_id == route.route_id
    assert profile.route_id == route.route_id
    assert fixture.definition.scale_profile.contract_id == f"length.{route.route_id}.v1"
    assert fixture.state.status == "running"
    assert fixture.state.stage_status["brief"] == "running"
    assert fixture.read_model.status == "running"
    assert fixture.read_model.active_stage_id == "brief"
    assert fixture.first_event.sequence == 1
    assert fixture.first_event.type == "stage.started"
    assert fixture.first_event.stage_id == "brief"
    assert fixture.repository.events(fixture.definition.run_id) == [fixture.first_event]


def test_phase32_run_fixture_restarts_from_new_repository_instance(tmp_path: Path) -> None:
    root = tmp_path / "restartable-run"
    fixture = create_phase32_run_fixture(
        root,
        route=LONG_NOVEL_ROUTE,
        run_id="fixture-long-restart",
        project_id="project-phase32-restart",
        creative_intent="重启后 identity、scale、state、read model 和 event 必须一致。",
        target=180_000,
    )

    from novel_workflow.storage.phase32_run_repository import Phase32RunRepository

    restored = Phase32RunRepository(root).read(fixture.definition.run_id)
    assert restored.definition == fixture.definition
    assert restored.state == fixture.state
    assert restored.read_model == fixture.read_model
    assert Phase32RunRepository(root).events(fixture.definition.run_id) == [
        fixture.first_event
    ]


def test_phase32_run_fixture_rejects_unregistered_route_without_writing(tmp_path: Path) -> None:
    route = SHORT_NOVEL_ROUTE.model_construct(route_id="custom_route")
    root = tmp_path / "invalid"

    # The factory only accepts official route/review-policy pairs; no staging
    # directory should be created when the route cannot be resolved.
    with pytest.raises(ValueError, match="No official Phase 32 ReviewPolicy"):
        create_phase32_run_fixture(
            root,
            route=route,
            run_id="fixture-invalid-route",
            project_id="project-phase32-invalid",
            creative_intent="invalid",
        )
    assert not root.exists()


def test_phase32_run_fixture_source_has_no_provider_or_legacy_runtime_import() -> None:
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/orchestration/phase32_run_fixture.py"
    ).read_text(encoding="utf-8")
    assert "provider_gateway" not in source
    assert "NarrativeRuntime" not in source
    assert "narrative_scale" not in source
    assert "quality_mode" not in source

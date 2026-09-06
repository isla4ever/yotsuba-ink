from __future__ import annotations

import pytest

from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)


@pytest.mark.parametrize(
    ("route", "expected_stage_ids"),
    (
        (
            SCREENPLAY_SAMPLE_ROUTE,
            ("cast", "beat_board", "scene_deck", "script"),
        ),
        (
            SHORT_NOVEL_ROUTE,
            ("story_map", "cast", "section_plan", "text"),
        ),
        (
            LONG_NOVEL_ROUTE,
            ("book_architecture", "cast", "volumes", "rolling_detail", "text"),
        ),
    ),
    ids=("screenplay_sample", "short_novel", "long_novel"),
)
def test_each_creation_route_exposes_multi_turn_collaboration_at_its_text_stages(
    route,
    expected_stage_ids,
) -> None:
    manifest = RouteGraphCompiler().compile(route)

    assert "author_collaboration" in manifest.capabilities
    assert tuple(
        stage.stage_id for stage in manifest.stages if stage.collaboration_enabled
    ) == expected_stage_ids
    assert not any(
        stage.stage_id in {"brief", "cover", "export"}
        and stage.collaboration_enabled
        for stage in manifest.stages
    )

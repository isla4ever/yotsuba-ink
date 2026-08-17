from __future__ import annotations

from novel_workflow.runtime.graph.provider_contract_compiler import (
    schema_for_proposal,
    schema_for_stage,
    schema_with_frozen_context_bounds,
)
from novel_workflow.runtime.graph.provider_input_compiler import compile_provider_input
from novel_workflow.runtime.graph.provider_requests import ProposalGenerationRequest, StageGenerationRequest
from tests.phase27_bindings import provider_binding


def test_spine_schema_uses_the_frozen_turn_capacity() -> None:
    base = schema_for_stage("spine")
    effective = schema_with_frozen_context_bounds(
        "spine",
        base,
        {
            "material": {
                "scale_plan": {
                    "turn_target": 27,
                    "turn_capacity_range": [23, 34],
                }
            }
        },
    )

    assert base["properties"]["turns"]["minItems"] == 1
    assert effective["properties"]["turns"]["minItems"] == 27
    assert effective["properties"]["turns"]["maxItems"] == 27


def test_dynamic_proposal_and_unit_schemas_use_frozen_cardinality() -> None:
    role_schema, _ = schema_for_proposal("role_demand")
    role_effective = schema_with_frozen_context_bounds(
        "role_demand.proposal",
        role_schema,
        {
            "material": {
                "scale_plan": {
                    "cast_recommended_range": [3, 7],
                    "cast_hard_max": 11,
                }
            }
        },
    )
    assert role_effective["properties"]["proposals"]["minItems"] == 3
    assert role_effective["properties"]["proposals"]["maxItems"] == 11

    cast_effective = schema_with_frozen_context_bounds(
        "cast",
        schema_for_stage("cast"),
        {"material": {"subject_refs": [{"id": "subject-1"}, {"id": "subject-2"}]}},
    )
    assert cast_effective["properties"]["subjects"]["minItems"] == 2
    assert cast_effective["properties"]["subjects"]["maxItems"] == 2

    boundary_schema, _ = schema_for_proposal("volume_boundary")
    boundary_effective = schema_with_frozen_context_bounds(
        "volume_boundary.proposal",
        boundary_schema,
        {"material": {"scale_plan": {"volume_target": 3}}},
    )
    assert boundary_effective["properties"]["proposals"]["minItems"] == 3
    assert boundary_effective["properties"]["proposals"]["maxItems"] == 3

    layout_schema, _ = schema_for_proposal("detail_layout")
    layout_effective = schema_with_frozen_context_bounds(
        "detail_layout.proposal",
        layout_schema,
        {"material": {"chapter_slots": [{"slot": 1}, {"slot": 2}, {"slot": 3}]}},
    )
    chapters = layout_effective["$defs"]["DetailLayoutVolumeProposal"]["properties"]["chapters"]
    assert chapters["minItems"] == 3
    assert chapters["maxItems"] == 3


def test_detail_schema_uses_the_frozen_segment_and_scene_capacity() -> None:
    effective = schema_with_frozen_context_bounds(
        "detail",
        schema_for_stage("detail"),
        {
            "material": {
                "scale_projection": {
                    "chapter_target": 7,
                    "scenes_per_chapter_min": 2,
                    "scenes_per_chapter_max": 5,
                }
            }
        },
    )

    assert effective["properties"]["chapters"]["minItems"] == 7
    assert effective["properties"]["chapters"]["maxItems"] == 7
    scenes = effective["$defs"]["DetailSegmentChapter"]["properties"]["scenes"]
    assert scenes["minItems"] == 2
    assert scenes["maxItems"] == 5


def test_compiled_spine_input_exposes_dynamic_bounds_to_the_provider() -> None:
    compiled = compile_provider_input(
        StageGenerationRequest(
            operation_key="run:spine:1",
            run_id="run",
            stage_id="spine",
            attempt=1,
            binding=provider_binding("spine"),
            context={
                "target": "spine",
                "material": {
                    "scale_plan": {
                        "turn_target": 27,
                        "turn_capacity_range": [23, 34],
                        "chapter_target": 40,
                        "milestone_positions": {
                            "inciting": 1,
                            "commitment": 7,
                            "midpoint_reversal": 14,
                            "crisis": 19,
                            "climax": 26,
                            "aftermath": 27,
                        },
                    },
                    "story_brief": {},
                },
            },
        )
    )

    turns = compiled.output_contract.json_schema_contract["properties"]["turns"]
    assert turns["minItems"] == 27
    assert turns["maxItems"] == 27
    assert '"minItems": 27' in compiled.rendered_prompt
    assert "Return exactly 27" in compiled.rendered_prompt

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_compiler import (
    PHASE32_ARCHITECTURE_VERSION,
    RouteCompileError,
    RouteGraphCompiler,
    compile_official_routes,
)
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
    RouteStageSpec,
    official_creation_routes,
)


EXPECTED_ROUTE_STAGES = {
    "screenplay_sample": (
        "brief",
        "cast",
        "beat_board",
        "scene_deck",
        "script",
        "export",
    ),
    "short_novel": (
        "brief",
        "story_map",
        "cast",
        "section_plan",
        "text",
        "cover",
        "export",
    ),
    "long_novel": (
        "brief",
        "book_architecture",
        "cast",
        "volumes",
        "rolling_detail",
        "text",
        "cover",
        "export",
    ),
}

EXPECTED_ROUTE_DIGESTS = {
    "screenplay_sample": "230caf07ba1c3155977ae33b981a551f6c6c902d7890d9e0ff9ad8e29bfa1b70",
    "short_novel": "9ec42dc580b80723b134b208026c1dff094fbd9d35ea83542c33542b36a9ff25",
    "long_novel": "1c7776adf0abbab05efb1e97ae9995304577eaca76d70acae4317d1734a4ba01",
}


def _replace_stage(
    route: CreationRouteSpec,
    stage_id: str,
    **updates,
) -> CreationRouteSpec:
    stages = tuple(
        stage.model_copy(update=updates) if stage.stage_id == stage_id else stage
        for stage in route.stages
    )
    return route.model_copy(update={"stages": stages})


def _assert_compile_error(
    route: CreationRouteSpec,
    code: str,
    *,
    compiler: RouteGraphCompiler | None = None,
) -> None:
    with pytest.raises(RouteCompileError) as raised:
        (compiler or RouteGraphCompiler()).compile(route)
    assert raised.value.code == code


def test_official_routes_compile_to_one_phase32_manifest_shape() -> None:
    manifests = compile_official_routes()

    assert tuple(manifest.route_id for manifest in manifests) == (
        "screenplay_sample",
        "short_novel",
        "long_novel",
    )
    for manifest in manifests:
        assert manifest.architecture_version == PHASE32_ARCHITECTURE_VERSION
        assert manifest.route_revision == "r3"
        assert manifest.start_stage_id == "brief"
        assert manifest.terminal_stage_id == "export"
        assert tuple(stage.stage_id for stage in manifest.stages) == EXPECTED_ROUTE_STAGES[
            manifest.route_id
        ]
        assert tuple(stage.ordinal for stage in manifest.stages) == tuple(
            range(len(manifest.stages))
        )
        assert manifest.route_digest == EXPECTED_ROUTE_DIGESTS[manifest.route_id]
        cast = next(stage for stage in manifest.stages if stage.stage_id == "cast")
        assert cast.context_policy_ref.endswith(".cast.v2")


def test_each_official_route_has_exactly_one_deterministic_export() -> None:
    for manifest in compile_official_routes():
        exports = [stage for stage in manifest.stages if stage.stage_id == "export"]
        assert len(exports) == 1
        assert exports[0].provider_task_kind is None
        assert exports[0].unitization == "deterministic"
        assert exports[0].downstream_stage_ids == ()


def test_route_digest_and_order_do_not_depend_on_spec_list_order() -> None:
    shuffled = SHORT_NOVEL_ROUTE.model_copy(
        update={"stages": tuple(reversed(SHORT_NOVEL_ROUTE.stages))}
    )

    original = RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE)
    reordered = RouteGraphCompiler().compile(shuffled)

    assert reordered.route_digest == original.route_digest
    assert reordered.stages == original.stages


@pytest.mark.parametrize("retired_route_id", ["fast", "balanced", "deep"])
def test_retired_quality_modes_are_not_creation_route_ids(retired_route_id: str) -> None:
    payload = SCREENPLAY_SAMPLE_ROUTE.model_dump(mode="json")
    payload["route_id"] = retired_route_id

    with pytest.raises(ValidationError, match="route_id"):
        CreationRouteSpec.model_validate(payload)


def test_route_compiler_rejects_duplicate_stage_ids() -> None:
    duplicate = SHORT_NOVEL_ROUTE.model_copy(
        update={"stages": SHORT_NOVEL_ROUTE.stages + (SHORT_NOVEL_ROUTE.stages[0],)}
    )
    _assert_compile_error(duplicate, "duplicate_stage_id")


def test_route_compiler_rejects_duplicate_dependencies() -> None:
    invalid = _replace_stage(
        SHORT_NOVEL_ROUTE,
        "story_map",
        upstream_stage_ids=("brief", "brief"),
    )
    _assert_compile_error(invalid, "duplicate_stage_dependency")


def test_route_compiler_rejects_unknown_dependencies() -> None:
    invalid = _replace_stage(
        SHORT_NOVEL_ROUTE,
        "story_map",
        upstream_stage_ids=("missing",),
    )
    _assert_compile_error(invalid, "unknown_stage_dependency")


def test_route_compiler_rejects_multiple_start_stages() -> None:
    invalid = _replace_stage(
        SHORT_NOVEL_ROUTE,
        "story_map",
        upstream_stage_ids=(),
    )
    _assert_compile_error(invalid, "route_start_invalid")


def test_route_compiler_rejects_any_terminal_other_than_single_export() -> None:
    invalid = _replace_stage(
        SHORT_NOVEL_ROUTE,
        "export",
        upstream_stage_ids=("text",),
    )
    _assert_compile_error(invalid, "route_terminal_invalid")


def test_route_compiler_rejects_cycles() -> None:
    invalid = _replace_stage(
        SHORT_NOVEL_ROUTE,
        "story_map",
        upstream_stage_ids=("brief", "cast"),
    )
    _assert_compile_error(invalid, "route_cycle")


@pytest.mark.parametrize(
    ("stage_id", "updates"),
    [
        ("text", {"workbench_kind": "chapter_editor"}),
        ("text", {"artifact_kind": "chapter"}),
        ("text", {"provider_task_kind": "chapter"}),
        ("text", {"provider_task_kind": None}),
        ("export", {"provider_task_kind": "cover"}),
    ],
)
def test_route_compiler_rejects_incompatible_stage_bindings(
    stage_id: str,
    updates: dict[str, str | None],
) -> None:
    invalid = _replace_stage(SHORT_NOVEL_ROUTE, stage_id, **updates)
    _assert_compile_error(invalid, "stage_binding_invalid")


def test_route_compiler_rejects_new_cast_without_epistemic_context() -> None:
    invalid = _replace_stage(
        SCREENPLAY_SAMPLE_ROUTE,
        "cast",
        context_policy_ref="context.screenplay.cast.v1",
    )

    _assert_compile_error(invalid, "cast_context_policy_invalid")


def test_route_compiler_rejects_unknown_review_policy() -> None:
    invalid = SHORT_NOVEL_ROUTE.model_copy(
        update={"default_review_policy_ref": "review.unknown.default"}
    )
    _assert_compile_error(invalid, "review_policy_unknown")


def test_route_compiler_rejects_review_policy_from_another_route() -> None:
    invalid = SHORT_NOVEL_ROUTE.model_copy(
        update={"default_review_policy_ref": "review.long_novel.default"}
    )
    _assert_compile_error(invalid, "review_policy_route_mismatch")


def test_route_compiler_rejects_review_policy_unknown_stage_refs() -> None:
    policy = ReviewPolicy(
        policy_id="review.short_novel.test",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        mandatory_decision_stages=("ghost_stage",),
    )
    invalid = SHORT_NOVEL_ROUTE.model_copy(
        update={"default_review_policy_ref": policy.policy_id}
    )
    _assert_compile_error(
        invalid,
        "review_policy_stage_unknown",
        compiler=RouteGraphCompiler({policy.policy_id: policy}),
    )


def test_review_policy_rejects_conflicting_stage_controls() -> None:
    with pytest.raises(ValidationError, match="both automatic and mandatory"):
        ReviewPolicy(
            policy_id="review.short_novel.conflict",
            revision="r1",
            route_id="short_novel",
            checkpoint_policy="milestone",
            warning_policy="continue_and_surface",
            auto_continue_stages=("text",),
            mandatory_decision_stages=("text",),
        )


def test_review_policy_rejects_redraft_on_deterministic_export() -> None:
    policy = ReviewPolicy(
        policy_id="review.short_novel.export_redraft",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        directed_redraft_limit_by_stage={"export": 1},
        mandatory_decision_stages=("brief",),
    )
    invalid = SHORT_NOVEL_ROUTE.model_copy(
        update={"default_review_policy_ref": policy.policy_id}
    )
    _assert_compile_error(
        invalid,
        "review_policy_redraft_invalid",
        compiler=RouteGraphCompiler({policy.policy_id: policy}),
    )


def test_route_kernel_has_no_retired_execution_contract_imports() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "novel_workflow" / "workflows"
    source = "\n".join(
        (source_root / name).read_text(encoding="utf-8")
        for name in ("review_policy.py", "route_specs.py", "route_compiler.py")
    )

    for retired_term in (
        "QualityMode",
        "STAGE_ORDER",
        "PHASE27_EDGES",
        '"fast"',
        '"balanced"',
        '"deep"',
    ):
        assert retired_term not in source


def test_official_route_objects_are_the_registry_values() -> None:
    assert official_creation_routes() == (
        SCREENPLAY_SAMPLE_ROUTE,
        SHORT_NOVEL_ROUTE,
        LONG_NOVEL_ROUTE,
    )


def test_stage_specs_forbid_unknown_fields() -> None:
    payload = SHORT_NOVEL_ROUTE.stages[0].model_dump(mode="json")
    payload["quality_mode"] = "retired"

    with pytest.raises(ValidationError, match="quality_mode"):
        RouteStageSpec.model_validate(payload)

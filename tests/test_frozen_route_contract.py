from __future__ import annotations

import pytest
from pydantic import ValidationError

from novel_workflow.workflows.frozen_route_contract import (
    FrozenRouteContract,
    canonical_digest,
    freeze_route_contract,
)
from novel_workflow.workflows.review_policy import (
    LONG_NOVEL_REVIEW_POLICY,
    ReviewPolicy,
    SCREENPLAY_REVIEW_POLICY,
    SHORT_NOVEL_REVIEW_POLICY,
)
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)


OFFICIAL_CASES = (
    (SCREENPLAY_SAMPLE_ROUTE, SCREENPLAY_REVIEW_POLICY),
    (SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY),
    (LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY),
)


@pytest.mark.parametrize(
    ("route", "policy"),
    OFFICIAL_CASES,
    ids=lambda value: getattr(value, "route_id", getattr(value, "policy_id", "case")),
)
def test_official_routes_freeze_and_round_trip(route, policy) -> None:
    manifest = RouteGraphCompiler().compile(route)

    frozen = freeze_route_contract(manifest, policy)
    restored = FrozenRouteContract.model_validate_json(frozen.model_dump_json())

    assert restored == frozen
    assert restored.creation_route_id == route.route_id
    assert restored.route_revision == route.revision
    assert restored.stage_ids == tuple(stage.stage_id for stage in manifest.stages)
    assert "export" not in restored.provider_stage_ids
    assert restored.contract_digest == canonical_digest(
        restored.model_dump(mode="json", exclude={"contract_digest"})
    )


@pytest.mark.parametrize(
    "policy",
    (
        SCREENPLAY_REVIEW_POLICY,
        SHORT_NOVEL_REVIEW_POLICY,
        LONG_NOVEL_REVIEW_POLICY,
    ),
    ids=lambda policy: policy.route_id,
)
def test_official_routes_gate_cast_before_subject_refs_become_immutable(policy) -> None:
    assert policy.revision == "r2"
    assert "cast" in policy.mandatory_decision_stages
    assert "cast" not in policy.auto_continue_stages
    assert policy.directed_redraft_limit_by_stage["cast"] == 1


def test_custom_review_policy_can_be_frozen_without_becoming_a_new_route() -> None:
    manifest = RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE)
    policy = ReviewPolicy(
        policy_id="review.short_novel.author_sample",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="every_stage",
        warning_policy="continue_and_surface",
        contract_correction_limit=0,
        directed_redraft_limit_by_stage={"text": 2},
        mandatory_decision_stages=("brief", "text"),
    )

    frozen = freeze_route_contract(manifest, policy)

    assert frozen.creation_route_id == "short_novel"
    assert frozen.review_policy.policy_id == policy.policy_id
    assert frozen.route_digest == manifest.route_digest


def test_freeze_rejects_review_policy_from_another_route() -> None:
    manifest = RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE)

    with pytest.raises(ValueError, match="different creation route"):
        freeze_route_contract(manifest, LONG_NOVEL_REVIEW_POLICY)


def test_freeze_rejects_review_policy_refs_outside_route() -> None:
    manifest = RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE)
    policy = ReviewPolicy(
        policy_id="review.short_novel.invalid_stage",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="pause_at_milestone",
        mandatory_decision_stages=("scene_deck",),
    )

    with pytest.raises(ValueError, match="outside the compiled route"):
        freeze_route_contract(manifest, policy)


def test_freeze_rejects_automatic_deterministic_export() -> None:
    manifest = RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE)
    policy = ReviewPolicy(
        policy_id="review.short_novel.auto_export",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        auto_continue_stages=("export",),
        mandatory_decision_stages=("brief",),
    )

    with pytest.raises(ValueError, match="automatic generation"):
        freeze_route_contract(manifest, policy)


def test_freeze_rejects_redraft_for_deterministic_export() -> None:
    manifest = RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE)
    policy = ReviewPolicy(
        policy_id="review.short_novel.redraft_export",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        directed_redraft_limit_by_stage={"export": 1},
        mandatory_decision_stages=("brief",),
    )

    with pytest.raises(ValueError, match="requires a Provider stage"):
        freeze_route_contract(manifest, policy)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("creation_route_id", "long_novel", "identity"),
        ("route_revision", "r99", "identity"),
        ("route_digest", "f" * 64, "identity"),
        ("route_manifest_digest", "f" * 64, "manifest digest"),
        ("review_policy_digest", "f" * 64, "ReviewPolicy digest"),
        ("contract_digest", "f" * 64, "contract digest"),
    ],
)
def test_frozen_route_contract_rejects_tampered_top_level_fields(
    field: str,
    replacement: str,
    message: str,
) -> None:
    frozen = freeze_route_contract(
        RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE),
        SHORT_NOVEL_REVIEW_POLICY,
    )
    payload = frozen.model_dump(mode="json")
    payload[field] = replacement

    with pytest.raises(ValidationError, match=message):
        FrozenRouteContract.model_validate(payload)


def test_frozen_route_contract_rejects_tampered_manifest_payload() -> None:
    frozen = freeze_route_contract(
        RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE),
        SHORT_NOVEL_REVIEW_POLICY,
    )
    payload = frozen.model_dump(mode="json")
    payload["route_manifest"]["stages"][0]["label"] = "被篡改的阶段"

    with pytest.raises(ValidationError, match="manifest digest"):
        FrozenRouteContract.model_validate(payload)


def test_frozen_route_contract_rejects_tampered_review_policy_payload() -> None:
    frozen = freeze_route_contract(
        RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE),
        SHORT_NOVEL_REVIEW_POLICY,
    )
    payload = frozen.model_dump(mode="json")
    payload["review_policy"]["warning_policy"] = "continue_and_surface"

    with pytest.raises(ValidationError, match="ReviewPolicy digest"):
        FrozenRouteContract.model_validate(payload)


def test_frozen_route_contract_rejects_retired_quality_mode_field() -> None:
    frozen = freeze_route_contract(
        RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE),
        SHORT_NOVEL_REVIEW_POLICY,
    )
    payload = frozen.model_dump(mode="json")
    payload["quality_mode"] = "balanced"

    with pytest.raises(ValidationError, match="quality_mode"):
        FrozenRouteContract.model_validate(payload)


def test_frozen_route_contract_checks_stage_membership() -> None:
    frozen = freeze_route_contract(
        RouteGraphCompiler().compile(SCREENPLAY_SAMPLE_ROUTE),
        SCREENPLAY_REVIEW_POLICY,
    )

    frozen.require_stage("scene_deck")
    with pytest.raises(ValueError, match="not part of route screenplay_sample"):
        frozen.require_stage("volumes")

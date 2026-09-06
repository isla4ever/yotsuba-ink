from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novel_workflow.api.bootstrap import init_app_state
from novel_workflow.api.routes.runs import retired_router, router
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingService,
)
from novel_workflow.orchestration.phase32_continuity_acceptance import (
    Phase32ContinuityBudgetLimits,
)
from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    admit_phase32_provider_readiness,
)
from novel_workflow.orchestration.phase32_run_preflight import Phase32PreflightError
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_artifact_draft_store import Phase32ArtifactDraftStore
from novel_workflow.storage.phase32_decision_receipt_store import (
    Phase32DecisionReceiptStore,
)
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_history_projection import Phase32HistoryProjection
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.usage.phase32_live_candidate_preflight_contract import (
    Phase32PricingAttestationCommand,
)
from novel_workflow.workflows.definition_schemas import ProviderProfile
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)
from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.templates import (
    DEEPSEEK_PRICING_SOURCE_URL,
    DEEPSEEK_PRICING_VERIFIED_AT,
)
from tests.test_phase32_driver import _FixtureGateway


def _app(
    tmp_path: Path,
    route: CreationRouteSpec = SHORT_NOVEL_ROUTE,
    review_policy: ReviewPolicy | None = None,
    workflow_id: str | None = None,
) -> tuple[TestClient, str]:
    route_slug = route.route_id.replace("_", "-")
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=route,
        run_id=f"api-{route_slug}",
        project_id=f"project-api-{route_slug}",
        creative_intent="验证 Phase 32 HTTP start/resume adapter。",
        target=150_000 if route.route_id == "long_novel" else None,
        workflow_id=workflow_id,
        review_policy=review_policy,
    )
    gateway = _FixtureGateway({})
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    exports = ExportStore(tmp_path / "exports")
    drafts = Phase32ArtifactDraftStore(tmp_path / "artifact-drafts")
    editing = Phase32ArtifactEditingService(fixture.repository, artifacts, drafts)
    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: Phase32RouteDriver(
            artifacts,
            gateway,
            exports=exports,
        ),
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
        artifact_editing=editing,
    )
    app = FastAPI()
    app.include_router(router)
    app.include_router(retired_router)
    app.state.phase32_execution_service = service
    app.state.phase32_run_repository = fixture.repository
    app.state.phase32_event_projection = Phase32EventProjection(fixture.repository)
    app.state.phase32_history_projection = Phase32HistoryProjection(fixture.repository)
    app.state.phase32_artifact_editing = editing
    app.state.phase32_exports = exports
    return TestClient(app), fixture.definition.run_id


class _ForbiddenProviderGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, *_args, **_kwargs):
        self.calls.append("text")
        raise AssertionError("Provider must remain unreachable behind the API gate")

    async def generate_writeback(self, *_args, **_kwargs):
        self.calls.append("writeback")
        raise AssertionError("Provider must remain unreachable behind the API gate")

    async def generate_cover_image(self, *_args, **_kwargs):
        self.calls.append("image")
        raise AssertionError("Image Provider must remain unreachable")


class _RejectingPreflight:
    def validate(self, *_args, **_kwargs):
        raise Phase32PreflightError(
            "state_projection_invalid",
            "private-secret and https://provider.invalid must not escape",
        )


def _continuity_api(
    tmp_path: Path,
) -> tuple[TestClient, object, _ForbiddenProviderGateway, list[str]]:
    app = FastAPI()
    init_app_state(app, data_dir=tmp_path / "app-data")
    app.include_router(router)
    authority = app.state.phase32_continuity_acceptance
    observed_at = datetime.fromisoformat(DEEPSEEK_PRICING_VERIFIED_AT) + timedelta(
        minutes=5
    )
    authority.clock = lambda: observed_at
    app.state.phase32_live_candidate_preflight.clock = lambda: observed_at
    app.state.provider_secret_store.set_api_key(
        "provider-deepseek-text",
        "private-secret-must-not-escape",
    )
    profile = ProviderProfile.model_validate(
        app.state.provider_store.read("provider-deepseek-text")
    )
    pricing = profile.model_pricing["deepseek-v4-pro"]
    app.state.phase32_live_candidate_preflight.attest_pricing(
        Phase32PricingAttestationCommand(
            idempotency_key="execution-api-offline-pricing-attestation",
            expected_profile_digest=canonical_digest(profile.model_dump(mode="json")),
            input_usd_per_million_tokens=(
                pricing.input_usd_per_million_tokens or 1.32
            ),
            output_usd_per_million_tokens=(
                pricing.output_usd_per_million_tokens or 3.96
            ),
            source_url=DEEPSEEK_PRICING_SOURCE_URL,
            verified_at=DEEPSEEK_PRICING_VERIFIED_AT,
            estimate_basis_note="Offline API gate conservative pricing.",
            attested_by="offline-execution-api-test",
        )
    )
    gateway = _ForbiddenProviderGateway()
    app.state.phase32_provider_gateway = gateway
    app.state.phase32_writeback.gateway = gateway
    driver_creations: list[str] = []
    original_driver_factory = app.state.phase32_execution_service.driver_factory

    def tracked_driver_factory(definition):
        driver_creations.append(definition.run_id)
        return original_driver_factory(definition)

    app.state.phase32_execution_service.driver_factory = tracked_driver_factory
    return (
        TestClient(app, raise_server_exceptions=False),
        authority,
        gateway,
        driver_creations,
    )


def _continuity_request(key: str) -> CreationPreparationRequest:
    return CreationPreparationRequest.model_validate(
        {
            "selection": {
                "intent": {
                    "creative_intent": "十二封未来来信必须沿同一证据链完成验收。",
                    "creation_language": "zh-CN",
                    "creation_kind": "novel",
                    "novel_length_class": "long_novel",
                    "requested_target": 150_000,
                },
                "mode": "existing",
                "workflow_id": "official.long_novel",
            },
            "idempotency_key": key,
        }
    )


def _continuity_budget() -> Phase32ContinuityBudgetLimits:
    return Phase32ContinuityBudgetLimits(
        max_cost_usd=20,
        max_operations=100,
        max_total_tokens=2_000_000,
    )


def _assert_no_provider_side_effects(
    client: TestClient,
    run_id: str,
    gateway: _ForbiddenProviderGateway,
    driver_creations: list[str],
) -> None:
    assert driver_creations == []
    assert gateway.calls == []
    assert client.app.state.phase32_provider_inputs.list(run_id) == []
    assert client.app.state.phase32_provider_operations.list(run_id) == []


@pytest.mark.parametrize(
    "route",
    (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE),
    ids=lambda route: route.route_id,
)
def test_cast_draft_api_opens_for_all_routes_and_preserves_subject_identity(
    tmp_path: Path,
    route: CreationRouteSpec,
) -> None:
    policy = _cast_review_policy(route)
    client, run_id = _app(tmp_path / route.route_id, route, policy)
    result = client.post(f"/api/runs/{run_id}/start").json()
    decision = result["decision"]
    while decision["stage_id"] != "cast":
        result = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        ).json()
        decision = result["decision"]

    current_response = client.get(
        f"/api/runs/{run_id}/stages/cast/artifacts/current"
    )
    assert current_response.status_code == 200
    current = current_response.json()
    assert current["editable"] is True
    assert current["artifact_kind"] == "character_bible"

    payload = dict(current["payload"])
    characters = [dict(character) for character in payload["characters"]]
    original_refs = [character["subject_ref"] for character in characters]
    characters[0]["desire"] = "在公开听证前找到可独立核验的原始签名链。"
    characters[0]["constraints"] = [
        "不能公开未经核验的证据。",
        "必须保护愿意作证的档案保管者。",
    ]
    payload["characters"] = characters
    saved_response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert saved_response.status_code == 200
    draft = saved_response.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    committed = client.get(
        f"/api/runs/{run_id}/stages/cast/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert committed["payload"]["characters"][0]["desire"] == characters[0]["desire"]
    assert [
        character["subject_ref"] for character in committed["payload"]["characters"]
    ] == original_refs


def test_cast_draft_api_rejects_added_or_replaced_subject_refs(tmp_path: Path) -> None:
    route = SHORT_NOVEL_ROUTE
    client, run_id = _app(tmp_path, route, _cast_review_policy(route))
    result = client.post(f"/api/runs/{run_id}/start").json()
    decision = result["decision"]
    while decision["stage_id"] != "cast":
        result = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        ).json()
        decision = result["decision"]
    current = client.get(
        f"/api/runs/{run_id}/stages/cast/artifacts/current"
    ).json()
    payload = dict(current["payload"])
    characters = [dict(character) for character in payload["characters"]]
    characters[0]["subject_ref"] = "replacement-subject"
    payload["characters"] = characters

    response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert response.status_code == 409


def _cast_review_policy(route: CreationRouteSpec) -> ReviewPolicy:
    cast_index = next(
        index for index, stage in enumerate(route.stages) if stage.stage_id == "cast"
    )
    mandatory_stages = tuple(stage.stage_id for stage in route.stages[: cast_index + 1])
    if route.route_id in {"short_novel", "long_novel"}:
        mandatory_stages = (*mandatory_stages, "cover")
    return ReviewPolicy(
        policy_id=f"review.{route.route_id}.cast_workbench",
        revision="r1",
        route_id=route.route_id,
        checkpoint_policy="every_stage",
        warning_policy="pause_at_milestone",
        directed_redraft_limit_by_stage={"cast": 1},
        mandatory_decision_stages=mandatory_stages,
    )


def _section_plan_review_policy() -> ReviewPolicy:
    return ReviewPolicy(
        policy_id="review.short_novel.section_plan_workbench",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="every_stage",
        warning_policy="pause_at_milestone",
        directed_redraft_limit_by_stage={"section_plan": 1},
        mandatory_decision_stages=(
            "brief",
            "story_map",
            "section_plan",
            "text",
            "cover",
        ),
    )


def _beat_board_review_policy() -> ReviewPolicy:
    return ReviewPolicy(
        policy_id="review.screenplay_sample.beat_board_workbench",
        revision="r1",
        route_id="screenplay_sample",
        checkpoint_policy="every_stage",
        warning_policy="pause_at_milestone",
        directed_redraft_limit_by_stage={"beat_board": 1},
        mandatory_decision_stages=("brief", "cast", "beat_board", "scene_deck"),
    )


def _scene_deck_review_policy() -> ReviewPolicy:
    return ReviewPolicy(
        policy_id="review.screenplay_sample.scene_deck_workbench",
        revision="r1",
        route_id="screenplay_sample",
        checkpoint_policy="every_stage",
        warning_policy="pause_at_milestone",
        directed_redraft_limit_by_stage={"scene_deck": 1},
        mandatory_decision_stages=(
            "brief",
            "cast",
            "beat_board",
            "scene_deck",
            "script",
        ),
    )


def test_phase32_start_and_resume_routes_return_read_model_and_decision(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path)
    started = client.post(f"/api/runs/{run_id}/start")
    assert started.status_code == 200
    body = started.json()
    assert body["run"]["read_model"]["status"] == "awaiting_decision"
    decision = body["decision"]
    assert decision["stage_id"] == "brief"

    resumed = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
        },
    )
    assert resumed.status_code == 200
    assert resumed.json()["run"]["read_model"]["status"] in {
        "awaiting_decision",
        "running",
        "completed",
    }

    repeated = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["reused"] is True


def test_canonical_short_route_exposes_image_deferred_and_blocks_export(
    tmp_path: Path,
) -> None:
    policy = ReviewPolicy(
        policy_id="review.short_novel.api-image-deferred",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        auto_continue_stages=(
            "story_map",
            "cast",
            "section_plan",
            "text",
            "cover",
        ),
        mandatory_decision_stages=("brief",),
    )
    client, run_id = _app(
        tmp_path,
        SHORT_NOVEL_ROUTE,
        policy,
        workflow_id="official.short_novel",
    )
    result = client.post(f"/api/runs/{run_id}/start").json()
    while result.get("decision"):
        decision = result["decision"]
        result = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        ).json()

    run = result["run"]
    assert run["read_model"]["status"] == "image_deferred"
    assert run["read_model"]["active_stage_id"] == "cover"
    assert run["summary"]["export_ready"] is False
    exports = client.get(f"/api/runs/{run_id}/exports")
    assert exports.status_code == 409
    detail = exports.json()["detail"]
    assert detail["code"] == "image_deferred"
    assert detail["artifact_type"] == "book_delivery"
    assert detail["dependency_status"] == "deferred"
    assert detail["deferred_reason"] == "image_acceptance_not_in_current_wave"
    assert detail["source_artifact_refs"]


def test_phase32_execution_routes_map_unknown_and_unconfigured_runs(
    tmp_path: Path,
) -> None:
    client, _ = _app(tmp_path)
    missing = client.post("/api/runs/missing/start")
    assert missing.status_code == 404

    unconfigured = FastAPI()
    unconfigured.include_router(router)
    with TestClient(unconfigured) as empty_client:
        response = empty_client.post("/api/runs/any/start")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "phase32_execution_unavailable"


def test_continuity_start_maps_expired_readiness_to_structured_409(
    tmp_path: Path,
) -> None:
    client, authority, gateway, driver_creations = _continuity_api(tmp_path)
    prepared = authority.prepare(
        _continuity_request("continuity-api-expired-readiness"),
        budget=_continuity_budget(),
    )
    observed_at = datetime.fromisoformat(prepared.readiness.observed_at)
    authority.clock = lambda: observed_at + timedelta(seconds=900)

    response = client.post(f"/api/runs/{prepared.definition.run_id}/start")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "phase32_provider_readiness_admission_failed",
        "message": "Continuity acceptance Provider readiness is not current",
        "retryable": True,
        "retry_condition": "after_provider_readiness_refresh",
        "issue_codes": ["readiness_admission_expired"],
    }
    assert "private-secret-must-not-escape" not in response.text
    assert "provider.invalid" not in response.text
    _assert_no_provider_side_effects(
        client,
        prepared.definition.run_id,
        gateway,
        driver_creations,
    )


def test_continuity_start_maps_missing_budget_authority_to_structured_409(
    tmp_path: Path,
) -> None:
    client, authority, gateway, driver_creations = _continuity_api(tmp_path)
    prepared = authority.creation.prepare_continuity_acceptance(
        _continuity_request("continuity-api-missing-budget")
    )
    observed_at = authority.clock()
    admit_phase32_provider_readiness(
        prepared.definition,
        store=authority.readiness,
        policy=authority.readiness_policy,
        secret_resolver=authority.secret_resolver,
        now=observed_at,
    )

    response = client.post(f"/api/runs/{prepared.definition.run_id}/start")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "phase32_continuity_admission_failed",
        "message": "Continuity acceptance authority is not available for this Run",
        "retryable": True,
        "retry_condition": "after_continuity_authority_restore",
    }
    assert "private-secret-must-not-escape" not in response.text
    assert "provider.invalid" not in response.text
    _assert_no_provider_side_effects(
        client,
        prepared.definition.run_id,
        gateway,
        driver_creations,
    )


def test_continuity_start_maps_missing_live_authorization_to_structured_409(
    tmp_path: Path,
) -> None:
    client, authority, gateway, driver_creations = _continuity_api(tmp_path)
    prepared = authority.prepare(
        _continuity_request("continuity-api-missing-live-authorization"),
        budget=_continuity_budget(),
    )

    response = client.post(f"/api/runs/{prepared.definition.run_id}/start")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "phase32_live_candidate_authorization_failed",
        "message": "Live candidate authorization is not current",
        "retryable": True,
        "retry_condition": "after_live_candidate_reauthorization",
    }
    _assert_no_provider_side_effects(
        client,
        prepared.definition.run_id,
        gateway,
        driver_creations,
    )


def test_continuity_start_maps_missing_execution_admission_to_structured_409(
    tmp_path: Path,
) -> None:
    client, authority, gateway, driver_creations = _continuity_api(tmp_path)
    prepared = authority.prepare(
        _continuity_request("continuity-api-missing-execution-admission"),
        budget=_continuity_budget(),
    )
    client.app.state.phase32_execution_service.run_admission = None

    response = client.post(f"/api/runs/{prepared.definition.run_id}/start")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "phase32_run_admission_required",
        "message": "Continuity acceptance execution admission is not configured",
        "retryable": False,
        "retry_condition": "continuity_admission_service_required",
    }
    assert "private-secret-must-not-escape" not in response.text
    assert "provider.invalid" not in response.text
    _assert_no_provider_side_effects(
        client,
        prepared.definition.run_id,
        gateway,
        driver_creations,
    )


def test_failure_recovery_endpoint_rejects_a_nonfailed_run(tmp_path: Path) -> None:
    client, run_id = _app(tmp_path)

    response = client.post(
        f"/api/runs/{run_id}/recoveries",
        json={
            "recovery_id": "not-failed-recovery",
            "domain_revision": 0,
            "direction": "输出完整合同。",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "phase32_execution_conflict",
        "message": "Failure recovery requires a terminal failed Run",
    }


def test_continuity_start_maps_malformed_budget_authority_to_structured_409(
    tmp_path: Path,
) -> None:
    client, authority, gateway, driver_creations = _continuity_api(tmp_path)
    prepared = authority.prepare(
        _continuity_request("continuity-api-malformed-budget"),
        budget=_continuity_budget(),
    )
    authorization_path = (
        authority.budgets.root
        / prepared.definition.run_id
        / "authorization.json"
    )
    authorization_path.write_text(
        '{"secret":"private-secret","base_url":"https://provider.invalid"}',
        encoding="utf-8",
    )

    response = client.post(f"/api/runs/{prepared.definition.run_id}/start")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "phase32_run_budget_store_invalid",
        "message": "Continuity acceptance budget authority is inconsistent",
        "retryable": False,
        "retry_condition": "budget_authority_repair_required",
    }
    assert "private-secret" not in response.text
    assert "provider.invalid" not in response.text
    _assert_no_provider_side_effects(
        client,
        prepared.definition.run_id,
        gateway,
        driver_creations,
    )


def test_continuity_start_maps_preflight_rejection_to_nonretryable_422(
    tmp_path: Path,
) -> None:
    client, authority, gateway, driver_creations = _continuity_api(tmp_path)
    prepared = authority.prepare(
        _continuity_request("continuity-api-preflight-rejected"),
        budget=_continuity_budget(),
    )
    client.app.state.phase32_live_candidate_authorization.authorize_run(
        prepared.definition,
        readiness=prepared.readiness,
        budget=prepared.budget,
    )
    client.app.state.phase32_execution_service.preflight = _RejectingPreflight()

    response = client.post(f"/api/runs/{prepared.definition.run_id}/start")

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "state_projection_invalid",
        "message": "Phase 32 Run preflight rejected the current definition or projection",
        "retryable": False,
        "retry_condition": "run_definition_or_projection_repair_required",
    }
    assert "private-secret" not in response.text
    assert "provider.invalid" not in response.text
    _assert_no_provider_side_effects(
        client,
        prepared.definition.run_id,
        gateway,
        driver_creations,
    )


def test_brief_draft_api_commits_edited_candidate_and_freezes_receipt_identity(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path)
    started = client.post(f"/api/runs/{run_id}/start").json()
    decision = started["decision"]

    current_response = client.get(f"/api/runs/{run_id}/stages/brief/artifacts/current")
    assert current_response.status_code == 200
    current = current_response.json()
    assert current["editable"] is True
    assert current["pending_decision"]["domain_revision"] == decision["domain_revision"]
    assert current["pending_decision"]["allowed_actions"] == decision["allowed_actions"]

    payload = dict(current["payload"])
    payload["premise"] = "一份被删改的证词迫使主角在封存前重建事实链。"
    saved_response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert saved_response.status_code == 200
    draft = saved_response.json()["draft"]
    assert draft["source_artifact_ref"] == current["artifact_ref"]

    latest = client.get(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}"
    )
    assert latest.status_code == 200
    assert latest.json()["draft"]["draft_ref"] == draft["draft_ref"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    committed_ref = accepted.json()["run"]["read_model"]["artifact_refs"]["brief"][
        "artifact_ref"
    ]
    assert committed_ref != current["artifact_ref"]

    committed = client.get(f"/api/runs/{run_id}/stages/brief/artifacts/current")
    assert committed.status_code == 200
    assert committed.json()["payload"]["premise"] == payload["premise"]
    assert committed.json()["editable"] is False

    receipt = client.app.state.phase32_execution_service.decisions.read(
        run_id,
        f"decision:{decision['decision_id']}",
    )
    assert receipt.command["draft_ref"] == draft["draft_ref"]
    assert receipt.command["source_artifact_ref"] == current["artifact_ref"]
    assert receipt.command["candidate_ref"].startswith("p32-brief-candidate-")


def test_brief_draft_api_rejects_stale_source_and_frozen_scale_drift(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path)
    decision = client.post(f"/api/runs/{run_id}/start").json()["decision"]
    current = client.get(
        f"/api/runs/{run_id}/stages/brief/artifacts/current"
    ).json()
    endpoint = f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}"

    stale = client.put(
        endpoint,
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": "p32-brief-candidate-" + "0" * 32,
            "payload": current["payload"],
        },
    )
    assert stale.status_code == 409

    drifted = dict(current["payload"])
    drifted["target_characters"] += 1
    scale = client.put(
        endpoint,
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": drifted,
        },
    )
    assert scale.status_code == 422


def test_story_map_draft_api_commits_edited_anchor_and_advances_to_cast(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path)
    brief = client.post(f"/api/runs/{run_id}/start").json()["decision"]
    story_map_result = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": brief["decision_id"],
            "action": "accept",
            "domain_revision": brief["domain_revision"],
        },
    ).json()
    decision = story_map_result["decision"]
    assert decision["stage_id"] == "story_map"

    current_response = client.get(
        f"/api/runs/{run_id}/stages/story_map/artifacts/current"
    )
    assert current_response.status_code == 200
    current = current_response.json()
    assert current["editable"] is True
    assert current["artifact_kind"] == "story_map"

    payload = dict(current["payload"])
    anchors = [dict(anchor) for anchor in payload["anchors"]]
    anchors[0]["pressure"] = "档案将在午夜永久封存，主角只剩一次公开核验机会。"
    anchors[0]["promise_refs"] = ["promise-signature-chain"]
    payload["anchors"] = anchors
    payload["open_questions"] = ["谁能证明封存命令并非正常流程？"]

    saved_response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert saved_response.status_code == 200
    draft = saved_response.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["decision"]["stage_id"] == "cast"
    assert "regenerate" in body["decision"]["allowed_actions"]
    assert body["run"]["read_model"]["stage_status"]["cast"] == "awaiting_decision"
    assert body["run"]["read_model"]["stage_status"]["section_plan"] == "locked"

    committed = client.get(
        f"/api/runs/{run_id}/stages/story_map/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert committed["payload"]["anchors"][0]["pressure"] == anchors[0]["pressure"]
    assert committed["payload"]["open_questions"] == payload["open_questions"]
    assert committed["artifact_ref"] != current["artifact_ref"]

    receipt = client.app.state.phase32_execution_service.decisions.read(
        run_id,
        f"decision:{decision['decision_id']}",
    )
    assert receipt.command["draft_ref"] == draft["draft_ref"]
    assert receipt.command["source_artifact_ref"] == current["artifact_ref"]
    assert receipt.command["candidate_ref"].startswith(
        "p32-story_map-candidate-"
    )


def test_section_plan_draft_api_commits_edited_unit_and_advances_to_text(
    tmp_path: Path,
) -> None:
    client, run_id = _app(
        tmp_path,
        SHORT_NOVEL_ROUTE,
        _section_plan_review_policy(),
    )
    decision = _advance_to_section_plan(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/section_plan/artifacts/current"
    ).json()

    assert current["editable"] is True
    assert current["artifact_kind"] == "section_plan"
    units = [dict(unit) for unit in current["payload"]["units"]]
    units[0].update(
        {
            "title": "封存前的签名",
            "dramatic_job": "迫使主角在闭馆前获得第一条可独立核验的签名证据。",
            "scene_load": "档案室核验、走廊拦截与离馆后的复盘。",
            "handoff": "下一单元从签名日期与封存命令冲突开始。",
            "soft_character_budget": 3_600,
        }
    )
    saved = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"units": units},
        },
    )
    assert saved.status_code == 200
    draft = saved.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["decision"]["stage_id"] == "text"

    committed = client.get(
        f"/api/runs/{run_id}/stages/section_plan/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert committed["payload"]["units"][0]["unit_ref"] == units[0]["unit_ref"]
    assert committed["payload"]["units"][0]["title"] == units[0]["title"]
    assert committed["payload"]["units"][0]["soft_character_budget"] == 3_600


def test_short_prose_draft_api_edits_content_but_freezes_unit_identity(
    tmp_path: Path,
) -> None:
    client, run_id = _app(
        tmp_path,
        SHORT_NOVEL_ROUTE,
        _section_plan_review_policy(),
    )
    section_plan = _advance_to_section_plan(client, run_id)
    text_result = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": section_plan["decision_id"],
            "action": "accept",
            "domain_revision": section_plan["domain_revision"],
        },
    ).json()
    decision = text_result["decision"]
    assert decision["stage_id"] == "text"
    assert decision["unit_ref"] == "unit-1"
    current = client.get(
        f"/api/runs/{run_id}/stages/text/artifacts/current?unit_ref=unit-1"
    ).json()
    endpoint = f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}"

    identity_drift = dict(current["payload"])
    identity_drift["title"] = "作者不能在正文阶段改标题"
    rejected = client.put(
        endpoint,
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": identity_drift,
        },
    )
    assert rejected.status_code == 409

    edited = dict(current["payload"])
    edited["content"] = "玛雅把复印件贴近台灯，水印日期比封存记录晚了三天。"
    saved = client.put(
        endpoint,
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": edited,
        },
    )
    assert saved.status_code == 200
    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": saved.json()["draft"]["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    progress = accepted.json()["run"]["read_model"]["sequential_stage_progress"][
        "text"
    ]
    assert progress["committed_artifact_refs"]["unit-1"].startswith(
        "p32-text-committed-"
    )
    committed = client.get(
        f"/api/runs/{run_id}/stages/text/artifacts/current?unit_ref=unit-1"
    ).json()
    assert committed["editable"] is False
    assert committed["payload"]["content"] == edited["content"]


@pytest.mark.parametrize("mutation", ("replace_unit_ref", "unknown_pov", "unknown_promise"))
def test_section_plan_draft_api_rejects_identity_and_upstream_reference_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    client, run_id = _app(
        tmp_path / mutation,
        SHORT_NOVEL_ROUTE,
        _section_plan_review_policy(),
    )
    decision = _advance_to_section_plan(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/section_plan/artifacts/current"
    ).json()
    units = [dict(unit) for unit in current["payload"]["units"]]
    if mutation == "replace_unit_ref":
        units[0]["unit_ref"] = "unit-replacement"
    elif mutation == "unknown_pov":
        units[0]["pov_subject_ref"] = "subject-ghost"
    else:
        units[0]["promise_refs"] = ["promise-ghost"]

    response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"units": units},
        },
    )
    assert response.status_code == 409


def test_beat_board_draft_api_reorders_beats_and_advances_to_scene_deck(
    tmp_path: Path,
) -> None:
    client, run_id = _app(
        tmp_path,
        SCREENPLAY_SAMPLE_ROUTE,
        _beat_board_review_policy(),
    )
    decision = _advance_to_beat_board(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/beat_board/artifacts/current"
    ).json()

    assert current["editable"] is True
    assert current["artifact_kind"] == "beat_board"
    beats = [dict(beat) for beat in reversed(current["payload"]["beats"])]
    beats[0].update(
        {
            "dramatic_job": "让签名证据在公开场合形成不可逆的新局面。",
            "visible_pressure": "听证会即将结束，主持人要求主角立刻离场。",
            "character_decision": "主角当场递交带水印的签名页并要求登记。",
            "outcome": "证据进入公开记录，主角也正式成为调查对象。",
            "timing_hint": "约 110 秒",
        }
    )
    saved = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"beats": beats},
        },
    )
    assert saved.status_code == 200
    draft = saved.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["decision"]["stage_id"] == "scene_deck"

    committed = client.get(
        f"/api/runs/{run_id}/stages/beat_board/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert [beat["beat_ref"] for beat in committed["payload"]["beats"]] == [
        beat["beat_ref"] for beat in beats
    ]
    assert committed["payload"]["beats"][0]["dramatic_job"] == beats[0]["dramatic_job"]


def test_beat_board_draft_api_rejects_replaced_beat_ref(tmp_path: Path) -> None:
    client, run_id = _app(
        tmp_path,
        SCREENPLAY_SAMPLE_ROUTE,
        _beat_board_review_policy(),
    )
    decision = _advance_to_beat_board(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/beat_board/artifacts/current"
    ).json()
    beats = [dict(beat) for beat in current["payload"]["beats"]]
    beats[0]["beat_ref"] = "beat-replacement"

    response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"beats": beats},
        },
    )
    assert response.status_code == 409


def test_scene_deck_draft_api_commits_edited_scene_and_advances_to_script(
    tmp_path: Path,
) -> None:
    client, run_id = _app(
        tmp_path,
        SCREENPLAY_SAMPLE_ROUTE,
        _scene_deck_review_policy(),
    )
    decision = _advance_to_scene_deck(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/scene_deck/artifacts/current"
    ).json()

    assert current["editable"] is True
    assert current["artifact_kind"] == "scene_deck"
    scenes = [dict(scene) for scene in current["payload"]["scenes"]]
    scenes[0].update(
        {
            "heading": "INT. 市档案馆·封存室 - NIGHT",
            "location_and_time": "闭馆前八分钟，封存室只剩应急灯",
            "visible_goal": "在保安封门前核验原始签名页的水印序列。",
            "opposition": "保安切断主灯并要求她立刻交出档案盒。",
            "outcome": "她把水印序列同步到公开听证记录，但暴露了自己的位置。",
            "soft_page_target": 3.25,
        }
    )
    saved = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"scenes": scenes},
        },
    )
    assert saved.status_code == 200
    draft = saved.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["decision"]["stage_id"] == "script"

    committed = client.get(
        f"/api/runs/{run_id}/stages/scene_deck/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert committed["payload"]["scenes"][0]["scene_ref"] == scenes[0]["scene_ref"]
    assert committed["payload"]["scenes"][0]["heading"] == scenes[0]["heading"]
    assert committed["payload"]["scenes"][0]["soft_page_target"] == 3.25


@pytest.mark.parametrize("mutation", ("replace_scene_ref", "unknown_cast"))
def test_scene_deck_draft_api_rejects_identity_or_cast_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    client, run_id = _app(
        tmp_path,
        SCREENPLAY_SAMPLE_ROUTE,
        _scene_deck_review_policy(),
    )
    decision = _advance_to_scene_deck(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/scene_deck/artifacts/current"
    ).json()
    scenes = [dict(scene) for scene in current["payload"]["scenes"]]
    if mutation == "replace_scene_ref":
        scenes[0]["scene_ref"] = "scene-replacement"
    else:
        scenes[0]["cast_subject_refs"] = ["subject-ghost"]

    response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"scenes": scenes},
        },
    )
    assert response.status_code == 409


def test_book_architecture_draft_api_commits_aggregate_and_advances_to_cast(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path, LONG_NOVEL_ROUTE)
    brief = client.post(f"/api/runs/{run_id}/start").json()["decision"]
    architecture_result = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": brief["decision_id"],
            "action": "accept",
            "domain_revision": brief["domain_revision"],
        },
    ).json()
    decision = architecture_result["decision"]
    assert decision["stage_id"] == "book_architecture"

    current_response = client.get(
        f"/api/runs/{run_id}/stages/book_architecture/artifacts/current"
    )
    assert current_response.status_code == 200
    current = current_response.json()
    assert current["editable"] is True
    assert current["artifact_kind"] == "book_architecture"

    payload = dict(current["payload"])
    payload["book_promise"] = "让读者持续追问公共记忆由谁书写，以及公开真相必须支付什么代价。"
    payload["ending_conditions"] = [
        "完整证据链进入公共记录。",
        "主角承担公开证据造成的长期关系后果。",
    ]
    parts = [dict(part) for part in payload["parts"]]
    added_part = {
        **parts[-1],
        "part_ref": "part-injected",
        "ordinal": 3,
    }
    rejected = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {**payload, "parts": [*parts, added_part]},
        },
    )
    assert rejected.status_code == 409

    parts[0].update(
        {
            "ordinal": 2,
            "entry_state": "主角拿到一份无法公开核验的原始档案。",
            "unresolved_obligations": ["找到签发删改命令的人。"],
        }
    )
    later_part = {
        **parts[1],
        "ordinal": 1,
        "entry_state": "听证启动，但证据来源受到质疑。",
        "dramatic_question": "她是否愿意公开自己的违规取证过程？",
        "promise_refs": ["promise-truth", "promise-cost"],
        "turning_point_refs": ["turn-hearing", "turn-choice"],
        "exit_state": "事实进入公共记录，职业代价也已经落地。",
        "unresolved_obligations": [],
    }
    payload["parts"] = [later_part, parts[0]]

    saved_response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert saved_response.status_code == 200
    draft = saved_response.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["decision"]["stage_id"] == "cast"
    assert "regenerate" in body["decision"]["allowed_actions"]
    assert body["run"]["read_model"]["stage_status"]["cast"] == "awaiting_decision"

    committed = client.get(
        f"/api/runs/{run_id}/stages/book_architecture/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert committed["payload"]["book_promise"] == payload["book_promise"]
    assert [part["part_ref"] for part in committed["payload"]["parts"]] == [
        "part-hearing",
        parts[0]["part_ref"],
    ]
    assert committed["payload"]["parts"][1]["entry_state"] == parts[0]["entry_state"]
    assert committed["artifact_ref"] != current["artifact_ref"]

    receipt = client.app.state.phase32_execution_service.decisions.read(
        run_id,
        f"decision:{decision['decision_id']}",
    )
    assert receipt.command["draft_ref"] == draft["draft_ref"]
    assert receipt.command["source_artifact_ref"] == current["artifact_ref"]
    assert receipt.command["candidate_ref"].startswith(
        "p32-book_architecture-candidate-"
    )


def test_volumes_draft_api_reorders_stable_refs_and_advances_to_rolling_detail(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path, LONG_NOVEL_ROUTE)
    decision = _advance_to_volumes(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/volumes/artifacts/current"
    ).json()

    assert current["editable"] is True
    assert current["artifact_kind"] == "volume_architecture"
    source_volumes = [dict(volume) for volume in current["payload"]["volumes"]]
    assert [volume["volume_ref"] for volume in source_volumes] == [
        "volume-1",
        "volume-2",
    ]

    source_volumes.reverse()
    for index, volume in enumerate(source_volumes, start=1):
        volume["ordinal"] = index
    source_volumes[0]["promise"] = "把签名链变成任何人都能独立复核的公共证据。"
    source_volumes[0]["length_hint"] = 58_000
    payload = {"volumes": source_volumes}
    saved_response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert saved_response.status_code == 200
    draft = saved_response.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["decision"]["stage_id"] == "rolling_detail"

    committed = client.get(
        f"/api/runs/{run_id}/stages/volumes/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert [
        volume["volume_ref"] for volume in committed["payload"]["volumes"]
    ] == ["volume-2", "volume-1"]
    assert committed["payload"]["volumes"][0]["promise"] == source_volumes[0][
        "promise"
    ]
    assert committed["payload"]["volumes"][0]["part_ref"] == source_volumes[0][
        "part_ref"
    ]
    assert committed["payload"]["volumes"][0]["cast_subject_refs"] == ["maya"]


@pytest.mark.parametrize(
    "mutation",
    ("add_volume", "replace_volume_ref", "replace_part_ref", "replace_cast_ref"),
)
def test_volumes_draft_api_rejects_identity_and_upstream_reference_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    client, run_id = _app(tmp_path / mutation, LONG_NOVEL_ROUTE)
    decision = _advance_to_volumes(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/volumes/artifacts/current"
    ).json()
    volumes = [dict(volume) for volume in current["payload"]["volumes"]]
    if mutation == "add_volume":
        volumes.append(
            {
                **volumes[-1],
                "volume_ref": "volume-3",
                "ordinal": 3,
            }
        )
    elif mutation == "replace_volume_ref":
        volumes[0]["volume_ref"] = "volume-replacement"
    elif mutation == "replace_part_ref":
        volumes[0]["part_ref"] = "part-ghost"
    else:
        volumes[0]["cast_subject_refs"] = ["subject-ghost"]

    response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"volumes": volumes},
        },
    )
    assert response.status_code == 409


def test_rolling_detail_draft_api_reorders_frozen_chapters_and_advances_to_text(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path, LONG_NOVEL_ROUTE)
    decision = _advance_to_rolling_detail(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/rolling_detail/artifacts/current"
    ).json()

    assert current["editable"] is True
    assert current["artifact_kind"] == "detail_plan_index"
    payload = dict(current["payload"])
    windows = [dict(window) for window in payload["windows"]]
    chapters = [dict(chapter) for chapter in windows[0]["chapters"]]
    chapters.reverse()
    for index, chapter in enumerate(chapters, start=1):
        chapter["ordinal"] = index
    chapters[0]["dramatic_job"] = "让公开听证迫使机构对签名链作出正式回应。"
    chapters[0]["hook"] = "撤回封存单的人留下了可追溯的审批签名。"
    chapters[0]["scenes"][0]["goal"] = "在封存单撤回前锁定审批签名。"
    windows[0]["chapters"] = chapters
    windows[0]["handoff"] = "下一窗口从审批人失联与证人保护同时展开。"

    saved = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"windows": windows},
        },
    )
    assert saved.status_code == 200
    draft = saved.json()["draft"]

    accepted = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
            "draft_ref": draft["draft_ref"],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["decision"]["stage_id"] == "text"

    committed = client.get(
        f"/api/runs/{run_id}/stages/rolling_detail/artifacts/current"
    ).json()
    assert committed["editable"] is False
    assert [
        chapter["chapter_ref"]
        for chapter in committed["payload"]["windows"][0]["chapters"]
    ] == [chapters[0]["chapter_ref"], chapters[1]["chapter_ref"]]
    assert committed["payload"]["windows"][0]["chapters"][0][
        "dramatic_job"
    ] == chapters[0]["dramatic_job"]
    assert committed["payload"]["windows"][0]["chapters"][0]["scenes"][0][
        "scene_ref"
    ] == chapters[0]["scenes"][0]["scene_ref"]


def test_long_chapter_draft_api_edits_content_and_rejects_frozen_identity_drift(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path, LONG_NOVEL_ROUTE)
    rolling_detail = _advance_to_rolling_detail(client, run_id)
    result = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": rolling_detail["decision_id"],
            "action": "accept",
            "domain_revision": rolling_detail["domain_revision"],
        },
    ).json()
    decision = result["decision"]
    assert decision["stage_id"] == "text"
    chapter_ref = decision["unit_ref"]
    current = client.get(
        f"/api/runs/{run_id}/stages/text/artifacts/current",
        params={"unit_ref": chapter_ref},
    ).json()
    assert current["editable"] is True
    assert current["artifact_kind"] == "chapter"

    payload = dict(current["payload"])
    payload["content"] = "她重新核验了签名链。\n\n审批时间与封存记录相互矛盾。"
    saved = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert saved.status_code == 200

    for field, value in (
        ("chapter_ref", "chapter-replacement"),
        ("volume_ref", "volume-ghost"),
        ("title", "漂移标题"),
        ("pov_subject_ref", "ghost"),
    ):
        drifted = {**payload, field: value}
        rejected = client.put(
            f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
            json={
                "domain_revision": decision["domain_revision"],
                "source_artifact_ref": current["artifact_ref"],
                "payload": drifted,
            },
        )
        assert rejected.status_code == 409


@pytest.mark.parametrize(
    "mutation",
    (
        "add_window",
        "add_chapter",
        "replace_chapter_ref",
        "remove_scene",
        "replace_scene_ref",
        "replace_volume_ref",
        "replace_pov_ref",
        "replace_cast_ref",
    ),
)
def test_rolling_detail_draft_api_rejects_identity_and_upstream_reference_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    client, run_id = _app(tmp_path / mutation, LONG_NOVEL_ROUTE)
    decision = _advance_to_rolling_detail(client, run_id)
    current = client.get(
        f"/api/runs/{run_id}/stages/rolling_detail/artifacts/current"
    ).json()
    windows = [dict(window) for window in current["payload"]["windows"]]
    chapters = [dict(chapter) for chapter in windows[0]["chapters"]]
    chapter = chapters[0]

    if mutation == "add_window":
        windows.append(
            {
                **windows[0],
                "window_ref": "window-added",
                "ordinal": 2,
                "volume_refs": [chapter["volume_ref"]],
                "chapters": [
                    {
                        **chapter,
                        "chapter_ref": "chapter-added",
                        "ordinal": 3,
                        "scenes": [
                            {
                                **chapter["scenes"][0],
                                "scene_ref": "scene-added",
                            }
                        ],
                    }
                ],
            }
        )
    elif mutation == "add_chapter":
        chapters.append(
            {
                **chapter,
                "chapter_ref": "chapter-added",
                "ordinal": 3,
                "scenes": [
                    {
                        **chapter["scenes"][0],
                        "scene_ref": "scene-added",
                    }
                ],
            }
        )
        windows[0]["chapters"] = chapters
    elif mutation == "replace_chapter_ref":
        chapter["chapter_ref"] = "chapter-replacement"
    elif mutation == "remove_scene":
        chapter["scenes"] = []
    elif mutation == "replace_scene_ref":
        chapter["scenes"][0]["scene_ref"] = "scene-replacement"
    elif mutation == "replace_volume_ref":
        chapter["volume_ref"] = "volume-ghost"
        windows[0]["volume_refs"] = ["volume-ghost", windows[0]["volume_refs"][1]]
    elif mutation == "replace_pov_ref":
        chapter["pov_subject_ref"] = "ghost"
        chapter["cast_subject_refs"] = ["ghost"]
        chapter["scenes"][0]["cast_subject_refs"] = ["ghost"]
    else:
        chapter["cast_subject_refs"] = ["ghost"]
        chapter["pov_subject_ref"] = "ghost"
        chapter["scenes"][0]["cast_subject_refs"] = ["ghost"]
    windows[0]["chapters"] = chapters

    response = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": {"windows": windows},
        },
    )
    assert response.status_code == (422 if mutation == "remove_scene" else 409)


def _advance_to_rolling_detail(client: TestClient, run_id: str) -> dict:
    decision = _advance_to_volumes(client, run_id)
    result = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
        },
    ).json()
    assert result["decision"]["stage_id"] == "rolling_detail"
    return result["decision"]


def _advance_to_volumes(client: TestClient, run_id: str) -> dict:
    result = client.post(f"/api/runs/{run_id}/start").json()
    decision = result["decision"]
    while decision["stage_id"] != "volumes":
        result = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        ).json()
        decision = result["decision"]
    return decision


def _advance_to_section_plan(client: TestClient, run_id: str) -> dict:
    result = client.post(f"/api/runs/{run_id}/start").json()
    decision = result["decision"]
    while decision["stage_id"] != "section_plan":
        result = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        ).json()
        decision = result["decision"]
    return decision


def _advance_to_beat_board(client: TestClient, run_id: str) -> dict:
    result = client.post(f"/api/runs/{run_id}/start").json()
    decision = result["decision"]
    while decision["stage_id"] != "beat_board":
        result = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        ).json()
        decision = result["decision"]
    return decision


def _advance_to_scene_deck(client: TestClient, run_id: str) -> dict:
    decision = _advance_to_beat_board(client, run_id)
    result = client.post(
        f"/api/runs/{run_id}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
        },
    ).json()
    assert result["decision"]["stage_id"] == "scene_deck"
    return result["decision"]


def test_formal_run_routes_read_only_phase32_repository_and_retire_aliases(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path)

    listed = client.get("/api/runs")
    assert listed.status_code == 200
    assert [item["run_id"] for item in listed.json()["items"]] == [run_id]

    loaded = client.get(f"/api/runs/{run_id}")
    assert loaded.status_code == 200
    assert loaded.json()["definition"]["architecture_version"] == "phase32-routes-v1"
    assert loaded.json()["summary"]["run_id"] == run_id

    assert client.post("/api/runs").status_code == 410
    assert client.post(f"/api/runs/{run_id}/resume").status_code == 410
    assert client.get("/api/phase32/runs").status_code == 410
    assert client.post(f"/api/phase32/runs/{run_id}/start").status_code == 410


def test_formal_run_adapter_has_no_legacy_projection_or_store_reader() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/api/routes/runs.py"
    ).read_text(encoding="utf-8")

    assert "storage.event_projection" not in source
    assert "storage.run_history_projection" not in source
    assert "narrative_stores" not in source
    assert "api.routes.phase32_runs" not in source
    assert "api.routes.phase32_execution" not in source

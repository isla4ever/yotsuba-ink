from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novel_workflow.api.routes.contract_repairs import router as contract_repairs_router
from novel_workflow.api.routes.runs import router as runs_router
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingConflict,
    validate_phase32_author_edit_identity,
)
from novel_workflow.orchestration.phase32_contract_repair import (
    Phase32ContractRepairConflict,
    Phase32ContractRepairNotEligible,
    Phase32ContractRepairService,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_graph_execution import Phase32ExecutionError
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.output_contracts.phase32_route_artifacts import (
    DetailPlanIndexArtifact,
    ScreenplayBlock,
    ScreenplayDraftArtifact,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32ProviderResponse,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_contract_repair_store import (
    Phase32ContractRepairStore,
)
from novel_workflow.storage.phase32_decision_receipt_store import (
    Phase32DecisionReceiptStore,
)
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_history_projection import Phase32HistoryProjection
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from tests.test_phase32_driver import _payload_for
from tests.test_phase32_execution_failure_lock import _ContractFailOnceGateway


class _SemanticRedraftFailureGateway:
    def __init__(self) -> None:
        self.requests: list[Phase32ProviderRequest] = []
        self.script_attempts = 0

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        payload = _payload_for(request.creation_route_id, request.stage_id)
        if request.stage_id == "script":
            self.script_attempts += 1
            if self.script_attempts == 2:
                artifact = ScreenplayDraftArtifact.model_validate(payload)
                payload = artifact.model_copy(
                    update={
                        "blocks": (
                            artifact.blocks[0],
                            ScreenplayBlock(
                                kind="action",
                                text="姓名：林晚出现在封存表上。",
                            ),
                        )
                    }
                ).model_dump(mode="json")
        return Phase32ProviderResponse(
            payload=payload,
            usage={"prompt_tokens": 5, "completion_tokens": 7},
        )


class _SemanticInitialFailureGateway(_SemanticRedraftFailureGateway):
    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        response = await super().generate(request, binding=binding)
        if request.stage_id != "script" or self.script_attempts != 1:
            return response
        artifact = ScreenplayDraftArtifact.model_validate(response.payload)
        return response.model_copy(
            update={
                "payload": artifact.model_copy(
                    update={
                        "blocks": (
                            artifact.blocks[0],
                            ScreenplayBlock(
                                kind="action",
                                text="姓名：林晚出现在封存表上。",
                            ),
                        )
                    }
                ).model_dump(mode="json")
            }
        )


def test_rolling_detail_repair_may_fix_local_cast_scope_but_not_scene_identity() -> None:
    source = DetailPlanIndexArtifact.model_validate(
        _payload_for("long_novel", "rolling_detail")
    )
    source_window = source.windows[0]
    source_chapter = source_window.chapters[0].model_copy(
        update={"cast_subject_refs": ("maya", "mentor")}
    )
    source = source.model_copy(
        update={
            "windows": (
                source_window.model_copy(
                    update={
                        "chapters": (source_chapter, *source_window.chapters[1:])
                    }
                ),
            )
        }
    )
    repaired_scene = source_chapter.scenes[0].model_copy(
        update={"cast_subject_refs": ("maya", "mentor")}
    )
    repaired_chapter = source_chapter.model_copy(update={"scenes": (repaired_scene,)})
    repaired = source.model_copy(
        update={
            "windows": (
                source.windows[0].model_copy(
                    update={
                        "chapters": (repaired_chapter, *source.windows[0].chapters[1:])
                    }
                ),
            )
        }
    )

    with pytest.raises(Phase32ArtifactEditingConflict, match="Scene Cast scope"):
        validate_phase32_author_edit_identity(
            "rolling_detail",
            source.model_dump(mode="json"),
            repaired,
        )
    validate_phase32_author_edit_identity(
        "rolling_detail",
        source.model_dump(mode="json"),
        repaired,
        allow_rolling_detail_cast_scope_changes=True,
    )

    replaced_scene = repaired_scene.model_copy(update={"scene_ref": "scene-replaced"})
    replaced_chapter = repaired_chapter.model_copy(update={"scenes": (replaced_scene,)})
    replaced = repaired.model_copy(
        update={
            "windows": (
                repaired.windows[0].model_copy(
                    update={
                        "chapters": (replaced_chapter, *repaired.windows[0].chapters[1:])
                    }
                ),
            )
        }
    )
    with pytest.raises(Phase32ArtifactEditingConflict, match="Scene refs"):
        validate_phase32_author_edit_identity(
            "rolling_detail",
            source.model_dump(mode="json"),
            replaced,
            allow_rolling_detail_cast_scope_changes=True,
        )


async def _failed_script_fixture(tmp_path: Path):
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="contract-repair-run",
        project_id="contract-repair-project",
        creative_intent="验证合同拒绝稿可以零调用修复并回到人工门。",
    )
    gateway = _SemanticRedraftFailureGateway()
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    exports = ExportStore(tmp_path / "exports")
    decisions = Phase32DecisionReceiptStore(tmp_path / "decisions")
    driver = Phase32RouteDriver(artifacts, gateway, exports=exports)
    execution = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: driver,
        decisions=decisions,
    )
    current = await execution.start(fixture.definition.run_id)
    while current.result.decision is not None:
        decision = current.result.decision
        if decision["stage_id"] == "script":
            break
        current = await execution.resume(
            fixture.definition.run_id,
            {
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        )
    script_decision = current.result.decision
    assert script_decision is not None
    assert script_decision["stage_id"] == "script"
    with pytest.raises(Phase32ExecutionError, match="graph step failed"):
        await execution.resume(
            fixture.definition.run_id,
            {
                "decision_id": script_decision["decision_id"],
                "action": "regenerate",
                "domain_revision": script_decision["domain_revision"],
                "direction": "保留场景身份，但补充封存表上的姓名。",
            },
        )
    rejected = next(
        receipt
        for receipt in reversed(driver.provider_operations.list(fixture.definition.run_id))
        if receipt.stage_id == "script" and receipt.status == "contract_rejected"
    )
    repairs = Phase32ContractRepairStore(tmp_path / "contract-repairs")
    service = Phase32ContractRepairService(
        fixture.repository,
        artifacts,
        driver.provider_operations,
        repairs,
        execution,
    )
    return fixture, gateway, artifacts, exports, service, rejected


@pytest.mark.asyncio
async def test_semantic_contract_repair_reopens_explicit_decision_without_provider_call(
    tmp_path: Path,
) -> None:
    fixture, gateway, artifacts, _exports, service, rejected = (
        await _failed_script_fixture(tmp_path)
    )
    run_id = fixture.definition.run_id
    failed = fixture.repository.read(run_id)
    quarantine = service.inspect(run_id, rejected.receipt_ref)

    assert failed.state.status == "failed"
    assert quarantine.eligible is True
    assert quarantine.stage_id == "script"
    assert quarantine.findings[0].code == "stage_reference_contract_invalid"
    assert "unregistered explicit character name" in quarantine.findings[0].message
    assert quarantine.source_payload == rejected.raw_provider_payload

    repaired_payload = _payload_for("screenplay_sample", "script")
    drifted_payload = dict(repaired_payload)
    drifted_payload["scene_ref"] = "scene-replaced"
    command = {
        "repair_id": "script-contract-repair-1",
        "provider_receipt_ref": rejected.receipt_ref,
        "provider_request_signature": rejected.request_signature,
        "definition_digest": fixture.definition.definition_digest,
        "domain_revision": failed.state.domain_revision,
        "source_payload_digest": quarantine.source_payload_digest,
        "payload": drifted_payload,
    }
    with pytest.raises(Phase32ArtifactEditingConflict, match="frozen Scene ref"):
        await service.repair(run_id, command)

    command["payload"] = repaired_payload
    calls_before = len(gateway.requests)
    operations_before = len(service.provider_operations.list(run_id))
    outcome = await service.repair(run_id, command)

    assert outcome.reused is False
    assert outcome.repair.status == "succeeded"
    assert outcome.decision is not None
    assert outcome.decision["stage_id"] == "script"
    assert outcome.decision["artifact_ref"] == outcome.repair.candidate_ref
    assert outcome.decision["allowed_actions"] == ["accept", "cancel"]
    assert outcome.decision["redraft_used"] == 1
    restored = fixture.repository.read(run_id)
    assert restored.state.status == "awaiting_decision"
    assert restored.read_model.failure is None
    assert restored.read_model.pending_decisions[0].artifact_ref == (
        outcome.repair.candidate_ref
    )
    candidate = artifacts.read(run_id, outcome.repair.candidate_ref)
    assert candidate.source_operation_key.startswith("contract-repair:")
    assert len(gateway.requests) == calls_before
    assert len(service.provider_operations.list(run_id)) == operations_before
    assert service.provider_operations.read_receipt_ref(
        run_id,
        rejected.receipt_ref,
    ) == rejected

    replay = await service.repair(run_id, command)
    assert replay.reused is True
    assert replay.repair == outcome.repair
    assert replay.decision == outcome.decision
    assert len(gateway.requests) == calls_before
    assert len(service.provider_operations.list(run_id)) == operations_before

    conflicting = dict(command)
    conflicting["payload"] = {
        **repaired_payload,
        "blocks": [
            repaired_payload["blocks"][0],
            {"kind": "action", "text": "Maya 重新核对封存表。"},
        ],
    }
    with pytest.raises(Phase32ContractRepairConflict, match="different command data"):
        await service.repair(run_id, conflicting)


@pytest.mark.asyncio
async def test_initial_semantic_failure_injects_repair_without_provider_fallthrough(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="initial-contract-repair-run",
        project_id="initial-contract-repair-project",
        creative_intent="验证首次语义合同失败的本地候选注入。",
    )
    gateway = _SemanticInitialFailureGateway()
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    driver = Phase32RouteDriver(artifacts, gateway)
    execution = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: driver,
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
    )
    current = await execution.start(fixture.definition.run_id)
    for expected_stage in ("brief", "cast"):
        decision = current.result.decision
        assert decision is not None and decision["stage_id"] == expected_stage
        current = await execution.resume(
            fixture.definition.run_id,
            {
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        )
    beat_decision = current.result.decision
    assert beat_decision is not None and beat_decision["stage_id"] == "beat_board"
    with pytest.raises(Phase32ExecutionError, match="graph step failed"):
        await execution.resume(
            fixture.definition.run_id,
            {
                "decision_id": beat_decision["decision_id"],
                "action": "accept",
                "domain_revision": beat_decision["domain_revision"],
            },
        )
    failed = fixture.repository.read(fixture.definition.run_id)
    assert failed.state.active_stage_id == "script"
    assert failed.state.pending_decision_action == ""
    rejected = next(
        receipt
        for receipt in reversed(driver.provider_operations.list(fixture.definition.run_id))
        if receipt.stage_id == "script"
    )
    service = Phase32ContractRepairService(
        fixture.repository,
        artifacts,
        driver.provider_operations,
        Phase32ContractRepairStore(tmp_path / "contract-repairs"),
        execution,
    )
    quarantine = service.inspect(fixture.definition.run_id, rejected.receipt_ref)
    calls_before = len(gateway.requests)
    operations_before = len(driver.provider_operations.list(fixture.definition.run_id))

    outcome = await service.repair(
        fixture.definition.run_id,
        {
            "repair_id": "initial-script-contract-repair-1",
            "provider_receipt_ref": rejected.receipt_ref,
            "provider_request_signature": rejected.request_signature,
            "definition_digest": fixture.definition.definition_digest,
            "domain_revision": failed.state.domain_revision,
            "source_payload_digest": quarantine.source_payload_digest,
            "payload": _payload_for("screenplay_sample", "script"),
        },
    )

    assert outcome.decision is not None
    assert outcome.decision["stage_id"] == "script"
    assert outcome.decision["redraft_used"] == 0
    assert outcome.decision["allowed_actions"] == ["accept", "regenerate", "cancel"]
    assert len(gateway.requests) == calls_before
    assert len(driver.provider_operations.list(fixture.definition.run_id)) == (
        operations_before
    )


@pytest.mark.asyncio
async def test_contract_repair_http_projection_preserves_source_and_zero_call_boundary(
    tmp_path: Path,
) -> None:
    fixture, gateway, _artifacts, exports, service, rejected = (
        await _failed_script_fixture(tmp_path)
    )
    run_id = fixture.definition.run_id
    app = FastAPI()
    app.include_router(runs_router)
    app.include_router(contract_repairs_router)
    app.state.phase32_contract_repairs = service
    app.state.phase32_execution_service = service.execution
    app.state.phase32_run_repository = fixture.repository
    app.state.phase32_event_projection = Phase32EventProjection(fixture.repository)
    app.state.phase32_history_projection = Phase32HistoryProjection(fixture.repository)
    app.state.phase32_exports = exports
    client = TestClient(app)

    quarantine_response = client.get(
        f"/api/runs/{run_id}/contract-quarantines/{rejected.receipt_ref}"
    )
    assert quarantine_response.status_code == 200
    quarantine = quarantine_response.json()["quarantine"]
    assert quarantine["eligible"] is True
    assert quarantine["provider_request_signature"] == rejected.request_signature

    current_quarantine_response = client.get(
        f"/api/runs/{run_id}/contract-quarantine"
    )
    assert current_quarantine_response.status_code == 200
    assert current_quarantine_response.json()["quarantine"] == quarantine

    operations_before = len(service.provider_operations.list(run_id))
    calls_before = len(gateway.requests)
    response = client.post(
        f"/api/runs/{run_id}/contract-repairs",
        json={
            "repair_id": "script-api-contract-repair-1",
            "provider_receipt_ref": rejected.receipt_ref,
            "provider_request_signature": rejected.request_signature,
            "definition_digest": fixture.definition.definition_digest,
            "domain_revision": quarantine["domain_revision"],
            "source_payload_digest": quarantine["source_payload_digest"],
            "payload": _payload_for("screenplay_sample", "script"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["repair"]["status"] == "succeeded"
    assert body["run"]["read_model"]["status"] == "awaiting_decision"
    assert body["decision"]["artifact_ref"] == body["repair"]["candidate_ref"]
    assert body["decision"]["kind"] == "route_stage_decision"
    assert len(gateway.requests) == calls_before
    assert len(service.provider_operations.list(run_id)) == operations_before


@pytest.mark.asyncio
async def test_schema_invalid_provider_return_cannot_be_reconstructed_as_human_repair(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="schema-invalid-quarantine-run",
        project_id="schema-invalid-quarantine-project",
        creative_intent="验证截断或 Schema 无效返回不能伪装成人工语义修复。",
    )
    gateway = _ContractFailOnceGateway()
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    driver = Phase32RouteDriver(artifacts, gateway)
    execution = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: driver,
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
    )
    with pytest.raises(Phase32ExecutionError, match="graph step failed"):
        await execution.start(fixture.definition.run_id)
    rejected = driver.provider_operations.list(fixture.definition.run_id)[0]
    service = Phase32ContractRepairService(
        fixture.repository,
        artifacts,
        driver.provider_operations,
        Phase32ContractRepairStore(tmp_path / "contract-repairs"),
        execution,
    )

    quarantine = service.inspect(fixture.definition.run_id, rejected.receipt_ref)
    assert quarantine.eligible is False
    assert quarantine.findings[0].code == "artifact_schema_invalid"
    operations_before = len(driver.provider_operations.list(fixture.definition.run_id))
    with pytest.raises(Phase32ContractRepairNotEligible, match="Schema"):
        await service.repair(
            fixture.definition.run_id,
            {
                "repair_id": "schema-invalid-repair-forbidden",
                "provider_receipt_ref": rejected.receipt_ref,
                "provider_request_signature": rejected.request_signature,
                "definition_digest": fixture.definition.definition_digest,
                "domain_revision": quarantine.domain_revision,
                "source_payload_digest": quarantine.source_payload_digest,
                "payload": _payload_for("screenplay_sample", "brief"),
            },
        )
    assert len(gateway.requests) == 1
    assert len(driver.provider_operations.list(fixture.definition.run_id)) == (
        operations_before
    )
    assert service.repairs.list(fixture.definition.run_id) == []
    assert artifacts.list(fixture.definition.run_id) == []

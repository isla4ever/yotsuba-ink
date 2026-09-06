from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingService,
)
from novel_workflow.orchestration.phase32_author_collaboration import (
    Phase32AuthorCollaborationService,
    Phase32AuthorCollaborationUnavailable,
    Phase32PatchWritebackUnavailable,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32DecisionCommand,
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.output_contracts.phase32_author_collaboration import (
    CreatePhase32CollaborationThreadRequest,
    CreatePhase32CollaborationTurnRequest,
    Phase32CollaborationContextPreviewRequest,
    Phase32SelectionAnchor,
)
from novel_workflow.providers.phase32_contract import Phase32ProviderResponse
from novel_workflow.references.collaboration_context_errors import (
    CollaborationContextError,
    CollaborationSourceStale,
)
from novel_workflow.references.phase32_collaboration_context import (
    Phase32CollaborationContextCompiler,
)
from novel_workflow.runtime.graph.phase32_collaboration_execution import (
    Phase32CollaborationExecutor,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.storage.phase32_artifact_draft_store import Phase32ArtifactDraftStore
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_collaboration_context_store import (
    Phase32CollaborationContextStore,
)
from novel_workflow.storage.phase32_collaboration_store import Phase32CollaborationStore
from novel_workflow.storage.phase32_decision_receipt_store import (
    Phase32DecisionReceiptStore,
)
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationStore,
)
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.workflows.graph_run_definition import (
    freeze_graph_run_definition,
    freeze_phase32_scale_profile,
)
from novel_workflow.workflows.phase32_scale import (
    freeze_continuity_acceptance_scale_profile,
)
from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)
from tests.test_phase32_driver import _FixtureGateway


ROUTE_STAGES = (
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
)


class _CollaborationGateway(_FixtureGateway):
    async def generate(self, request, *, binding):
        if request.provider_task_kind != "author_collaboration":
            return await super().generate(request, binding=binding)
        self.requests.append(request)
        if request.transport_task_name.endswith(".plan"):
            return Phase32ProviderResponse(
                payload={
                    "response": "先确认人物的公开目标，再缩小改动范围。",
                    "plan": {
                        "goal": "增强人物目标的可验证性",
                        "findings": ["当前目标缺少公开动作"],
                        "steps": ["补充可验证动作", "复核下游引用"],
                        "impacts": ["人物职责"],
                        "risks": ["不得改变 subject_ref"],
                        "questions": [],
                    },
                },
                usage={"input_tokens": 120, "output_tokens": 48},
            )
        if request.transport_task_name.endswith(".revise"):
            return Phase32ProviderResponse(
                payload={
                    "response": "我只改写了选中的目标描述。",
                    "replacement": "在公开听证前找到可独立核验的原始签名链。",
                    "rationale": "把抽象愿望改成可观察、可验证的行动目标。",
                },
                usage={"input_tokens": 140, "output_tokens": 56},
            )
        return Phase32ProviderResponse(
            payload={"response": "这个阶段的核心判断应以当前冻结 Artifact 为准。"},
            usage={"input_tokens": 100, "output_tokens": 32},
        )


class _UnexpectedCollaborationExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def execute(self, run_id: str, thread_id: str, turn_id: str):
        self.calls.append((run_id, thread_id, turn_id))
        raise AssertionError("continuity acceptance must reject before executor dispatch")


@pytest.mark.asyncio
async def test_continuity_acceptance_rejects_collaboration_before_provider_side_effects(
    tmp_path: Path,
) -> None:
    source = create_phase32_run_fixture(
        tmp_path / "source",
        route=LONG_NOVEL_ROUTE,
        run_id="source-continuity-acceptance",
        project_id="source-continuity-acceptance-project",
        workflow_id="official.long_novel",
        creative_intent="验证连续性验收基线不会被作者协作改写。",
        target=150_000,
    ).definition
    definition = freeze_graph_run_definition(
        run_id="continuity-acceptance-collaboration-domain",
        project_id="continuity-acceptance-collaboration-domain-project",
        workflow_id=source.workflow_id,
        workflow_revision=source.workflow_revision,
        workflow_digest=source.workflow_digest,
        route_contract=source.route_contract,
        scale_profile=freeze_phase32_scale_profile(
            freeze_continuity_acceptance_scale_profile(
                "long_novel",
                target=150_000,
            )
        ),
        inputs=source.inputs,
        provider_bindings_by_stage=source.provider_bindings_by_stage,
        export_profile=source.export_profile,
        created_at=source.created_at,
    )
    repository = Phase32RunRepository(tmp_path / "acceptance")
    repository.create(definition)
    artifacts = Phase32ArtifactStore(tmp_path / "acceptance-artifacts")
    editing = Phase32ArtifactEditingService(
        repository,
        artifacts,
        Phase32ArtifactDraftStore(tmp_path / "acceptance-drafts"),
    )
    collaboration = Phase32CollaborationStore(tmp_path / "acceptance-collaboration")
    contexts = Phase32CollaborationContextStore(tmp_path / "acceptance-contexts")
    provider_inputs = Phase32ProviderInputStore(tmp_path / "acceptance-provider-inputs")
    provider_operations = Phase32ProviderOperationStore(
        tmp_path / "acceptance-provider-operations",
        provider_inputs=provider_inputs,
    )
    executor = _UnexpectedCollaborationExecutor()
    service = Phase32AuthorCollaborationService(
        repository,
        collaboration,
        contexts,
        Phase32CollaborationContextCompiler(
            repository,
            artifacts,
            editing,
            collaboration,
        ),
        executor,
    )

    with pytest.raises(Phase32AuthorCollaborationUnavailable) as create_error:
        service.create_thread(
            definition.run_id,
            CreatePhase32CollaborationThreadRequest(stage_id="book_architecture"),
        )
    with pytest.raises(Phase32AuthorCollaborationUnavailable) as execute_error:
        await service.execute_turn(
            definition.run_id,
            "preexisting-thread",
            "queued-turn",
        )

    assert create_error.value.code == "author_collaboration_unavailable"
    assert execute_error.value.code == "author_collaboration_unavailable"
    assert executor.calls == []
    assert collaboration.list_threads(definition.run_id) == []
    assert provider_inputs.list(definition.run_id) == []
    assert provider_operations.list(definition.run_id) == []


@pytest.mark.parametrize(
    ("route", "expected_stages"),
    ROUTE_STAGES,
    ids=("screenplay_sample", "short_novel", "long_novel"),
)
@pytest.mark.asyncio
async def test_phase32_routes_create_threads_only_at_declared_collaboration_stages(
    tmp_path: Path,
    route,
    expected_stages,
) -> None:
    harness = _Harness(tmp_path / route.route_id, route)
    outcome = await harness.execution.start(harness.run_id)
    seen: list[str] = []
    while outcome.result.decision is not None:
        decision = outcome.result.decision
        stage_id = str(decision["stage_id"])
        if stage_id == "brief":
            with pytest.raises(Phase32AuthorCollaborationUnavailable):
                harness.collaboration.create_thread(
                    harness.run_id,
                    CreatePhase32CollaborationThreadRequest(stage_id="brief"),
                )
        if stage_id in expected_stages and stage_id not in seen:
            thread = harness.collaboration.create_thread(
                harness.run_id,
                CreatePhase32CollaborationThreadRequest(
                    stage_id=stage_id,
                    label=f"{stage_id} 当前单元",
                ),
            )
            assert thread.creation_route_id == route.route_id
            assert thread.route_revision == route.revision
            assert thread.artifact_kind == harness.fixture.definition.stage(stage_id).artifact_kind
            assert thread.scope.artifact_ref.startswith(f"p32-{stage_id}-candidate-")
            seen.append(stage_id)
        if tuple(seen) == expected_stages:
            break
        outcome = await harness.execution.resume(
            harness.run_id,
            Phase32DecisionCommand(
                decision_id=str(decision["decision_id"]),
                action="accept",
                domain_revision=int(decision["domain_revision"]),
            ),
        )
    assert tuple(dict.fromkeys(seen)) == expected_stages
    assert outcome.result.decision is not None
    assert outcome.result.decision["stage_id"] == expected_stages[-1]


@pytest.mark.asyncio
async def test_thread_identity_rejects_other_route_source_and_missing_unit(tmp_path: Path) -> None:
    first = _Harness(tmp_path / "first", SHORT_NOVEL_ROUTE)
    second = _Harness(tmp_path / "second", SHORT_NOVEL_ROUTE)
    first_decision = await _advance_to(first, "story_map")
    second_decision = await _advance_to(second, "story_map")
    unrelated_source_ref = f"{second_decision['artifact_ref']}-other-run"

    with pytest.raises(CollaborationSourceStale):
        first.collaboration.create_thread(
            first.run_id,
            CreatePhase32CollaborationThreadRequest(
                stage_id="story_map",
                source_ref=unrelated_source_ref,
            ),
        )
    with pytest.raises(CollaborationContextError, match="does not exist"):
        first.collaboration.create_thread(
            first.run_id,
            CreatePhase32CollaborationThreadRequest(
                stage_id="story_map",
                source_ref=str(first_decision["artifact_ref"]),
                unit_ref="missing-anchor",
            ),
        )
    with pytest.raises(Phase32AuthorCollaborationUnavailable):
        first.collaboration.create_thread(
            first.run_id,
            CreatePhase32CollaborationThreadRequest(stage_id="book_architecture"),
        )


@pytest.mark.asyncio
async def test_draft_change_makes_existing_thread_context_stale(tmp_path: Path) -> None:
    harness = _Harness(tmp_path, SHORT_NOVEL_ROUTE)
    decision = await _advance_to(harness, "cast")
    current = harness.editing.current(harness.run_id, "cast")
    thread = harness.collaboration.create_thread(
        harness.run_id,
        CreatePhase32CollaborationThreadRequest(stage_id="cast"),
    )
    payload = dict(current.payload)
    characters = [dict(item) for item in payload["characters"]]
    characters[0]["desire"] = "在听证前找到可核验的原始签名链。"
    payload["characters"] = characters
    harness.editing.save_draft(
        harness.run_id,
        str(decision["decision_id"]),
        domain_revision=int(decision["domain_revision"]),
        source_artifact_ref=current.artifact_ref,
        payload=payload,
    )

    with pytest.raises(CollaborationSourceStale):
        harness.collaboration.preview_context(
            harness.run_id,
            thread.thread_id,
            Phase32CollaborationContextPreviewRequest(
                client_turn_id="stale-turn",
                message="人物目标是否足够具体？",
            ),
        )


@pytest.mark.asyncio
async def test_revise_creates_patch_and_phase32_provider_receipts_without_writeback(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path, SHORT_NOVEL_ROUTE)
    await _advance_to(harness, "cast")
    current = harness.editing.current(harness.run_id, "cast")
    character = current.payload["characters"][0]
    unit_ref = str(character["subject_ref"])
    field_path = "characters.0.desire"
    selected_text = str(character["desire"])
    thread = harness.collaboration.create_thread(
        harness.run_id,
        CreatePhase32CollaborationThreadRequest(
            stage_id="cast",
            source_ref=current.artifact_ref,
            unit_ref=unit_ref,
            label=str(character["display_name"]),
        ),
    )
    selection = Phase32SelectionAnchor(
        anchor_id="selection-cast-desire",
        stage_id="cast",
        source_ref=current.artifact_ref,
        unit_ref=unit_ref,
        field_path=field_path,
        field_hash=_sha256(selected_text),
        selection_start=0,
        selection_end=len(selected_text),
        selected_text_hash=_sha256(selected_text),
        selected_char_count=len(selected_text),
        preview=selected_text,
        selected_text=selected_text,
        created_at="2026-08-25T00:00:00+08:00",
    )
    preview_input = Phase32CollaborationContextPreviewRequest(
        client_turn_id="revise-cast-1",
        mode="revise",
        message="把目标改得具体，但不要改变人物身份。",
        selection=selection,
    )
    receipt = harness.collaboration.preview_context(
        harness.run_id, thread.thread_id, preview_input
    )
    queued = harness.collaboration.create_turn(
        harness.run_id,
        thread.thread_id,
        CreatePhase32CollaborationTurnRequest(
            **preview_input.model_dump(),
            preview_signature=receipt.receipt_hash,
        ),
    )
    completed = await harness.collaboration.execute_turn(
        harness.run_id, thread.thread_id, queued.turn_id
    )

    assert completed.status == "completed"
    assert completed.patch_candidate_ref.startswith("p32-patch-")
    patch = harness.store.read_patch(harness.run_id, completed.patch_candidate_ref)
    assert patch.status == "proposed"
    assert patch.source_artifact_ref == current.artifact_ref
    assert patch.operations[0].field_path == field_path
    assert patch.operations[0].replacement.startswith("在公开听证前")
    assert harness.artifacts.read(harness.run_id, current.artifact_ref).payload == current.payload
    with pytest.raises(Phase32PatchWritebackUnavailable):
        harness.collaboration.accept_patch(harness.run_id, patch.patch_id)
    rejected = harness.collaboration.reject_patch(harness.run_id, patch.patch_id)
    assert rejected.status == "rejected"
    assert harness.artifacts.read(harness.run_id, current.artifact_ref).payload == current.payload

    inputs = harness.provider_inputs.list(harness.run_id)
    operations = harness.provider_operations.list(harness.run_id)
    collaboration_inputs = [
        item for item in inputs if ":collaboration:" in item.operation_key
    ]
    collaboration_operations = [
        item for item in operations if ":collaboration:" in item.operation_key
    ]
    assert len(collaboration_inputs) == 1
    assert len(collaboration_operations) == 1
    assert collaboration_operations[0].status == "succeeded"
    assert collaboration_operations[0].provider_input_ref == collaboration_inputs[0].provider_input_ref
    assert not (tmp_path / "native_runtime" / "collaboration").exists()


@pytest.mark.asyncio
async def test_client_turn_replay_is_idempotent_and_input_drift_conflicts(tmp_path: Path) -> None:
    harness = _Harness(tmp_path, SCREENPLAY_SAMPLE_ROUTE)
    await _advance_to(harness, "cast")
    thread = harness.collaboration.create_thread(
        harness.run_id,
        CreatePhase32CollaborationThreadRequest(stage_id="cast"),
    )
    preview_input = Phase32CollaborationContextPreviewRequest(
        client_turn_id="discussion-1",
        mode="discuss",
        message="当前人物职责是否清晰？",
    )
    receipt = harness.collaboration.preview_context(
        harness.run_id, thread.thread_id, preview_input
    )
    command = CreatePhase32CollaborationTurnRequest(
        **preview_input.model_dump(),
        preview_signature=receipt.receipt_hash,
    )
    first = harness.collaboration.create_turn(harness.run_id, thread.thread_id, command)
    replay = harness.collaboration.create_turn(harness.run_id, thread.thread_id, command)
    assert replay.turn_id == first.turn_id

    changed_preview = harness.collaboration.preview_context(
        harness.run_id,
        thread.thread_id,
        Phase32CollaborationContextPreviewRequest(
            client_turn_id="discussion-1",
            mode="discuss",
            message="换一个问题。",
        ),
    )
    with pytest.raises(ValueError, match="turn_replay_conflict"):
        harness.collaboration.create_turn(
            harness.run_id,
            thread.thread_id,
            CreatePhase32CollaborationTurnRequest(
                client_turn_id="discussion-1",
                mode="discuss",
                message="换一个问题。",
                preview_signature=changed_preview.receipt_hash,
            ),
        )


class _Harness:
    def __init__(self, root: Path, route) -> None:
        policy = ReviewPolicy(
            policy_id=f"review.{route.route_id}.collaboration-test",
            revision="r1",
            route_id=route.route_id,
            checkpoint_policy="every_stage",
            warning_policy="pause_at_milestone",
            directed_redraft_limit_by_stage={},
            mandatory_decision_stages=tuple(
                stage.stage_id for stage in route.stages if stage.stage_id != "export"
            ),
        )
        self.fixture = create_phase32_run_fixture(
            root / "runtime",
            route=route,
            run_id=f"collaboration-{route.route_id}",
            project_id=f"project-{route.route_id}",
            creative_intent="验证 Phase 32 作者协作绑定真实阶段 Artifact。",
            target=150_000 if route.route_id == "long_novel" else None,
            review_policy=policy,
        )
        self.run_id = self.fixture.definition.run_id
        self.gateway = _CollaborationGateway({})
        self.artifacts = Phase32ArtifactStore(root / "artifacts")
        self.drafts = Phase32ArtifactDraftStore(root / "artifact_drafts")
        self.editing = Phase32ArtifactEditingService(
            self.fixture.repository, self.artifacts, self.drafts
        )
        self.provider_inputs = Phase32ProviderInputStore(root / "provider_inputs")
        self.provider_operations = Phase32ProviderOperationStore(
            root / "provider_operations",
            provider_inputs=self.provider_inputs,
        )
        self.execution = Phase32RunExecutionService(
            self.fixture.repository,
            checkpoint_root=root / "checkpoints",
            decisions=Phase32DecisionReceiptStore(root / "decisions"),
            artifact_editing=self.editing,
            driver_factory=lambda _definition: Phase32RouteDriver(
                self.artifacts,
                self.gateway,
                provider_inputs=self.provider_inputs,
                provider_operations=self.provider_operations,
            ),
        )
        self.store = Phase32CollaborationStore(root / "collaboration")
        self.context_store = Phase32CollaborationContextStore(
            root / "collaboration_contexts"
        )
        self.context = Phase32CollaborationContextCompiler(
            self.fixture.repository,
            self.artifacts,
            self.editing,
            self.store,
        )
        executor = Phase32CollaborationExecutor(
            self.store,
            self.context_store,
            self.context,
            self.provider_inputs,
            self.provider_operations,
            self.gateway,
        )
        self.collaboration = Phase32AuthorCollaborationService(
            self.fixture.repository,
            self.store,
            self.context_store,
            self.context,
            executor,
        )


async def _advance_to(harness: _Harness, stage_id: str) -> dict[str, object]:
    outcome = await harness.execution.start(harness.run_id)
    while outcome.result.decision is not None:
        decision = outcome.result.decision
        if decision["stage_id"] == stage_id:
            return decision
        outcome = await harness.execution.resume(
            harness.run_id,
            Phase32DecisionCommand(
                decision_id=str(decision["decision_id"]),
                action="accept",
                domain_revision=int(decision["domain_revision"]),
            ),
        )
    raise AssertionError(f"Run completed before reaching {stage_id}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

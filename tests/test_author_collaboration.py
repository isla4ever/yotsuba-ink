from __future__ import annotations

import asyncio
import hashlib

import pytest

from novel_workflow.knowledge import KnowledgeBase
from novel_workflow.memory.canon_store import CanonFact
from novel_workflow.orchestration.author_collaboration import (
    AuthorCollaborationService,
    PatchWritebackUnavailable,
)
from novel_workflow.orchestration.stage_artifact_editing import (
    load_stage_artifact_draft,
    save_stage_artifact_draft,
)
from novel_workflow.output_contracts.author_collaboration import (
    CollaborationContextPolicy,
    CollaborationContextPreviewRequest,
    CreateCollaborationThreadRequest,
    CreateCollaborationTurnRequest,
    SelectionAnchor,
)
from novel_workflow.references.collaboration_context import (
    CollaborationContextBudgetExceeded,
    CollaborationContextError,
    CollaborationSourceStale,
)
from novel_workflow.references.collaboration_context_errors import (
    CollaborationFieldNotEditable,
)
from novel_workflow.runtime.graph.author_collaboration_requests import (
    CollaborationProviderResult,
)
from novel_workflow.runtime.graph.author_collaboration_graph import (
    AuthorCollaborationExecutor,
)
from novel_workflow.runtime.graph.execution_service import NarrativeExecutionService
from novel_workflow.runtime.graph.runtime import filesystem_stores, open_sqlite_runtime
from novel_workflow.storage.narrative_run_repository import ExportPreferences, ProviderBinding
from novel_workflow.workflows.hierarchical_scale import plan_hierarchical_narrative_scale
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.phase27_bindings import cover_asset_binding, provider_binding
from tests.test_planning_contracts import (
    _brief as contract_brief,
    _cast as contract_cast,
    _detail as contract_detail,
    _spine as contract_spine,
    _volumes as contract_volumes,
)


class FakeCollaborationProvider:
    def __init__(self) -> None:
        self.requests = []

    async def generate_collaboration_turn(self, request):
        self.requests.append(request)
        if request.mode == "revise":
            return CollaborationProviderResult(
                content="已将因果动作收紧为可见选择，等待你确认差异。",
                replacement="主角公开母带来源，并承担档案修复资格被撤销的后果",
                rationale="把抽象的调查进展改为可验证动作与不可逆代价。",
                usage={"prompt_tokens": 30, "completion_tokens": 20},
            )
        return CollaborationProviderResult(
            content="当前因果成立，但主角承担的公开代价还可以更明确。",
            usage={"prompt_tokens": 20, "completion_tokens": 12},
        )


class BlockingCollaborationProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def generate_collaboration_turn(self, request):
        self.started.set()
        await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_parallel_runtime_open_initializes_one_checkpoint_schema(tmp_path) -> None:
    root = tmp_path / "runtime"

    async def open_once() -> None:
        async with open_sqlite_runtime(root, FakeCollaborationProvider()) as runtime:
            assert runtime.stores.runs is not None

    await asyncio.gather(*(open_once() for _ in range(4)))


@pytest.mark.asyncio
async def test_discussion_turn_is_receipted_and_provider_replay_is_idempotent(tmp_path) -> None:
    root = tmp_path / "runtime"
    stores, source = _deep_run(root)
    service = AuthorCollaborationService(stores)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="turn-1",
            label="转折一",
        ),
    )
    preview_request = CollaborationContextPreviewRequest(
        client_turn_id="client-turn-1",
        mode="discuss",
        message="这个转折的代价是否足够具体？",
    )
    preview = service.preview_context("run-collab", thread.thread_id, preview_request)
    turn = service.create_turn(
        "run-collab",
        thread.thread_id,
        CreateCollaborationTurnRequest(
            **preview_request.model_dump(),
            preview_signature=preview.receipt_hash,
        ),
    )
    provider = FakeCollaborationProvider()

    async with open_sqlite_runtime(root, provider) as runtime:
        await runtime.collaborate("run-collab", thread.thread_id, turn.turn_id)
        await runtime.collaborate("run-collab", thread.thread_id, turn.turn_id)

    detail = service.read_thread("run-collab", thread.thread_id)
    assert len(provider.requests) == 1
    assert detail["turns"][0].status == "completed"
    assert [message.role for message in detail["messages"]] == ["user", "assistant"]
    receipt = stores.operations.read(
        "run-collab",
        f"collab:{thread.thread_id}:{turn.turn_id}:1",
    )
    assert receipt.status == "succeeded"
    assert receipt.provider_input_ref
    assert stores.artifacts.read("run-collab", source.artifact_id).payload == source.payload


@pytest.mark.asyncio
@pytest.mark.parametrize("quality_mode", ("fast", "balanced"))
async def test_non_deep_modes_can_complete_the_same_multi_turn_discussion_flow(
    tmp_path,
    quality_mode: str,
) -> None:
    root = tmp_path / "runtime"
    stores, source = _deep_run(root, quality_mode=quality_mode)
    service = AuthorCollaborationService(stores)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="turn-1",
            label=f"{quality_mode} 转折",
        ),
    )
    preview_request = CollaborationContextPreviewRequest(
        client_turn_id=f"client-{quality_mode}-discussion",
        mode="discuss",
        message="请检查这处转折的因果代价。",
    )
    preview = service.preview_context("run-collab", thread.thread_id, preview_request)
    turn = service.create_turn(
        "run-collab",
        thread.thread_id,
        CreateCollaborationTurnRequest(
            **preview_request.model_dump(),
            preview_signature=preview.receipt_hash,
        ),
    )

    async with open_sqlite_runtime(root, FakeCollaborationProvider()) as runtime:
        await runtime.collaborate("run-collab", thread.thread_id, turn.turn_id)

    assert service.read_thread("run-collab", thread.thread_id)["turns"][0].status == "completed"


@pytest.mark.asyncio
async def test_execution_service_recovers_a_queued_collaboration_turn_once(tmp_path) -> None:
    root = tmp_path / "runtime"
    stores, source = _deep_run(root)
    service = AuthorCollaborationService(stores)
    thread, turn = _queued_discussion_turn(service, source.artifact_id, "client-recover-queued")
    provider = FakeCollaborationProvider()
    execution = NarrativeExecutionService(root, lambda: provider)

    await execution.recover_incomplete()
    await _wait_for_turn_terminal(stores, thread.thread_id, turn.turn_id)

    recovered = stores.collaboration.read_turn("run-collab", thread.thread_id, turn.turn_id)
    assert recovered.status == "completed"
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_recovery_persists_a_durable_provider_return_without_a_second_call(tmp_path) -> None:
    root = tmp_path / "runtime"
    stores, source = _deep_run(root)
    service = AuthorCollaborationService(stores)
    thread, turn = _queued_discussion_turn(service, source.artifact_id, "client-recover-returned")
    first_provider = FakeCollaborationProvider()
    executor = AuthorCollaborationExecutor(stores, first_provider)
    state = {
        "run_id": "run-collab",
        "collaboration_thread_id": thread.thread_id,
        "active_turn_id": turn.turn_id,
        **executor.validate_source(
            {
                "run_id": "run-collab",
                "collaboration_thread_id": thread.thread_id,
                "active_turn_id": turn.turn_id,
            }
        ),
    }
    state.update(await executor.call_provider(state))
    assert stores.collaboration.read_turn(
        "run-collab", thread.thread_id, turn.turn_id
    ).status == "streaming"

    recovery_provider = FakeCollaborationProvider()
    execution = NarrativeExecutionService(root, lambda: recovery_provider)
    await execution.recover_incomplete()
    await _wait_for_turn_terminal(stores, thread.thread_id, turn.turn_id)

    recovered = stores.collaboration.read_turn("run-collab", thread.thread_id, turn.turn_id)
    assert recovered.status == "completed"
    assert len(first_provider.requests) == 1
    assert recovery_provider.requests == []


@pytest.mark.asyncio
async def test_recovery_never_retries_a_provider_call_with_an_unknown_outcome(tmp_path) -> None:
    root = tmp_path / "runtime"
    stores, source = _deep_run(root)
    service = AuthorCollaborationService(stores)
    thread, turn = _queued_discussion_turn(service, source.artifact_id, "client-recover-unknown")
    blocking_provider = BlockingCollaborationProvider()
    executor = AuthorCollaborationExecutor(stores, blocking_provider)
    state = {
        "run_id": "run-collab",
        "collaboration_thread_id": thread.thread_id,
        "active_turn_id": turn.turn_id,
        **executor.validate_source(
            {
                "run_id": "run-collab",
                "collaboration_thread_id": thread.thread_id,
                "active_turn_id": turn.turn_id,
            }
        ),
    }
    provider_task = asyncio.create_task(executor.call_provider(state))
    await blocking_provider.started.wait()
    provider_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await provider_task

    recovery_provider = FakeCollaborationProvider()
    execution = NarrativeExecutionService(root, lambda: recovery_provider)
    await execution.recover_incomplete()

    recovered = stores.collaboration.read_turn("run-collab", thread.thread_id, turn.turn_id)
    operation = stores.operations.read(
        "run-collab",
        recovered.provider_operation_ref,
    )
    assert recovered.status == "failed"
    assert recovered.error["code"] == "provider_outcome_unknown"
    assert operation.status == "failed"
    assert recovery_provider.requests == []


@pytest.mark.asyncio
async def test_revise_produces_selection_bound_patch_without_automatic_writeback(tmp_path) -> None:
    root = tmp_path / "runtime"
    stores, source = _deep_run(root)
    service = AuthorCollaborationService(stores)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="turn-1",
            label="转折一",
        ),
    )
    original = str(source.payload["turns"][0]["change"])
    selection = SelectionAnchor(
        anchor_id="anchor-turn-1-change",
        stage_id="spine",
        source_ref=source.artifact_id,
        unit_ref="turn-1",
        field_path="turns.0.change",
        field_hash=_digest(original),
        selection_start=0,
        selection_end=len(original),
        selected_text_hash=_digest(original),
        selected_char_count=len(original),
        preview=f"{original[:16]}...",
        selected_text=original,
        created_at="2026-08-21T00:00:00+00:00",
    )
    preview_request = CollaborationContextPreviewRequest(
        client_turn_id="client-revise-1",
        mode="revise",
        message="把这个变化写得更具体，并体现公开代价。",
        selection=selection,
    )
    preview = service.preview_context("run-collab", thread.thread_id, preview_request)
    turn = service.create_turn(
        "run-collab",
        thread.thread_id,
        CreateCollaborationTurnRequest(
            **preview_request.model_dump(),
            preview_signature=preview.receipt_hash,
        ),
    )
    provider = FakeCollaborationProvider()
    async with open_sqlite_runtime(root, provider) as runtime:
        await runtime.collaborate("run-collab", thread.thread_id, turn.turn_id)

    patch = stores.collaboration.list_patches(
        "run-collab",
        thread_id=thread.thread_id,
    )[0]
    assert patch.status == "proposed"
    assert patch.operations[0].before_hash == selection.selected_text_hash
    assert stores.artifacts.read("run-collab", source.artifact_id).payload == source.payload
    with pytest.raises(PatchWritebackUnavailable):
        service.accept_patch("run-collab", patch.patch_id)
    assert stores.collaboration.read_patch("run-collab", patch.patch_id).status == "proposed"


@pytest.mark.asyncio
async def test_all_five_collaboration_stages_complete_through_the_shared_graph(
    tmp_path,
) -> None:
    root = tmp_path / "runtime"
    stores, stage_sources = _deep_run_with_all_collaboration_stages(root)
    service = AuthorCollaborationService(stores)
    provider = FakeCollaborationProvider()
    stage_scopes = {
        "spine": ("turn-1", "起始转折"),
        "cast": ("subject-1", "林远"),
        "volumes": ("volume-1", "明日旧案"),
        "detail": ("chapter-1", "明日号码"),
        "text": ("chapter-1", "明日号码正文"),
    }

    async with open_sqlite_runtime(root, provider) as runtime:
        for index, (stage_id, (unit_ref, label)) in enumerate(
            stage_scopes.items(),
            start=1,
        ):
            source = stage_sources[stage_id]
            thread = service.create_thread(
                "run-collab",
                CreateCollaborationThreadRequest(
                    stage_id=stage_id,
                    source_ref=source,
                    unit_ref=unit_ref,
                    label=label,
                ),
            )
            preview_request = CollaborationContextPreviewRequest(
                client_turn_id=f"client-stage-{index}",
                mode="discuss",
                message=f"请检查{label}是否忠实承接当前阶段与上游约束。",
            )
            preview = service.preview_context(
                "run-collab",
                thread.thread_id,
                preview_request,
            )
            turn = service.create_turn(
                "run-collab",
                thread.thread_id,
                CreateCollaborationTurnRequest(
                    **preview_request.model_dump(),
                    preview_signature=preview.receipt_hash,
                ),
            )

            await runtime.collaborate("run-collab", thread.thread_id, turn.turn_id)

            detail = service.read_thread("run-collab", thread.thread_id)
            assert detail["turns"][0].status == "completed"
            assert [message.role for message in detail["messages"]] == [
                "user",
                "assistant",
            ]
            assert preview.source_artifact_ref == source
            assert any(item.category == "artifact" for item in preview.sources)

    assert [request.stage_id for request in provider.requests] == list(stage_scopes)
    assert len(
        {
            request.context_receipt_ref
            for request in provider.requests
        }
    ) == len(stage_scopes)


def test_text_context_uses_scoped_story_state_and_explicit_omissions(tmp_path) -> None:
    stores, stage_sources = _deep_run_with_all_collaboration_stages(
        tmp_path / "runtime"
    )
    stores.canon.commit(
        "run-collab",
        "canon-phase31-context",
        [
            CanonFact(
                fact_id="fact-lin-recording",
                claim="林远已确认未来报警录音包含未公开的事故地址。",
                evidence_refs=["evidence-chapter-1-lin"],
                chapter_version_id="chapter-1-v1-accepted",
                subject_id="subject-1",
                property_key="knowledge.future-call",
                value="confirmed",
                effective_from_chapter=1,
            ),
            CanonFact(
                fact_id="fact-unrelated-recording",
                claim="无关角色掌握另一座城市的广播记录。",
                evidence_refs=["evidence-unrelated"],
                chapter_version_id="chapter-1-v1-accepted",
                subject_id="subject-unrelated",
                property_key="knowledge.other-city",
                value="confirmed",
                effective_from_chapter=1,
            ),
        ],
    )
    service = AuthorCollaborationService(stores)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="text",
            source_ref=stage_sources["text"],
            unit_ref="chapter-1",
            label="明日号码正文",
        ),
    )
    envelope = service.context.compile_preview(
        thread,
        CollaborationContextPreviewRequest(
            client_turn_id="client-scoped-story-state",
            mode="discuss",
            message="这段正文是否遵守已确认事实？",
            context_policy=CollaborationContextPolicy(
                include_canon_wiki=True,
                include_foreshadow=False,
            ),
        ),
    )

    assert "continuity_state" in envelope.material
    assert "canon_wiki" in envelope.material
    assert "fact-lin-recording" in envelope.material["canon_wiki"]
    assert "fact-unrelated-recording" not in envelope.material["canon_wiki"]
    foreshadow = next(
        item for item in envelope.receipt.sources if item.category == "foreshadow"
    )
    assert foreshadow.disposition == "omitted"
    assert foreshadow.char_count == 0


def test_explicit_knowledge_source_pack_is_receipted_and_project_scoped(tmp_path) -> None:
    stores, source = _deep_run(tmp_path / "runtime")
    knowledge = KnowledgeBase(tmp_path / "knowledge")
    uploaded = knowledge.upload(
        title="母带保管规范",
        content="母带保管规范要求公开播放前核验来源、保管链与登记时间。".encode(),
        filename="archive-rules.txt",
        project_id="project-1",
    )
    service = AuthorCollaborationService(stores, knowledge_base=knowledge)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="turn-1",
            label="转折一",
        ),
    )
    request = CollaborationContextPreviewRequest(
        client_turn_id="client-knowledge-source-pack",
        mode="discuss",
        message="母带保管规范如何约束公开播放？",
        context_policy=CollaborationContextPolicy(
            include_knowledge=True,
            source_pack_refs=[uploaded.document.doc_id],
        ),
    )

    envelope = service.context.compile_preview(thread, request)

    knowledge_sources = [
        item
        for item in envelope.receipt.sources
        if item.category == "knowledge" and item.disposition == "optional"
    ]
    assert knowledge_sources
    assert all(item.scope_ref == uploaded.document.doc_id for item in knowledge_sources)
    assert "母带保管规范" in "\n".join(
        value for key, value in envelope.material.items() if key.startswith("knowledge_")
    )

    with pytest.raises(CollaborationContextError, match="unavailable for this project"):
        service.context.compile_preview(
            thread,
            request.model_copy(
                update={
                    "client_turn_id": "client-unknown-source-pack",
                    "context_policy": request.context_policy.model_copy(
                        update={"source_pack_refs": ["kb-other-project"]}
                    ),
                }
            ),
        )


def test_context_requires_rebase_after_source_version_changes(tmp_path) -> None:
    stores, source = _deep_run(tmp_path / "runtime")
    service = AuthorCollaborationService(stores)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="turn-1",
        ),
    )
    changed = {**source.payload, "ending": "主角公开真相，也失去继续修复公共档案的资格。"}
    stores.artifacts.save_candidate(
        "run-collab",
        "spine",
        changed,
        source="new-candidate",
    )

    with pytest.raises(CollaborationSourceStale):
        service.preview_context(
            "run-collab",
            thread.thread_id,
            CollaborationContextPreviewRequest(
                client_turn_id="client-stale",
                message="继续讨论旧转折。",
            ),
        )


def test_context_budget_never_silently_truncates_required_material(tmp_path) -> None:
    stores, source = _deep_run(tmp_path / "runtime")
    service = AuthorCollaborationService(stores)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="turn-1",
        ),
    )
    with pytest.raises(CollaborationContextBudgetExceeded):
        service.preview_context(
            "run-collab",
            thread.thread_id,
            CollaborationContextPreviewRequest(
                client_turn_id="client-budget",
                message="请分析" + "因果与代价" * 780,
                context_policy=CollaborationContextPolicy(max_input_chars=4_000),
            ),
        )


def test_collaboration_rejects_structural_and_identity_field_paths(tmp_path) -> None:
    stores, source = _deep_run(tmp_path / "runtime")
    service = AuthorCollaborationService(stores)

    with pytest.raises(CollaborationFieldNotEditable):
        service.create_thread(
            "run-collab",
            CreateCollaborationThreadRequest(
                stage_id="spine",
                source_ref=source.artifact_id,
                unit_ref="turn-1",
                field_path="turns.0.id",
            ),
        )

    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="turn-1",
        ),
    )
    value = str(source.payload["turns"][0]["id"])
    selection = SelectionAnchor(
        anchor_id="anchor-identity-field",
        stage_id="spine",
        source_ref=source.artifact_id,
        unit_ref="turn-1",
        field_path="turns.0.id",
        field_hash=_digest(value),
        selection_start=0,
        selection_end=len(value),
        selected_text_hash=_digest(value),
        selected_char_count=len(value),
        preview=value,
        selected_text=value,
        created_at="2026-08-21T00:00:00+00:00",
    )

    with pytest.raises(CollaborationFieldNotEditable):
        service.preview_context(
            "run-collab",
            thread.thread_id,
            CollaborationContextPreviewRequest(
                client_turn_id="client-identity-field",
                mode="revise",
                message="把这个 ID 改掉。",
                selection=selection,
            ),
        )


@pytest.mark.asyncio
async def test_selection_and_patch_bind_to_the_current_pending_draft(tmp_path) -> None:
    stores, source = _deep_run(tmp_path / "runtime")
    current = stores.runs.read("run-collab")
    decision_id = f"run-collab:spine:{source.artifact_id}"
    stores.runs.project(
        "run-collab",
        current.model_copy(
            update={
                "active_stage_id": "spine",
                "status": "awaiting_decision",
                "stage_status": {**current.stage_status, "spine": "awaiting_decision"},
                "pending_decisions": [
                    {
                        "type": "stage_artifact_decision",
                        "decision_id": decision_id,
                        "thread_id": "run-collab",
                        "node_id": "spine.human_decision",
                        "artifact_ref": source.artifact_id,
                        "domain_revision": 0,
                        "allowed_actions": ["accept", "regenerate", "cancel"],
                    }
                ],
            }
        ),
    )
    edited = {
        **source.payload,
        "ending": "主角公开母带，也公开自己的违规修复记录。",
        "open_questions": ["未来电话是否仍会继续？"],
    }
    save_stage_artifact_draft(
        stores,
        run_id="run-collab",
        decision_id=decision_id,
        domain_revision=0,
        source_artifact_id=source.artifact_id,
        artifact=edited,
    )
    service = AuthorCollaborationService(stores)
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source.artifact_id,
            unit_ref="artifact",
        ),
    )
    selected = str(edited["ending"])
    selection = SelectionAnchor(
        anchor_id="anchor-edited-ending",
        stage_id="spine",
        source_ref=source.artifact_id,
        unit_ref="artifact",
        field_path="ending",
        field_hash=_digest(selected),
        selection_start=0,
        selection_end=len(selected),
        selected_text_hash=_digest(selected),
        selected_char_count=len(selected),
        preview=selected,
        selected_text=selected,
        created_at="2026-08-21T00:00:00+00:00",
    )

    request = CollaborationContextPreviewRequest(
        client_turn_id="client-current-draft",
        mode="revise",
        message="收紧结局表达。",
        selection=selection,
    )
    receipt = service.preview_context(
        "run-collab",
        thread.thread_id,
        request,
    )

    assert receipt.source_artifact_ref == source.artifact_id
    assert next(item for item in receipt.sources if item.category == "selection").source_version == _digest(selected)
    turn = service.create_turn(
        "run-collab",
        thread.thread_id,
        CreateCollaborationTurnRequest(
            **request.model_dump(),
            preview_signature=receipt.receipt_hash,
        ),
    )
    async with open_sqlite_runtime(tmp_path / "runtime", FakeCollaborationProvider()) as runtime:
        await runtime.collaborate("run-collab", thread.thread_id, turn.turn_id)
    patch = stores.collaboration.list_patches(
        "run-collab",
        thread_id=thread.thread_id,
    )[0]

    accepted = service.accept_patch("run-collab", patch.patch_id)

    current_draft = load_stage_artifact_draft(
        stores,
        run_id="run-collab",
        decision_id=decision_id,
    )
    assert accepted.status == "accepted"
    assert current_draft is not None
    assert current_draft.payload["ending"] == (
        "主角公开母带来源，并承担档案修复资格被撤销的后果"
    )
    assert current_draft.payload["open_questions"] == ["未来电话是否仍会继续？"]


def _deep_run(root, *, quality_mode: str = "deep"):
    stores = filesystem_stores(root)
    scale = NarrativeScaleProfile(word_target_soft=4_000)
    stores.runs.create(
        run_id="run-collab",
        project_id="project-1",
        workflow_id=f"workflow-{quality_mode}",
        workflow_revision="phase31",
        workflow_digest="a" * 64,
        quality_mode=quality_mode,
        inputs={"genre": "悬疑"},
        scale_profile=scale,
        hierarchical_scale_plan=plan_hierarchical_narrative_scale(
            scale,
            quality_mode=quality_mode,
        ),
        provider_bindings=_bindings(),
        cover_asset_binding=cover_asset_binding(),
        export_preferences=ExportPreferences(format="zip"),
    )
    source = stores.artifacts.save_candidate(
        "run-collab",
        "spine",
        _spine(),
        source="phase31-test",
    )
    return stores, source


def _queued_discussion_turn(
    service: AuthorCollaborationService,
    source_ref: str,
    client_turn_id: str,
):
    thread = service.create_thread(
        "run-collab",
        CreateCollaborationThreadRequest(
            stage_id="spine",
            source_ref=source_ref,
            unit_ref="turn-1",
            label="转折一",
        ),
    )
    preview_request = CollaborationContextPreviewRequest(
        client_turn_id=client_turn_id,
        mode="discuss",
        message="请检查这处转折的因果代价。",
    )
    preview = service.preview_context(
        "run-collab",
        thread.thread_id,
        preview_request,
    )
    turn = service.create_turn(
        "run-collab",
        thread.thread_id,
        CreateCollaborationTurnRequest(
            **preview_request.model_dump(),
            preview_signature=preview.receipt_hash,
        ),
    )
    return thread, turn


async def _wait_for_turn_terminal(stores, thread_id: str, turn_id: str) -> None:
    for _ in range(200):
        turn = stores.collaboration.read_turn("run-collab", thread_id, turn_id)
        if turn.status not in {"queued", "streaming"}:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Collaboration turn did not reach a terminal state")


def _deep_run_with_all_collaboration_stages(root):
    stores, _ = _deep_run(root)
    brief = stores.artifacts.commit(
        "run-collab",
        "brief",
        contract_brief(),
        source="phase31-five-stage-fixture",
    )
    spine = stores.artifacts.commit(
        "run-collab",
        "spine",
        contract_spine(),
        source="phase31-five-stage-fixture",
    )
    cast = stores.artifacts.commit(
        "run-collab",
        "cast",
        contract_cast(),
        source="phase31-five-stage-fixture",
        chapter_target=3,
    )
    volumes = stores.artifacts.commit(
        "run-collab",
        "volumes",
        contract_volumes(),
        source="phase31-five-stage-fixture",
        subject_ids={"subject-1"},
        turn_ids={"turn-1", "turn-2", "turn-3"},
    )
    detail = stores.artifacts.commit(
        "run-collab",
        "detail",
        contract_detail(),
        source="phase31-five-stage-fixture",
        subject_ids={"subject-1"},
        chapter_refs={"chapter-1", "chapter-2", "chapter-3"},
        chapter_turn_refs={
            "chapter-1": ["turn-1"],
            "chapter-2": ["turn-2"],
            "chapter-3": ["turn-3"],
        },
        volume_cast_ids={"volume-1": {"subject-1"}},
    )
    chapter = stores.chapters.write(
        "run-collab",
        {
            "chapter_id": "chapter-1",
            "version_id": "chapter-1-v1-accepted",
            "title": "明日号码",
            "content": "林远按下回放键，尚未发生的事故地址再次从耳机里传来。",
            "author_status": "accepted",
        },
    )
    return stores, {
        "spine": spine.artifact_id,
        "cast": cast.artifact_id,
        "volumes": volumes.artifact_id,
        "detail": detail.artifact_id,
        "text": chapter.version_id,
        "brief": brief.artifact_id,
    }


def _bindings() -> dict[str, ProviderBinding]:
    return {
        stage: provider_binding(stage)
        for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
    }


def _spine() -> dict[str, object]:
    return {
        "turns": [
            {
                "id": "turn-1",
                "cause": "旧档案母带出现一段未登记的人声",
                "change": "主角确认有人主动删除事故证言",
                "progress_type": "information",
                "milestones": ["inciting", "commitment"],
            },
            {
                "id": "turn-2",
                "cause": "删除签名指向主角信任的修复导师",
                "change": "主角必须在保护导师和公开证据之间选择",
                "progress_type": "relationship",
                "milestones": ["midpoint_reversal", "crisis", "climax"],
            },
            {
                "id": "turn-3",
                "cause": "公开听证要求主角提交自己的违规修复记录",
                "change": "事故真相公开，主角承担职业资格被撤销的后果",
                "progress_type": "external",
                "milestones": ["aftermath"],
            },
        ],
        "ending": "主角公开母带和自己的违规记录，让事故责任得到确认。",
        "open_questions": ["导师为何在最后时刻保留母带副本？"],
        "progress_types": ["information", "relationship", "external"],
    }


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

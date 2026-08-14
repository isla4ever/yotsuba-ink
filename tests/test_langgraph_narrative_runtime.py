from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.output_contracts.artifacts_vnext import (
    ContextManifest,
    RoleDemandProposalBatch,
    StoryBriefArtifact,
    StorySpineArtifact,
    VolumeBoundaryProposalBatch,
    validate_artifact_vnext,
)
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterReviewRequest,
    ChapterReviewResult,
    PlainTextProviderResult,
    StructuredProviderResult,
)
from novel_workflow.runtime.graph.branch_service import NarrativeBranchService
from novel_workflow.runtime.graph.runtime import (
    NarrativeRuntime,
    decision_operation_key,
    filesystem_stores,
    open_sqlite_runtime,
)
from novel_workflow.storage.narrative_run_repository import (
    ExportPreferences,
    ProviderBinding,
)
from novel_workflow.workflows.narrative_scale import (
    NarrativeScaleProfile,
    count_prose_characters,
)
from tests.fakes import FakeNarrativeProvider
from tests.phase27_bindings import cover_asset_binding, provider_binding


class InterruptingReviewProvider(FakeNarrativeProvider):
    def __init__(self) -> None:
        super().__init__()
        self._review_started = {
            "continuity": asyncio.Event(),
            "character": asyncio.Event(),
        }
        self._stop_once = True

    async def review_chapter(
        self,
        request: ChapterReviewRequest,
    ) -> StructuredProviderResult:
        self.review_requests.append(request)
        if request.chapter_id == "chapter-1" and request.role in self._review_started:
            self._review_started[request.role].set()
        if request.chapter_id == "chapter-1" and request.role == "prose" and self._stop_once:
            await asyncio.gather(*(event.wait() for event in self._review_started.values()))
            await asyncio.sleep(0)
            self._stop_once = False
            raise SimulatedProcessStop("process stopped during parallel review")
        return StructuredProviderResult(
            payload=ChapterReviewResult(role=request.role).model_dump(mode="json"),
            usage={"total_tokens": 1},
        )


class SimulatedProcessStop(BaseException):
    pass


def _bindings() -> dict[str, ProviderBinding]:
    return {
        stage: provider_binding(stage)
        for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
    }


def _create_run(stores: Any, run_id: str, *, quality_mode: str = "fast") -> None:
    stores.runs.create(
        run_id=run_id,
        project_id="project-1",
        workflow_id="workflow-1",
        workflow_revision="phase27-vnext",
        workflow_digest="a" * 64,
        quality_mode=quality_mode,
        inputs={"project_brief": {"genre": "悬疑"}},
        scale_profile=NarrativeScaleProfile(word_target_soft=4_000, chapter_target_soft=2),
        provider_bindings=_bindings(),
        cover_asset_binding=cover_asset_binding(),
        export_preferences=ExportPreferences(format="zip"),
    )


async def _advance_to_first_chapter(
    runtime: NarrativeRuntime,
    run_id: str,
):
    projection = await runtime.start(run_id)
    while (
        projection.pending_decisions
        and projection.pending_decisions[0]["type"] == "stage_artifact_decision"
    ):
        decision = dict(projection.pending_decisions[0])
        projection = await runtime.resume(
            run_id,
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )
    assert projection.status == "awaiting_decision", projection.failure
    assert projection.pending_decisions[0]["type"] == "chapter_author_decision"
    assert projection.pending_decisions[0]["chapter_id"] == "chapter-1"
    assert projection.active_chapter_number == 1
    return projection


def test_proposal_batches_are_strict_and_turn_refs_are_validated_at_graph_boundary() -> None:
    role = RoleDemandProposalBatch.model_validate({"proposals": [{"demand_key": "demand-a", "function": "取证", "required_change": "作证", "active_turn_refs": ["turn-1"]}]})
    assert role.proposals[0].demand_key == "demand-a"
    boundary = VolumeBoundaryProposalBatch.model_validate({"proposals": [{"boundary_key": "boundary-1", "turn_refs": ["turn-x"], "reason": "bad"}]})
    assert boundary.proposals[0].turn_refs == ["turn-x"]


def test_scale_profile_rejects_retired_reasonable_bounds() -> None:
    profile = NarrativeScaleProfile(chapter_target_soft=2)
    assert profile.chapter_target_soft == 2
    with pytest.raises(ValueError):
        NarrativeScaleProfile.model_validate({"chapter_target_soft": 8, "chapter_min_reasonable": 1})


def test_context_manifest_hash_and_forbidden_sections_are_explicit() -> None:
    text = "chapter script"
    source_hash = hashlib.sha256(text.encode()).hexdigest()
    payload = {"task": "chapter-1", "required": ["detail.chapter"], "optional": [], "forbidden": ["full_canon"], "snippets": [{"ref": "detail.chapter", "purpose": "script", "text": text, "source_hash": source_hash}], "budget": {"input_chars": len(text), "output_tokens": 100}}
    payload["manifest_hash"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = ContextManifest.model_validate(payload)
    assert manifest.forbidden == ["full_canon"]
    with pytest.raises(ValueError, match="source hash"):
        ContextManifest.model_validate({**payload, "snippets": [{**payload["snippets"][0], "text": "tampered"}]})


@pytest.mark.asyncio
async def test_langgraph_phase27_fast_run_uses_proposals_and_plaintext_chapters(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-phase27")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await runtime.start("run-phase27")
    assert projection.status == "completed", projection.failure
    assert [request.stage_id for request in provider.stage_requests] == ["brief", "spine", "cast", "volumes", "detail", "cover"]
    assert [request.proposal_type for request in provider.proposal_requests] == ["role_demand", "cast_relation", "volume_boundary"]
    assert [request.chapter_id for request in provider.chapter_requests] == ["chapter-1", "chapter-2"]
    manifests = stores.context_manifests.list("run-phase27")
    assert [(item.chapter_id, item.attempt) for item in manifests] == [
        ("chapter-1", 1),
        ("chapter-2", 1),
    ]
    assert all(
        set(request.context["material"]) == {"chapter_context_manifest"}
        for request in provider.chapter_requests
    )
    assert all(
        request.context["material"]["chapter_context_manifest"]["manifest_hash"]
        in {item.manifest.manifest_hash for item in manifests}
        for request in provider.chapter_requests
    )
    # Sequential chapters must see the previous accepted ending, not only the
    # planned one-line handoff, so prose time/place/knowledge state continues.
    second_manifest = provider.chapter_requests[1].context["material"]["chapter_context_manifest"]
    ending_snippets = [
        item for item in second_manifest["snippets"] if item["ref"] == "previous.ending_excerpt"
    ]
    assert len(ending_snippets) == 1
    accepted_first = stores.chapters.read(
        "run-phase27", "chapter-1", "chapter-1-v1-accepted"
    ).artifact.content
    assert accepted_first.strip().endswith(ending_snippets[0]["text"][-40:])
    # Canon facts committed from accepted chapters must bind later prose.
    canon_snippets = [
        item for item in second_manifest["snippets"] if item["ref"] == "canon.established_facts"
    ]
    assert len(canon_snippets) == 1
    assert "本章完成施工图目标" in canon_snippets[0]["text"]
    assert sorted(
        (request.chapter_id, request.role) for request in provider.review_requests
    ) == sorted(
        (chapter_id, role)
        for chapter_id in ("chapter-1", "chapter-2")
        for role in ("character", "continuity", "prose")
    )
    assert [request.chapter_id for request in provider.evidence_requests] == ["chapter-1", "chapter-2"]
    assert [request.candidate_index for request in provider.cover_requests] == [1]
    detail = stores.artifacts.latest("run-phase27", "detail").payload
    assert [item["ref"] for item in detail["chapters"]] == ["chapter-1", "chapter-2"]
    assert [item["title"] for item in detail["chapters"]] == ["母带残响1", "母带残响2"]
    assert [item["target_characters"] for item in detail["chapters"]] == [2_000, 2_000]
    accepted_chapters = [
        stores.chapters.read("run-phase27", item["ref"], f"{item['ref']}-v1-accepted").artifact
        for item in detail["chapters"]
    ]
    assert [chapter.title for chapter in accepted_chapters] == ["母带残响1", "母带残响2"]
    assert [count_prose_characters(chapter.content) for chapter in accepted_chapters] == [2_000, 2_000]
    assert stores.artifacts.latest("run-phase27", "export").payload["chapter_version_ids"] == ["chapter-1-v1-accepted", "chapter-2-v1-accepted"]
    candidate_stages = {
        event.stage_id
        for event in stores.events.read("run-phase27")
        if event.type == "artifact.candidate_ready"
    }
    assert candidate_stages == {
        "brief",
        "spine",
        "cast",
        "volumes",
        "detail",
        "text",
        "cover",
        "export",
    }
    assert len(stores.evidence.list("run-phase27")) == 2
    assert len(stores.canon.facts("run-phase27")) == 2
    assert len(stores.wiki.list("run-phase27")) == 2
    assert stores.outbox.read(
        "run-phase27", "outbox-chapter-1-chapter-1-v1-accepted"
    ).status == "committed"
    assert stores.outbox.read(
        "run-phase27", "outbox-chapter-2-chapter-2-v1-accepted"
    ).status == "committed"
    assert len(stores.cover_assets.list("run-phase27")) == 1
    assert len(stores.exports.list("run-phase27")) == 1


@pytest.mark.asyncio
async def test_chapter_length_violation_triggers_a_complete_rewrite(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate = provider.generate_chapter
    returned_short_draft = False

    async def generate_short_once(request):
        nonlocal returned_short_draft
        if request.chapter_id == "chapter-1" and not returned_short_draft:
            returned_short_draft = True
            provider.chapter_requests.append(request)
            return PlainTextProviderResult(content="过短初稿", usage={"total_tokens": 1})
        return await original_generate(request)

    provider.generate_chapter = generate_short_once
    _create_run(stores, "run-length-rewrite")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-length-rewrite")

    assert projection.status == "completed", projection.failure
    assert [request.chapter_id for request in provider.chapter_requests] == [
        "chapter-1",
        "chapter-1",
        "chapter-2",
    ]
    manifests = stores.context_manifests.list("run-length-rewrite")
    assert [(item.chapter_id, item.attempt) for item in manifests[:2]] == [
        ("chapter-1", 1),
        ("chapter-1", 2),
    ]
    revision = next(
        snippet
        for snippet in manifests[1].manifest.snippets
        if snippet.ref == "revision.request"
    )
    assert "完整重写本章" in revision.text
    assert "2000 字" in revision.text
    accepted = stores.chapters.read(
        "run-length-rewrite", "chapter-1", "chapter-1-v2-accepted"
    ).artifact
    assert accepted.title == "母带残响1"
    assert count_prose_characters(accepted.content) == 2_000


@pytest.mark.asyncio
async def test_chapter_length_fails_after_three_out_of_range_drafts(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()

    async def generate_short(request):
        provider.chapter_requests.append(request)
        return PlainTextProviderResult(content="始终过短", usage={"total_tokens": 1})

    provider.generate_chapter = generate_short
    _create_run(stores, "run-length-failure")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-length-failure")

    assert projection.status == "failed"
    assert projection.failure["node_id"] == "text.check_length_contract"
    assert "after 3 attempts" in projection.failure["message"]
    assert [request.chapter_id for request in provider.chapter_requests] == [
        "chapter-1",
        "chapter-1",
        "chapter-1",
    ]


@pytest.mark.asyncio
async def test_fast_run_projects_live_read_model_between_checkpoints(tmp_path) -> None:
    """Fast mode never interrupts, so the read model must be projected from
    super-step checkpoints mid-run — otherwise state polling and the monitor
    console see `created` until the whole run finishes."""
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_stage = provider.generate_stage
    observed: list[Any] = []

    async def generate_stage_with_probe(request):
        if request.stage_id == "detail":
            observed.append(stores.runs.read("run-live-projection"))
        return await original_generate_stage(request)

    provider.generate_stage = generate_stage_with_probe
    _create_run(stores, "run-live-projection")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await runtime.start("run-live-projection")

    assert projection.status == "completed", projection.failure
    assert observed, "detail stage probe never ran"
    mid_run = observed[0]
    assert mid_run.status == "running"
    assert mid_run.stage_status["brief"] == "completed"
    assert mid_run.active_stage_id not in ("", "brief")


@pytest.mark.asyncio
async def test_stage_unit_contract_violation_triggers_one_repair_retry(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_stage = provider.generate_stage
    broken_once = {"done": False}

    async def generate_stage_with_bad_kind(request):
        result = await original_generate_stage(request)
        if request.stage_id == "cast" and not broken_once["done"]:
            broken_once["done"] = True
            payload = json.loads(json.dumps(result.payload))
            payload["subjects"][0]["kind"] = "antagonist"
            return result.model_copy(update={"payload": payload})
        return result

    provider.generate_stage = generate_stage_with_bad_kind
    _create_run(stores, "run-contract-repair")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await runtime.start("run-contract-repair")

    assert projection.status == "completed", projection.failure
    cast_keys = [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "cast"
    ]
    assert len(cast_keys) == 2
    assert cast_keys[1] == f"{cast_keys[0]}:repair-1"
    repair_request = next(
        request
        for request in provider.stage_requests
        if request.operation_key.endswith(":repair-1")
    )
    assert "antagonist" in str(
        repair_request.context["contract_repair"]["previous_attempt_error"]
    )
    assert stores.operations.read("run-contract-repair", cast_keys[0]).status == "failed"
    assert stores.operations.read("run-contract-repair", cast_keys[1]).status == "succeeded"


@pytest.mark.asyncio
async def test_guarded_failure_appends_terminal_run_failed_event(tmp_path) -> None:
    """SSE observers must see exactly one terminal event when the graph halts.

    `derive_cast_demand` failures previously ended the graph without any
    run.failed event, leaving live monitors showing an auto-advancing run.
    """
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()

    async def generate_proposal_always_invalid(request):
        raise ProviderResponseError("unauthorized", "Provider rejected the API key")

    provider.generate_proposal = generate_proposal_always_invalid
    _create_run(stores, "run-halt-event")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await runtime.start("run-halt-event")

    assert projection.status == "failed"
    terminal = [
        event for event in stores.events.read("run-halt-event") if event.type == "run.failed"
    ]
    assert len(terminal) == 1
    assert terminal[0].payload["node_id"] == "spine.derive_cast_demand"
    assert "rejected the API key" in terminal[0].payload["message"]


@pytest.mark.asyncio
async def test_stage_unit_transient_network_error_retries_and_completes(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_stage = provider.generate_stage
    dropped_once = {"done": False}

    async def generate_stage_with_one_network_drop(request):
        if request.stage_id == "brief" and not dropped_once["done"]:
            dropped_once["done"] = True
            raise ProviderResponseError(
                "network_error", "Provider network error: APIConnectionError"
            )
        return await original_generate_stage(request)

    provider.generate_stage = generate_stage_with_one_network_drop
    _create_run(stores, "run-network-retry")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await runtime.start("run-network-retry")

    assert projection.status == "completed", projection.failure
    # The dropped first attempt never reached the fake's request log; the
    # successful retry ran under a distinct :net-1 operation key while the
    # original key kept its failed receipt for the audit trail.
    brief_keys = [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "brief"
    ]
    assert brief_keys == ["run-network-retry:brief:generate:1:net-1"]
    original = stores.operations.read(
        "run-network-retry", "run-network-retry:brief:generate:1"
    )
    assert original.status == "failed"
    retried = stores.operations.read(
        "run-network-retry", "run-network-retry:brief:generate:1:net-1"
    )
    assert retried.status == "succeeded"


@pytest.mark.asyncio
async def test_provider_receipt_replays_after_process_stop_without_duplicate_call(
    tmp_path,
    monkeypatch,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-provider-replay")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    original_write = stores.chapters.write
    stopped = False

    def stop_after_provider_receipt(run_id, payload):
        nonlocal stopped
        if not stopped and payload.get("author_status") == "candidate":
            stopped = True
            raise SimulatedProcessStop("process stopped after Provider receipt")
        return original_write(run_id, payload)

    monkeypatch.setattr(stores.chapters, "write", stop_after_provider_receipt)
    with pytest.raises(SimulatedProcessStop, match="after Provider receipt"):
        await runtime.start("run-provider-replay")

    receipt = stores.operations.read(
        "run-provider-replay",
        "run-provider-replay:chapter-1:generate:1",
    )
    assert receipt.status == "succeeded"
    assert [request.operation_key for request in provider.chapter_requests] == [
        "run-provider-replay:chapter-1:generate:1"
    ]

    monkeypatch.setattr(stores.chapters, "write", original_write)
    recovered = await runtime.recover("run-provider-replay")

    assert recovered.status == "completed", recovered.failure
    assert [request.operation_key for request in provider.chapter_requests] == [
        "run-provider-replay:chapter-1:generate:1",
        "run-provider-replay:chapter-2:generate:1",
    ]


@pytest.mark.asyncio
async def test_parallel_review_recovery_calls_only_the_unfinished_lane(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = InterruptingReviewProvider()
    _create_run(stores, "run-review-replay")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    with pytest.raises(SimulatedProcessStop, match="parallel review"):
        await runtime.start("run-review-replay")

    chapter_one_keys = {
        role: f"run-review-replay:chapter-1:review:chapter-1-v1:{role}"
        for role in ("continuity", "character", "prose")
    }
    assert stores.operations.read(
        "run-review-replay", chapter_one_keys["continuity"]
    ).status == "succeeded"
    assert stores.operations.read(
        "run-review-replay", chapter_one_keys["character"]
    ).status == "succeeded"
    assert stores.operations.read(
        "run-review-replay", chapter_one_keys["prose"]
    ).status == "pending"

    recovered = await runtime.recover("run-review-replay")

    assert recovered.status == "completed", recovered.failure
    chapter_one_calls = [
        request.operation_key
        for request in provider.review_requests
        if request.chapter_id == "chapter-1"
    ]
    assert chapter_one_calls.count(chapter_one_keys["continuity"]) == 1
    assert chapter_one_calls.count(chapter_one_keys["character"]) == 1
    assert chapter_one_calls.count(chapter_one_keys["prose"]) == 2
    assert all(
        stores.operations.read("run-review-replay", operation_key).status == "succeeded"
        for operation_key in chapter_one_keys.values()
    )


@pytest.mark.asyncio
async def test_completed_projection_rebuilds_from_graph_without_provider_calls(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-projection-rebuild")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    completed = await runtime.start("run-projection-rebuild")
    call_count = sum(
        len(items)
        for items in (
            provider.stage_requests,
            provider.proposal_requests,
            provider.chapter_requests,
            provider.review_requests,
            provider.evidence_requests,
            provider.cover_requests,
        )
    )
    stores.runs.project(
        "run-projection-rebuild",
        completed.model_copy(
            update={
                "status": "created",
                "active_stage_id": "brief",
                "artifact_refs": {},
                "checkpoint_id": "",
            }
        ),
    )

    rebuilt = await runtime.refresh_projection("run-projection-rebuild")

    assert rebuilt.status == "completed"
    assert rebuilt.active_stage_id == "export"
    assert rebuilt.artifact_refs == completed.artifact_refs
    assert rebuilt.checkpoint_id == completed.checkpoint_id
    assert call_count == sum(
        len(items)
        for items in (
            provider.stage_requests,
            provider.proposal_requests,
            provider.chapter_requests,
            provider.review_requests,
            provider.evidence_requests,
            provider.cover_requests,
        )
    )
    assert len(stores.context_manifests.list("run-projection-rebuild")) == 2
    assert len(stores.evidence.list("run-projection-rebuild")) == 2
    assert len(stores.canon.facts("run-projection-rebuild")) == 2
    assert len(stores.wiki.list("run-projection-rebuild")) == 2
    assert len(stores.exports.list("run-projection-rebuild")) == 1


@pytest.mark.asyncio
async def test_cast_batches_keep_every_preallocated_subject(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider(subject_count=6)
    _create_run(stores, "run-cast-batches")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-cast-batches")

    assert projection.status == "completed", projection.failure
    cast_requests = [request for request in provider.stage_requests if request.stage_id == "cast"]
    assert [len(request.context["material"]["subject_refs"]) for request in cast_requests] == [5, 1]
    artifact = stores.artifacts.latest("run-cast-batches", "cast").payload
    assert [subject["id"] for subject in artifact["subjects"]] == [
        f"subject-{index}" for index in range(1, 7)
    ]
    relation_request = next(
        request
        for request in provider.proposal_requests
        if request.proposal_type == "cast_relation"
    )
    assert len(relation_request.context["material"]["subjects"]) == 6


@pytest.mark.asyncio
async def test_cast_group_name_collision_repairs_with_reserved_names(tmp_path) -> None:
    """A later dossier group reusing an earlier group's name must repair, not fail.

    Groups run sequentially and only see other groups through
    material.reserved_names; a collision is caught per unit so the contract
    repair loop retries with the violation in context.
    """
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider(subject_count=6)
    original_generate_stage = provider.generate_stage
    collided_once = {"done": False}

    async def generate_stage_with_name_collision(request):
        result = await original_generate_stage(request)
        is_second_group = (
            request.stage_id == "cast"
            and request.context["material"]["subject_refs"][0]["id"] == "subject-6"
        )
        if is_second_group and not collided_once["done"]:
            collided_once["done"] = True
            payload = json.loads(json.dumps(result.payload))
            payload["subjects"][0]["name"] = "角色1"
            return result.model_copy(update={"payload": payload})
        return result

    provider.generate_stage = generate_stage_with_name_collision
    _create_run(stores, "run-cast-collision")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-cast-collision")

    assert projection.status == "completed", projection.failure
    second_group_requests = [
        request
        for request in provider.stage_requests
        if request.stage_id == "cast"
        and request.context["material"]["subject_refs"][0]["id"] == "subject-6"
    ]
    assert [request.operation_key.endswith(":repair-1") for request in second_group_requests] == [False, True]
    assert second_group_requests[1].context["material"]["reserved_names"] == [
        f"角色{index}" for index in range(1, 6)
    ]
    artifact = stores.artifacts.latest("run-cast-collision", "cast").payload
    names = [subject["name"] for subject in artifact["subjects"]]
    assert len(names) == len(set(names)) == 6


@pytest.mark.asyncio
async def test_chapter_revision_freezes_a_new_signed_context_manifest(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-revision-manifest", quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    paused = await _advance_to_first_chapter(runtime, "run-revision-manifest")
    first = stores.context_manifests.list("run-revision-manifest")[0]
    decision = dict(paused.pending_decisions[0])
    command = {
        "decision_id": decision["decision_id"],
        "domain_revision": decision["domain_revision"],
        "action": "regenerate",
        "direction": "收紧追逐节奏",
    }

    revised_pause = await runtime.resume("run-revision-manifest", command)

    manifests = stores.context_manifests.list("run-revision-manifest")
    assert [(item.chapter_id, item.attempt) for item in manifests] == [
        ("chapter-1", 1),
        ("chapter-1", 2),
    ]
    revised = manifests[-1]
    assert revised.manifest_id != first.manifest_id
    assert revised.manifest.optional[-1] == "revision.request"
    assert revised.manifest.snippets[-1].text == "收紧追逐节奏"
    assert revised_pause.context_manifest_ref == revised.manifest_id
    assert [request.chapter_id for request in provider.chapter_requests] == [
        "chapter-1",
        "chapter-1",
    ]
    provider_manifest = provider.chapter_requests[-1].context["material"]
    assert set(provider_manifest) == {"chapter_context_manifest"}
    assert (
        provider_manifest["chapter_context_manifest"]["manifest_hash"]
        == revised.manifest.manifest_hash
    )

    replay = await runtime.resume("run-revision-manifest", command)

    assert replay.pending_decisions == revised_pause.pending_decisions
    assert len(provider.chapter_requests) == 2
    assert len(stores.context_manifests.list("run-revision-manifest")) == 2


@pytest.mark.asyncio
async def test_branch_copies_only_context_manifest_referenced_by_checkpoint(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-branch-source", quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    paused = await _advance_to_first_chapter(runtime, "run-branch-source")
    referenced_manifest_id = paused.context_manifest_ref
    referenced = stores.context_manifests.read(
        "run-branch-source", referenced_manifest_id
    )
    future = stores.context_manifests.write(
        "run-branch-source",
        attempt=99,
        manifest=referenced.manifest,
    )

    branch = await NarrativeBranchService(runtime).create(
        source_run_id="run-branch-source",
        target_run_id="run-branch-target",
        checkpoint_id=paused.checkpoint_id,
    )

    copied = stores.context_manifests.list("run-branch-target")
    assert branch.context_manifest_ref == referenced_manifest_id
    assert [item.manifest_id for item in copied] == [referenced_manifest_id]
    assert future.manifest_id not in {item.manifest_id for item in copied}


@pytest.mark.asyncio
async def test_balanced_interrupt_resume_is_exactly_once(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-balanced", quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start("run-balanced")

    assert paused.status == "awaiting_decision"
    assert paused.active_stage_id == "brief"
    assert [request.stage_id for request in provider.stage_requests] == ["brief"]
    decision = dict(paused.pending_decisions[0])
    command = {
        "decision_id": decision["decision_id"],
        "domain_revision": decision["domain_revision"],
        "action": "accept",
    }

    next_pause = await runtime.resume("run-balanced", command)

    assert next_pause.status == "awaiting_decision"
    assert next_pause.active_stage_id == "spine"
    assert [request.stage_id for request in provider.stage_requests] == ["brief", "spine"]
    assert stores.artifacts.latest("run-balanced", "brief").status == "committed"
    assert stores.operations.read(
        "run-balanced", decision_operation_key(decision["decision_id"])
    ).status == "succeeded"

    replay = await runtime.resume("run-balanced", command)

    assert replay.pending_decisions == next_pause.pending_decisions
    assert [request.stage_id for request in provider.stage_requests] == ["brief", "spine"]
    assert len(
        [
            event
            for event in stores.events.read("run-balanced")
            if event.type == "artifact.committed" and event.stage_id == "brief"
        ]
    ) == 1


@pytest.mark.asyncio
async def test_sqlite_reopen_recover_preserves_human_interrupt(tmp_path) -> None:
    root = tmp_path / "runtime"
    stores = filesystem_stores(root)
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-reopen", quality_mode="balanced")

    async with open_sqlite_runtime(root, provider) as runtime:
        paused = await runtime.start("run-reopen")
        assert paused.status == "awaiting_decision"
        decision = dict(paused.pending_decisions[0])

    async with open_sqlite_runtime(root, provider) as reopened:
        recovered = await reopened.recover("run-reopen")

        assert recovered.status == "awaiting_decision"
        assert recovered.pending_decisions == paused.pending_decisions
        assert [request.stage_id for request in provider.stage_requests] == ["brief"]

        resumed = await reopened.resume(
            "run-reopen",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert resumed.status == "awaiting_decision"
    assert resumed.active_stage_id == "spine"
    assert [request.stage_id for request in provider.stage_requests] == ["brief", "spine"]
    assert filesystem_stores(root).runs.read("run-reopen").checkpoint_id


def test_downstream_volume_contract_rejects_unknown_spine_turn() -> None:
    volume = {"volumes": [{"id": "volume-1", "title": "雾港残响", "promise": "p", "conflict": "c", "climax": "x", "closure": "z", "turn_refs": ["turn-x"], "cast_ids": ["subject-lin"], "thread_ids": [], "length_hint": "short"}]}
    with pytest.raises(ValueError, match="unknown spine turns"):
        validate_artifact_vnext("volumes", volume, subject_ids={"subject-lin"}, turn_ids={"turn-1"})

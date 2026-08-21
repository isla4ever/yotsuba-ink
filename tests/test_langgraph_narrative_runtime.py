from __future__ import annotations

import asyncio
import hashlib
import json
from types import SimpleNamespace
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
    ProviderOperationError,
    StructuredProviderResult,
)
from novel_workflow.runtime.graph.branch_service import (
    BranchConflictError,
    NarrativeBranchService,
)
from novel_workflow.runtime.graph.runtime import (
    NarrativeRuntime,
    _active_interrupts,
    _decision_is_pending,
    _projection_values,
    decision_operation_key,
    filesystem_stores,
    has_active_graph_interrupt,
    open_sqlite_runtime,
)
from novel_workflow.storage.narrative_run_repository import (
    BranchBindingOverride,
    ExportPreferences,
    ProviderBinding,
)
from novel_workflow.workflows.hierarchical_scale import plan_hierarchical_narrative_scale
from novel_workflow.workflows.narrative_scale import (
    NarrativeScaleProfile,
    count_prose_characters,
)
from tests.fakes import FakeNarrativeProvider, fake_spine_payload
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


class HardConflictReviewProvider(FakeNarrativeProvider):
    async def review_chapter(
        self,
        request: ChapterReviewRequest,
    ) -> StructuredProviderResult:
        self.review_requests.append(request)
        findings = []
        if request.role == "continuity":
            material = request.context["material"]
            content = material["chapter"]["content"]
            cast_ids = material["current_detail_chapter"]["cast_ids"]
            findings = [{
                "code": "time_rule_conflict",
                "severity": "blocking",
                "claim": "正文让 24 小时后的事故在同一时段兑现。",
                "evidence": content[:20],
                "subject_ids": cast_ids[:1],
            }]
        return StructuredProviderResult(
            payload=ChapterReviewResult(
                role=request.role,
                findings=findings,
            ).model_dump(mode="json"),
            usage={"total_tokens": 1},
        )


class UnavailableRequiredReviewProvider(FakeNarrativeProvider):
    async def review_chapter(
        self,
        request: ChapterReviewRequest,
    ) -> StructuredProviderResult:
        self.review_requests.append(request)
        if request.role == "continuity":
            raise ProviderOperationError(
                "simulated required review failure",
                operation_key=request.operation_key,
            )
        return StructuredProviderResult(
            payload=ChapterReviewResult(role=request.role).model_dump(mode="json"),
            usage={"total_tokens": 1},
        )


class DeterministicConflictProvider(FakeNarrativeProvider):
    async def generate_stage(self, request):
        response = await super().generate_stage(request)
        if request.stage_id != "brief":
            return response
        payload = dict(response.payload)
        payload["world_rules"] = [
            "报警电话来自24小时后的事件，只能提前一天干预。"
        ]
        return response.model_copy(update={"payload": payload})

    async def generate_chapter_scene(self, request):
        response = await super().generate_chapter_scene(request)
        conflict = (
            "电话那头喊：马上要出车祸。林远刚放下听筒，"
            "几分钟后黑车撞向护栏。"
        )
        return PlainTextProviderResult(
            content=conflict + response.content,
            usage=response.usage,
        )


class UnbalancedQuoteProvider(FakeNarrativeProvider):
    async def generate_chapter_scene(self, request):
        response = await super().generate_chapter_scene(request)
        if request.chapter_id == "chapter-1" and request.scene_index == 1:
            return response.model_copy(update={"content": "林岚说：“来源不对。" + response.content})
        return response


class SimulatedProcessStop(BaseException):
    pass


def test_nested_interrupt_frontier_replaces_stale_parent_decision() -> None:
    stale = SimpleNamespace(id="interrupt-16", value={"decision_id": "chapter-16"})
    active = SimpleNamespace(id="interrupt-17", value={"decision_id": "chapter-17"})
    child = SimpleNamespace(
        values={"active_chapter_id": "chapter-17"},
        interrupts=(active,),
        tasks=(),
    )
    parent = SimpleNamespace(
        values={"active_chapter_id": "chapter-16"},
        interrupts=(stale,),
        tasks=(SimpleNamespace(state=child, interrupts=(stale,)),),
    )

    assert has_active_graph_interrupt(parent)
    assert _projection_values(parent)["active_chapter_id"] == "chapter-17"
    assert _active_interrupts(parent) == (active,)
    assert _decision_is_pending(parent, "chapter-17")
    assert not _decision_is_pending(parent, "chapter-16")


class RepairingSpineProvider(FakeNarrativeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.spine_review_count = 0

    async def generate_stage(self, request):
        result = await super().generate_stage(request)
        if request.stage_id != "spine":
            return result
        material = request.context.get("material") or {}
        if isinstance(material.get("revision_request"), dict):
            repaired = dict(result.payload)
            turns = [dict(turn) for turn in repaired["turns"]]
            turns[1]["cause"] = "首个调查结果迫使对立方公开阻断主角，形成可见的第二轮压力"
            repaired["turns"] = turns
            return StructuredProviderResult(payload=repaired, usage=result.usage)
        return result

    async def generate_proposal(self, request):
        if request.proposal_type != "spine_review":
            return await super().generate_proposal(request)
        self.proposal_requests.append(request)
        self.spine_review_count += 1
        payload = (
            {
                "verdict": "revise",
                "findings": [
                    {
                        "code": "causal_handoff",
                        "turn_refs": ["turn-1", "turn-2"],
                        "claim": "第二个 cause 没有消费首个 change。",
                        "required_fix": "让第二个压力由首个调查结果直接触发。",
                    }
                ],
            }
            if self.spine_review_count == 1
            else {"verdict": "pass", "findings": []}
        )
        return StructuredProviderResult(payload=payload, usage={"total_tokens": 2})


class ContractFailingSpineRepairProvider(RepairingSpineProvider):
    """The first private repair is structurally invalid; the next must remain private."""

    def __init__(self) -> None:
        super().__init__()
        self.contract_failure_emitted = False

    async def generate_stage(self, request):
        result = await super().generate_stage(request)
        if request.stage_id != "spine":
            return result
        material = request.context.get("material") or {}
        if not isinstance(material.get("revision_request"), dict):
            return result
        if not self.contract_failure_emitted:
            self.contract_failure_emitted = True
            repaired = dict(result.payload)
            turns = [dict(turn) for turn in repaired["turns"]]
            turns[0]["progress_type"] = "invalid-progress"
            repaired["turns"] = turns
            return StructuredProviderResult(payload=repaired, usage=result.usage)
        return result


class RepairingCastPlanningProvider(FakeNarrativeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.role_demand_review_count = 0
        self.cast_review_count = 0

    async def generate_stage(self, request):
        result = await super().generate_stage(request)
        if request.stage_id != "cast":
            return result
        material = request.context.get("material") or {}
        if not isinstance(material.get("revision_request"), dict):
            return result
        repaired = dict(result.payload)
        subjects = [dict(item) for item in repaired["subjects"]]
        subjects[0]["background"] = (
            "复核后确认其在故事开始前已负责公共档案修复，并因旧港事故积累了可调用的原件鉴别经验。"
        )
        repaired["subjects"] = subjects
        return StructuredProviderResult(payload=repaired, usage=result.usage)

    async def generate_proposal(self, request):
        if request.proposal_type == "role_demand_review":
            self.proposal_requests.append(request)
            self.role_demand_review_count += 1
            demands = request.context["material"]["proposed_role_demands"]["proposals"]
            payload = (
                {
                    "verdict": "revise",
                    "findings": [
                        {
                            "code": "mergeable_demand",
                            "demand_refs": [demands[0]["demand_key"], demands[1]["demand_key"]],
                            "turn_refs": ["turn-1"],
                            "claim": "两个职责仍可能由同一主体承担。",
                            "required_fix": "重新验证不可合并选择，并合并可替代职责。",
                        }
                    ],
                }
                if self.role_demand_review_count == 1
                else {"verdict": "pass", "findings": []}
            )
            return StructuredProviderResult(payload=payload, usage={"total_tokens": 2})
        if request.proposal_type == "cast_review":
            self.proposal_requests.append(request)
            self.cast_review_count += 1
            material = request.context["material"]
            subject_ref = material["subject_refs"][0]
            proposal = material["role_demand_proposals"][0]
            payload = (
                {
                    "verdict": "revise",
                    "findings": [
                        {
                            "code": "background_contradiction",
                            "subject_refs": [subject_ref["id"]],
                            "demand_refs": [proposal["demand_key"]],
                            "turn_refs": [proposal["active_turn_refs"][0]],
                            "claim": "背景没有清楚区分故事前经历与当前剧情动作。",
                            "required_fix": "只保留故事开始前已成立的身份、经历与能力。",
                        }
                    ],
                }
                if self.cast_review_count == 1
                else {"verdict": "pass", "findings": []}
            )
            return StructuredProviderResult(payload=payload, usage={"total_tokens": 2})
        return await super().generate_proposal(request)


class ContractFailingRoleDemandProvider(FakeNarrativeProvider):
    """Model one parsed Role Demand object that fails its frozen contract once."""

    def __init__(self) -> None:
        super().__init__()
        self.contract_failure_emitted = False

    async def generate_proposal(self, request):
        if request.proposal_type != "role_demand":
            return await super().generate_proposal(request)
        if not self.contract_failure_emitted:
            self.contract_failure_emitted = True
            self.proposal_requests.append(request)
            raise ProviderOperationError(
                "A present role demand must use actor mode",
                operation_key=request.operation_key,
                usage={"total_tokens": 3},
                diagnostic={
                    "code": "structured_contract_invalid",
                    "structured_parse": {
                        "response_chars": 100,
                        "candidate_count": 1,
                        "parsed_object_count": 1,
                        "schema_match_count": 1,
                    },
                },
            )
        return await super().generate_proposal(request)


def _bindings(*, detail_max_tokens: int = 6_000) -> dict[str, ProviderBinding]:
    return {
        stage: provider_binding(
            stage,
            max_tokens=detail_max_tokens if stage == "detail" else 12_000,
        )
        for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
    }


def _create_run(
    stores: Any,
    run_id: str,
    *,
    quality_mode: str = "fast",
    target_chapter_count: int = 2,
    word_target_soft: int | None = None,
    detail_max_tokens: int = 6_000,
    volume_candidate_cap: int = 12,
    include_cover_image: bool = True,
) -> None:
    scale_profile = NarrativeScaleProfile(
        word_target_soft=word_target_soft or target_chapter_count * 2_000,
        volume_candidate_cap=volume_candidate_cap,
    )
    stores.runs.create(
        run_id=run_id,
        project_id="project-1",
        workflow_id="workflow-1",
        workflow_revision="phase27-vnext",
        workflow_digest="a" * 64,
        quality_mode=quality_mode,
        inputs={"project_brief": {"genre": "悬疑"}},
        scale_profile=scale_profile,
        hierarchical_scale_plan=plan_hierarchical_narrative_scale(
            scale_profile,
            quality_mode=quality_mode,
        ),
        provider_bindings=_bindings(detail_max_tokens=detail_max_tokens),
        cover_asset_binding=cover_asset_binding(),
        export_preferences=ExportPreferences(
            format="zip",
            include_cover_image=include_cover_image,
        ),
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
    role = RoleDemandProposalBatch.model_validate({"proposals": [{"demand_key": "demand-a", "subject_mode": "actor", "narrative_role": "protagonist", "function": "取证", "required_change": "作证", "irreducibility": "必须由主角承担公开证言的不可逆后果。", "active_turn_refs": ["turn-1"]}]})
    assert role.proposals[0].demand_key == "demand-a"
    boundary = VolumeBoundaryProposalBatch.model_validate({"proposals": [{"boundary_key": "boundary-1", "turn_refs": ["turn-x"], "reason": "bad"}]})
    assert boundary.proposals[0].turn_refs == ["turn-x"]


def test_scale_profile_rejects_retired_reasonable_bounds() -> None:
    profile = NarrativeScaleProfile(word_target_soft=4_000)
    assert profile.word_target_soft == 4_000
    with pytest.raises(ValueError):
        NarrativeScaleProfile.model_validate(
            {
                "word_target_soft": 4_000,
                "chapter_target_soft": 8,
                "chapter_min_reasonable": 1,
            }
        )


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
async def test_spine_semantic_review_does_not_trigger_hidden_regeneration(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = RepairingSpineProvider()
    run_id = "run-spine-semantic-preflight"
    _create_run(stores, run_id, quality_mode="balanced", word_target_soft=100_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(run_id)
    brief_decision = dict(paused.pending_decisions[0])
    paused = await runtime.resume(
        run_id,
        {
            "decision_id": brief_decision["decision_id"],
            "domain_revision": brief_decision["domain_revision"],
            "action": "accept",
        },
    )

    assert paused.status == "awaiting_decision"
    assert paused.active_stage_id == "spine"
    assert provider.spine_review_count == 1
    assert len([request for request in provider.stage_requests if request.stage_id == "spine"]) == 1
    candidate = stores.artifacts.read(
        run_id,
        paused.pending_decisions[0]["artifact_ref"],
    )
    assert candidate.source.endswith(":spine:generate:1")
    assert not candidate.payload["turns"][1]["cause"].startswith("首个调查结果")
    assert not any(
        event.type == "artifact.candidate_ready" and event.stage_id == "spine"
        for event in stores.events.read(run_id)
        if event.payload_ref != candidate.artifact_id
    )


@pytest.mark.asyncio
async def test_advisory_spine_review_never_requests_a_contract_invalid_private_repair(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = ContractFailingSpineRepairProvider()
    run_id = "run-spine-contract-invalid-repair"
    _create_run(stores, run_id, quality_mode="balanced", word_target_soft=100_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(run_id)
    brief_decision = dict(paused.pending_decisions[0])
    paused = await runtime.resume(
        run_id,
        {
            "decision_id": brief_decision["decision_id"],
            "domain_revision": brief_decision["domain_revision"],
            "action": "accept",
        },
    )

    assert paused.status == "awaiting_decision"
    assert paused.active_stage_id == "spine"
    assert provider.spine_review_count == 1
    assert len([request for request in provider.stage_requests if request.stage_id == "spine"]) == 1
    candidate = stores.artifacts.read(run_id, paused.pending_decisions[0]["artifact_ref"])
    assert candidate.source.endswith(":spine:generate:1")
    assert len(
        [
            event
            for event in stores.events.read(run_id)
            if event.type == "artifact.candidate_ready" and event.stage_id == "spine"
        ]
    ) == 1
    assert stores.operations.find(
        run_id,
        "run-spine-contract-invalid-repair:spine:generate:1:semantic-repair-1",
    ) is None


@pytest.mark.asyncio
async def test_cast_semantic_reviews_are_advisory_without_hidden_regeneration(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = RepairingCastPlanningProvider()
    run_id = "run-cast-planning-semantic-preflight"
    _create_run(stores, run_id, quality_mode="balanced", word_target_soft=4_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(run_id)
    for expected_stage in ("brief", "spine"):
        assert paused.active_stage_id == expected_stage
        decision = dict(paused.pending_decisions[0])
        paused = await runtime.resume(
            run_id,
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert paused.status == "awaiting_decision"
    assert paused.active_stage_id == "cast"
    assert provider.role_demand_review_count == 1
    assert provider.cast_review_count == 1
    assert len(
        [
            request
            for request in provider.proposal_requests
            if request.proposal_type == "role_demand"
        ]
    ) == 1
    assert len(
        [request for request in provider.stage_requests if request.stage_id == "cast"]
    ) == 1
    candidate = stores.artifacts.read(
        run_id,
        paused.pending_decisions[0]["artifact_ref"],
    )
    assert not candidate.payload["subjects"][0]["background"].startswith("复核后确认")
    assert len(
        [
            event
            for event in stores.events.read(run_id)
            if event.type == "artifact.candidate_ready" and event.stage_id == "cast"
        ]
    ) == 1


@pytest.mark.asyncio
async def test_langgraph_phase27_fast_run_uses_proposals_and_plaintext_chapters(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-phase27")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await runtime.start("run-phase27")
    assert projection.status == "completed", projection.failure
    assert [request.stage_id for request in provider.stage_requests] == [
        "brief", "spine", "cast", "volumes", "detail", "cover",
    ]
    assert [request.proposal_type for request in provider.proposal_requests] == [
        "spine_review",
        "role_demand",
        "role_demand_review",
        "cast_review",
        "cast_relation",
        "volume_boundary",
        "detail_layout",
    ]
    detail_layout_request = next(
        request
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    )
    detail_scale = detail_layout_request.context["material"]["scale_plan"]
    assert detail_scale["turn_count"] == 3
    assert detail_scale["minimum_chapter_surplus_over_turns"] == 0
    assert detail_scale["target_chapter_surplus_over_turns"] == 0
    assert detail_scale["book_chapter_range"] == [2, 2]
    assert detail_scale["chapter_range"] == [2, 2]
    assert detail_scale["chapter_target"] == 2
    assert detail_scale["allocated_chapters"] == 0
    assert detail_scale["remaining_volume_range"] == [0, 0]
    assert detail_layout_request.context["material"]["chapter_slots"] == [
        {"slot_index": 1},
        {"slot_index": 2},
    ]
    assert detail_layout_request.context["material"]["world_rule_projection"][
        "rules"
    ][0]["source_text"] == "公开广播会覆盖个人记忆"
    detail_requests = [
        request for request in provider.stage_requests if request.stage_id == "detail"
    ]
    assert all(
        request.context["material"]["world_rule_projection"]["rules"][0][
            "source_text"
        ]
        == "公开广播会覆盖个人记忆"
        for request in detail_requests
    )
    assert [
        (request.chapter_id, request.scene_index)
        for request in provider.chapter_requests
    ] == [
        ("chapter-1", 1),
        ("chapter-1", 2),
        ("chapter-2", 1),
        ("chapter-2", 2),
    ]
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
        "scene.execution"
        in request.context["material"]["chapter_context_manifest"]["required"]
        for request in provider.chapter_requests
    )
    first_manifest_rules = next(
        item
        for item in provider.chapter_requests[0].context["material"][
            "chapter_context_manifest"
        ]["snippets"]
        if item["ref"] == "brief.world_rules"
    )
    assert json.loads(first_manifest_rules["text"])["rules"][0]["source_text"] == (
        "公开广播会覆盖个人记忆"
    )
    # Sequential chapters must see the previous accepted ending, not only the
    # planned one-line handoff, so prose time/place/knowledge state continues.
    second_manifest = provider.chapter_requests[2].context["material"]["chapter_context_manifest"]
    ending_snippets = [
        item for item in second_manifest["snippets"] if item["ref"] == "previous.ending_excerpt"
    ]
    assert len(ending_snippets) == 1
    accepted_first = stores.chapters.read(
        "run-phase27", "chapter-1", "chapter-1-v1-accepted"
    ).artifact.content
    assert accepted_first.strip().endswith(ending_snippets[0]["text"][-40:])
    # Resolved state derived from accepted chapter evidence must bind later prose.
    state_snippets = [
        item for item in second_manifest["snippets"] if item["ref"] == "story.current_state"
    ]
    assert len(state_snippets) == 1
    state_payload = json.loads(state_snippets[0]["text"])
    assert [item["value"] for item in state_payload["entries"]] == [
        "本章完成施工图目标"
    ]
    recent_snippet = next(
        item
        for item in second_manifest["snippets"]
        if item["ref"] == "continuity.recent_window"
    )
    recent_payload = json.loads(recent_snippet["text"])
    assert recent_payload["window_size"] == 4
    assert [item["chapter_id"] for item in recent_payload["chapters"]] == [
        "chapter-1"
    ]
    assert recent_payload["chapters"][0]["dramatic_job"] == "取得母带副本"
    assert sorted(
        (request.chapter_id, request.role) for request in provider.review_requests
    ) == sorted(
        (chapter_id, role)
        for chapter_id in ("chapter-1", "chapter-2")
        for role in ("character", "continuity", "prose")
    )
    continuity = {
        request.chapter_id: request.context["material"]
        for request in provider.review_requests
        if request.role == "continuity"
    }
    assert continuity["chapter-1"]["opening_chapter"] is True
    assert continuity["chapter-1"]["current_detail_chapter"]["ref"] == "chapter-1"
    assert continuity["chapter-1"]["world_rule_projection"]["rules"][0][
        "source_text"
    ] == "公开广播会覆盖个人记忆"
    assert {
        subject["id"] for subject in continuity["chapter-1"]["character_bible"]
    } == {"subject-1", "subject-2"}
    assert "spine" not in continuity["chapter-1"]
    assert "volume_contract" not in continuity["chapter-1"]
    assert continuity["chapter-2"]["previous_accepted_chapter"]["handoff"] == "追查签名来源"
    assert [
        item["chapter_id"]
        for item in continuity["chapter-2"]["recent_chapter_window"]["chapters"]
    ] == ["chapter-1"]
    assert "evidence_provenance" in continuity["chapter-2"]["continuity_state"]
    assert [
        item["value"] for item in continuity["chapter-2"]["story_state"]["entries"]
    ] == ["本章完成施工图目标"]
    assert continuity["chapter-2"]["story_state"]["conflicts"] == []
    assert [request.chapter_id for request in provider.evidence_requests] == ["chapter-1", "chapter-2"]
    first_evidence_context = provider.evidence_requests[0].context
    second_evidence_context = provider.evidence_requests[1].context
    assert {
        subject["id"] for subject in first_evidence_context["frozen_subjects"]
    } == {"subject-1", "subject-2"}
    assert first_evidence_context["story_state"]["entries"] == []
    first_fact = stores.canon.facts("run-phase27")[0]
    assert [
        item["source_fact_id"]
        for item in second_evidence_context["story_state"]["entries"]
    ] == [first_fact.fact_id]
    assert [request.candidate_index for request in provider.cover_requests] == [1]
    detail = stores.artifacts.latest("run-phase27", "detail").payload
    assert [item["ref"] for item in detail["chapters"]] == ["chapter-1", "chapter-2"]
    assert [item["title"] for item in detail["chapters"]] == ["母带残响1", "母带残响2"]
    assert [item["target_characters"] for item in detail["chapters"]] == [2_216, 2_184]
    assert sum(item["target_characters"] for item in detail["chapters"]) == 4_400
    accepted_chapters = [
        stores.chapters.read("run-phase27", item["ref"], f"{item['ref']}-v1-accepted").artifact
        for item in detail["chapters"]
    ]
    assert [chapter.title for chapter in accepted_chapters] == ["母带残响1", "母带残响2"]
    assert [count_prose_characters(chapter.content) for chapter in accepted_chapters] == [2_216, 2_184]
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
    evidence = stores.evidence.list("run-phase27")
    committed_facts = stores.canon.facts("run-phase27")
    assert len(evidence) == 2
    assert len(committed_facts) == 2
    assert sorted(
        (item.property_key, item.effective_from_chapter) for item in evidence
    ) == [
        ("chapter-1.completion", 1),
        ("chapter-2.completion", 2),
    ]
    assert [
        (
            item.subject_id,
            item.property_key,
            item.value,
            item.effective_from_chapter,
        )
        for item in committed_facts
    ] == [
        ("story", "chapter-1.completion", "本章完成施工图目标", 1),
        ("story", "chapter-2.completion", "本章完成施工图目标", 2),
    ]
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
async def test_run_can_close_cover_metadata_and_export_without_generating_an_image(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(
        stores,
        "run-cover-metadata-only",
        include_cover_image=False,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-cover-metadata-only")

    assert projection.status == "completed", projection.failure
    assert provider.cover_requests == []
    assert stores.cover_assets.list("run-cover-metadata-only") == []
    assert stores.artifacts.latest(
        "run-cover-metadata-only", "cover"
    ).payload["selected_asset_id"] == ""
    assert stores.artifacts.latest(
        "run-cover-metadata-only", "export"
    ).payload["cover_asset_id"] == ""
    assert len(stores.exports.list("run-cover-metadata-only")) == 1


@pytest.mark.asyncio
async def test_detail_capacity_segments_carry_a_strict_bounded_handoff(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(
        stores,
        "run-detail-handoff",
        word_target_soft=7_500,
        detail_max_tokens=2_400,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-detail-handoff")

    assert projection.status == "completed", projection.failure
    detail_requests = [
        request for request in provider.stage_requests if request.stage_id == "detail"
    ]
    assert len(detail_requests) == 3
    first_material = detail_requests[0].context["material"]
    second_material = detail_requests[1].context["material"]
    third_material = detail_requests[2].context["material"]
    assert first_material["historical_record_ids"] == []
    assert first_material["present_actor_ids"] == ["subject-1", "subject-2"]
    assert first_material["volume_contract"] == {
        "id": "volume-1",
        "title": "雾港1卷",
    }
    assert second_material["volume_contract"] == {
        "id": "volume-1",
        "title": "雾港1卷",
    }
    assert set(third_material["volume_contract"]) == {
        "id",
        "title",
        "closing_state",
    }
    assert first_material["scale_projection"]["chapter_beats"] == [
        {
            "chapter_offset": 1,
            "turn_refs": ["turn-1"],
            "dramatic_job": "完成volume-1的第1个独立变化",
            "length_hint": "standard",
        }
    ]
    assert second_material["scale_projection"]["chapter_beats"] == [
        {
            "chapter_offset": 1,
            "turn_refs": ["turn-2"],
            "dramatic_job": "完成volume-1的第2个独立变化",
            "length_hint": "standard",
        }
    ]
    assert "previous_segment_handoff" not in first_material
    assert second_material["previous_segment_handoff"] == {
        "previous_ref": "chapter-1",
        "completed_turn_refs": ["turn-1"],
        "established_chapters": [
            {
                "chapter_ref": "chapter-1",
                "title": "母带残响1",
                "turn_refs": ["turn-1"],
                "purpose": "取得母带副本",
                "final_result": "从档案室取得母带并核验内容",
            },
        ],
        "unresolved": ["追查签名来源"],
        "next_ref": "volume-1.segment-2",
    }
    assert third_material["previous_segment_handoff"] == {
        "previous_ref": "chapter-2",
        "completed_turn_refs": ["turn-1", "turn-2"],
        "established_chapters": [
            {
                "chapter_ref": "chapter-1",
                "title": "母带残响1",
                "turn_refs": ["turn-1"],
                "purpose": "取得母带副本",
                "final_result": "从档案室取得母带并核验内容",
            },
            {
                "chapter_ref": "chapter-2",
                "title": "母带残响2",
                "turn_refs": ["turn-2"],
                "purpose": "公开母带并锁定删除责任",
                "final_result": "公开母带并说明档案室来源",
            },
        ],
        "unresolved": ["追问删除命令责任"],
        "next_ref": "volume-1.segment-3",
    }


@pytest.mark.asyncio
async def test_detail_allows_single_scene_chapters_that_can_carry_viable_prose(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_stage = provider.generate_stage

    async def generate_single_scene_detail(request):
        result = await original_generate_stage(request)
        if request.stage_id != "detail":
            return result
        payload = json.loads(json.dumps(result.payload))
        for chapter in payload["chapters"]:
            chapter["scenes"] = chapter["scenes"][:1]
        return result.model_copy(update={"payload": payload})

    provider.generate_stage = generate_single_scene_detail
    _create_run(
        stores,
        "run-single-scene-detail",
        word_target_soft=7_500,
        include_cover_image=False,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-single-scene-detail")

    assert projection.status == "completed", projection.failure
    detail = stores.artifacts.latest("run-single-scene-detail", "detail").payload
    assert [len(chapter["scenes"]) for chapter in detail["chapters"]] == [1, 1, 1]
    assert sum(chapter["target_characters"] for chapter in detail["chapters"]) == 7_200
    assert stores.operations.usage_summary("run-single-scene-detail").failed_operations == 0


@pytest.mark.asyncio
async def test_stage_recovery_reuses_a_persisted_provider_return(
    tmp_path,
    monkeypatch,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(
        stores,
        "run-stage-provider-return-replay",
        word_target_soft=7_500,
        include_cover_image=False,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    original_record = stores.operations.record_provider_return
    stopped = False

    def stop_after_detail_return(run_id, operation_key, *args, **kwargs):
        nonlocal stopped
        receipt = original_record(run_id, operation_key, *args, **kwargs)
        if ":detail:generate:1:" in operation_key and not stopped:
            stopped = True
            raise SimulatedProcessStop("process stopped after the Detail Provider return")
        return receipt

    monkeypatch.setattr(stores.operations, "record_provider_return", stop_after_detail_return)
    with pytest.raises(SimulatedProcessStop, match="Detail Provider return"):
        await runtime.start("run-stage-provider-return-replay")

    detail_requests_before_recovery = [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "detail"
    ]
    assert len(detail_requests_before_recovery) == 1
    interrupted = stores.operations.read(
        "run-stage-provider-return-replay",
        detail_requests_before_recovery[0],
    )
    assert interrupted.status == "provider_returned"
    assert interrupted.provider_result is not None

    monkeypatch.setattr(stores.operations, "record_provider_return", original_record)
    completed = await runtime.recover("run-stage-provider-return-replay")

    assert completed.status == "completed", completed.failure
    assert [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "detail"
    ].count(detail_requests_before_recovery[0]) == 1
    accepted = stores.operations.read(
        "run-stage-provider-return-replay",
        detail_requests_before_recovery[0],
    )
    assert accepted.status == "succeeded"


@pytest.mark.asyncio
async def test_scene_length_violation_warns_without_a_scene_rewrite(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate = provider.generate_chapter_scene
    returned_short_draft = False

    async def generate_short_once(request):
        nonlocal returned_short_draft
        if request.chapter_id == "chapter-1" and not returned_short_draft:
            returned_short_draft = True
            provider.chapter_requests.append(request)
            return PlainTextProviderResult(content="过短初稿", usage={"total_tokens": 1})
        return await original_generate(request)

    provider.generate_chapter_scene = generate_short_once
    _create_run(stores, "run-length-rewrite")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-length-rewrite")

    assert projection.status == "completed", projection.failure
    assert [
        (request.chapter_id, request.scene_index, request.scene_attempt)
        for request in provider.chapter_requests
    ] == [
        ("chapter-1", 1, 1),
        ("chapter-1", 2, 1),
        ("chapter-2", 1, 1),
        ("chapter-2", 2, 1),
    ]
    manifests = stores.context_manifests.list("run-length-rewrite")
    assert [(item.chapter_id, item.attempt) for item in manifests[:2]] == [
        ("chapter-1", 1),
        ("chapter-2", 1),
    ]
    warnings = [
        event
        for event in stores.events.read("run-length-rewrite")
        if event.type == "quality.warning"
    ]
    assert [(event.node_id, event.payload["code"]) for event in warnings] == [
        ("text.generate_prose", "scene_length_soft_band"),
    ]
    accepted = stores.chapters.read(
        "run-length-rewrite", "chapter-1", "chapter-1-v1-accepted"
    ).artifact
    assert accepted.title == "母带残响1"
    assert count_prose_characters(accepted.content) == 2_216


@pytest.mark.asyncio
async def test_scene_lengths_can_vary_while_the_rolling_budget_hits_the_chapter_contract(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate = provider.generate_chapter_scene

    async def generate_shorter_first_scene(request):
        if request.chapter_id == "chapter-1" and request.scene_index == 1:
            provider.chapter_requests.append(request)
            return PlainTextProviderResult(content="短" * 750, usage={"total_tokens": 1})
        return await original_generate(request)

    provider.generate_chapter_scene = generate_shorter_first_scene
    _create_run(stores, "run-rolling-scene-budget")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-rolling-scene-budget")

    assert projection.status == "completed", projection.failure
    chapter_one_requests = [
        request for request in provider.chapter_requests if request.chapter_id == "chapter-1"
    ]
    assert [(item.scene_index, item.scene_attempt) for item in chapter_one_requests] == [
        (1, 1),
        (2, 1),
    ]
    second_manifest = chapter_one_requests[1].context["material"][
        "chapter_context_manifest"
    ]
    rolling = next(
        snippet
        for snippet in second_manifest["snippets"]
        if snippet["ref"] == "scale.scene_length"
    )
    assert json.loads(rolling["text"]) == {
        "accepted_prior_characters": 750,
        "chapter_max_characters": 2548,
        "chapter_min_characters": 1884,
        "chapter_target_characters": 2216,
        "counting_rule": "non_whitespace_characters",
        "max_characters": 1798,
        "min_characters": 1134,
        "remaining_scene_count": 0,
        "scene_count": 2,
        "scene_index": 2,
        "target_characters": 1466,
    }
    accepted = stores.chapters.read(
        "run-rolling-scene-budget", "chapter-1", "chapter-1-v1-accepted"
    ).artifact
    assert count_prose_characters(accepted.content) == 2_216


@pytest.mark.asyncio
async def test_new_quantified_facts_trigger_one_masked_local_scene_repair(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate = provider.generate_chapter_scene
    returned_drift = False

    async def generate_numeric_drift_once(request):
        nonlocal returned_drift
        if request.chapter_id == "chapter-1" and not returned_drift:
            returned_drift = True
            provider.chapter_requests.append(request)
            seed = "她复核第三枚晶片，进度达到百分之六十七。"
            return PlainTextProviderResult(
                content=seed + "文" * (1_000 - len(seed)),
                usage={"total_tokens": 1},
            )
        return await original_generate(request)

    provider.generate_chapter_scene = generate_numeric_drift_once
    _create_run(stores, "run-quantified-fact-rewrite")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-quantified-fact-rewrite")

    assert projection.status == "completed", projection.failure
    chapter_one_requests = [
        request for request in provider.chapter_requests if request.chapter_id == "chapter-1"
    ]
    assert [(item.scene_index, item.scene_attempt) for item in chapter_one_requests] == [
        (1, 1),
        (1, 2),
        (2, 1),
    ]
    drift_receipt = stores.operations.read(
        "run-quantified-fact-rewrite",
        "run-quantified-fact-rewrite:chapter-1:scene-1:generate:1.1",
    )
    assert drift_receipt.diagnostic["introduced_quantified_facts"] == [
        "第三枚",
        "百分之六十七",
    ]
    assert drift_receipt.status == "contract_rejected"
    assert drift_receipt.usage["total_tokens"] == 1
    assert drift_receipt.result is None
    retry_manifest = chapter_one_requests[1].context["material"][
        "chapter_context_manifest"
    ]
    local_repair = next(
        json.loads(snippet["text"])
        for snippet in retry_manifest["snippets"]
        if snippet["ref"] == "revision.local_segment"
    )
    assert local_repair["scope"] == "single_bounded_scene_segment"
    assert "[未授权量化事实]" in local_repair["masked_rejected_segment"]
    assert "revision.source_draft" not in {
        snippet["ref"] for snippet in retry_manifest["snippets"]
    }
    serialized_repair = json.dumps(retry_manifest, ensure_ascii=False)
    assert "第三枚" not in serialized_repair
    assert "百分之六十七" not in serialized_repair
    assert chapter_one_requests[1].mode == "fact_repair"
    repair_receipt = stores.operations.read(
        "run-quantified-fact-rewrite",
        "run-quantified-fact-rewrite:chapter-1:scene-1:generate:1.2",
    )
    assert repair_receipt.status == "succeeded"
    assert repair_receipt.provider_result != repair_receipt.result
    accepted = stores.chapters.read(
        "run-quantified-fact-rewrite", "chapter-1", "chapter-1-v1-accepted"
    ).artifact
    assert "第三枚" not in accepted.content
    assert "百分之六十七" not in accepted.content


@pytest.mark.asyncio
async def test_new_persistent_fact_rejects_without_hidden_scene_repair(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate = provider.generate_chapter_scene

    async def generate_persistent_drift(request):
        if request.chapter_id == "chapter-1" and request.scene_index == 1:
            provider.chapter_requests.append(request)
            seed = "周宁说她已经拿到主控室钥匙，并出示了一份尸检报告。"
            return PlainTextProviderResult(
                content=seed + "文" * (1_000 - len(seed)),
                usage={"total_tokens": 17},
            )
        return await original_generate(request)

    provider.generate_chapter_scene = generate_persistent_drift
    run_id = "run-persistent-fact-hard-stop"
    _create_run(stores, run_id)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start(run_id)

    assert projection.status == "failed"
    assert projection.failure["code"] == "SceneProseContractError"
    assert "durable facts absent from frozen context" in projection.failure["message"]
    requests = [
        request
        for request in provider.chapter_requests
        if request.chapter_id == "chapter-1" and request.scene_index == 1
    ]
    assert [(request.scene_attempt, request.mode) for request in requests] == [
        (1, "generate"),
    ]
    receipt = stores.operations.read(
        run_id,
        f"{run_id}:chapter-1:scene-1:generate:1.1",
    )
    assert receipt.status == "contract_rejected"
    assert {item["code"] for item in receipt.diagnostic["introduced_persistent_facts"]} >= {
        "unregistered_scene_subject",
        "unfrozen_access_or_key",
        "unfrozen_document_or_evidence",
    }
    assert stores.operations.find(
        run_id,
        f"{run_id}:chapter-1:scene-1:generate:1.2",
    ) is None


@pytest.mark.asyncio
async def test_repeated_scene_fact_violation_stops_after_one_local_repair(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate = provider.generate_chapter_scene

    async def generate_same_drift(request):
        if request.chapter_id == "chapter-1" and request.scene_index == 1:
            provider.chapter_requests.append(request)
            return PlainTextProviderResult(
                content="她复核第三枚晶片。",
                usage={"total_tokens": 13},
            )
        return await original_generate(request)

    provider.generate_chapter_scene = generate_same_drift
    run_id = "run-scene-fact-no-progress"
    _create_run(stores, run_id)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start(run_id)

    assert projection.status == "failed"
    assert projection.failure == {
        "node_id": "text.generate_prose",
        "code": "SceneProseContractError",
        "retryable": False,
        "evidence_ref": f"{run_id}:chapter-1:scene-1:generate:1.2",
        "message": "The same quantified fact violation survived the bounded repair",
    }
    requests = [
        request
        for request in provider.chapter_requests
        if request.chapter_id == "chapter-1" and request.scene_index == 1
    ]
    assert [(request.scene_attempt, request.mode) for request in requests] == [
        (1, "generate"),
        (2, "fact_repair"),
    ]
    repair_receipt = stores.operations.read(
        run_id,
        f"{run_id}:chapter-1:scene-1:generate:1.2",
    )
    assert repair_receipt.status == "contract_rejected"
    assert repair_receipt.diagnostic["no_progress"] is True
    assert stores.operations.usage_summary(run_id).contract_rejected_operations == 2
    assert stores.operations.usage_summary(run_id).total_tokens >= 26


@pytest.mark.asyncio
async def test_severely_short_chapter_requires_explicit_chapter_decision(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()

    async def generate_short(request):
        provider.chapter_requests.append(request)
        return PlainTextProviderResult(content="始终过短", usage={"total_tokens": 1})

    provider.generate_chapter_scene = generate_short
    _create_run(stores, "run-length-failure")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-length-failure")

    assert projection.status == "awaiting_decision"
    decision = projection.pending_decisions[0]
    assert decision["type"] == "chapter_author_decision"
    assert decision["allowed_actions"] == ["cancel"]
    assert decision["quality_decision"]["contract_blockers"][0]["code"] == (
        "chapter_severely_underlength"
    )
    assert [request.chapter_attempt for request in provider.chapter_requests] == [
        1,
        1,
        2,
        2,
    ]


@pytest.mark.asyncio
async def test_short_chapter_does_not_block_while_future_budget_can_recover(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate = provider.generate_chapter_scene

    async def generate_recoverable_short_chapter(request):
        if request.chapter_id == "chapter-1":
            provider.chapter_requests.append(request)
            prefix = (
                "短章在档案室缓慢推进。"
                if request.scene_index == 1
                else "短章转入旧潮道继续推进。"
            )
            return PlainTextProviderResult(
                content=prefix + "短" * (800 - len(prefix)),
                usage={"total_tokens": 1},
            )
        return await original_generate(request)

    provider.generate_chapter_scene = generate_recoverable_short_chapter
    _create_run(stores, "run-recoverable-book-budget")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-recoverable-book-budget")

    assert projection.status == "completed", projection.failure
    warning_codes = [
        event.payload["code"]
        for event in stores.events.read("run-recoverable-book-budget")
        if event.type == "quality.warning"
    ]
    assert "chapter_length_soft_band" in warning_codes
    assert "book_length_budget_unreachable" not in warning_codes


@pytest.mark.asyncio
async def test_final_whole_book_length_gate_remains_authoritative(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()

    async def generate_individually_viable_but_collectively_short(request):
        provider.chapter_requests.append(request)
        return PlainTextProviderResult(content="短" * 675, usage={"total_tokens": 1})

    provider.generate_chapter_scene = generate_individually_viable_but_collectively_short
    _create_run(stores, "run-final-book-length-gate")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-final-book-length-gate")

    assert projection.status == "failed"
    assert projection.failure["node_id"] == "text.finish_chapters"
    assert "Whole-book prose total is below the minimum viable length" in projection.failure[
        "message"
    ]
    assert not any(
        event.type == "quality.warning"
        and event.payload.get("code") == "book_length_budget_unreachable"
        for event in stores.events.read("run-final-book-length-gate")
    )


@pytest.mark.asyncio
async def test_live_5701_character_fixture_completes_with_soft_length_warnings(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_proposal = provider.generate_proposal
    scene_lengths = {
        "chapter-1": (702, 1_026),
        "chapter-2": (854, 1_196),
        "chapter-3": (841, 1_082),
    }

    async def generate_live_layout(request):
        response = await original_generate_proposal(request)
        if request.proposal_type != "detail_layout":
            return response
        payload = dict(response.payload)
        volumes = [dict(item) for item in payload["volumes"]]
        chapters = [dict(item) for item in volumes[0]["chapters"]]
        for chapter, length_hint in zip(
            chapters,
            ("compact", "standard", "expansive"),
            strict=True,
        ):
            chapter["length_hint"] = length_hint
        volumes[0]["chapters"] = chapters
        payload["volumes"] = volumes
        return response.model_copy(update={"payload": payload})

    async def generate_live_shortfall(request):
        provider.chapter_requests.append(request)
        character_count = scene_lengths[request.chapter_id][request.scene_index - 1]
        return PlainTextProviderResult(
            content="文" * character_count,
            usage={"total_tokens": 1},
        )

    provider.generate_proposal = generate_live_layout
    provider.generate_chapter_scene = generate_live_shortfall
    run_id = "run-soft-length-guidance"
    _create_run(
        stores,
        run_id,
        word_target_soft=7_500,
        include_cover_image=False,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start(run_id)

    assert projection.status == "completed", projection.failure
    chapter_three_requests = [
        request
        for request in provider.chapter_requests
        if request.chapter_id == "chapter-3"
    ]
    assert [request.chapter_attempt for request in chapter_three_requests] == [1, 1]
    assert [request.chapter_id for request in provider.evidence_requests] == [
        "chapter-1",
        "chapter-2",
        "chapter-3",
    ]
    assert (
        stores.outbox.root
        / run_id
        / "outbox-chapter-3-chapter-3-v1-accepted.json"
    ).exists()
    accepted = [
        record.artifact
        for record in stores.chapters.list(run_id)
        if record.artifact.author_status == "accepted"
    ]
    assert sum(count_prose_characters(chapter.content) for chapter in accepted) == 5_701
    assert any(
        record.chapter_id == "chapter-3"
        and record.artifact.author_status == "accepted"
        for record in stores.chapters.list(run_id)
    )
    warning_codes = [
        event.payload["code"]
        for event in stores.events.read(run_id)
        if event.type == "quality.warning"
    ]
    assert "book_length_soft_band" in warning_codes
    assert "chapter_severely_underlength" not in warning_codes


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
async def test_stage_unit_contract_violation_requires_explicit_regeneration(tmp_path) -> None:
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

    assert projection.status == "awaiting_decision"
    assert projection.failure is not None
    assert projection.failure["retryable"] is True
    assert projection.pending_decisions[0]["type"] == "stage_failure_decision"
    cast_keys = [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "cast"
    ]
    assert len(cast_keys) == 1
    assert ":repair-" not in cast_keys[0]
    rejected = stores.operations.read("run-contract-repair", cast_keys[0])
    assert rejected.status == "contract_rejected"
    assert rejected.provider_result is not None
    assert rejected.result is None
    assert rejected.usage["total_tokens"] == 3
    usage = stores.operations.usage_summary("run-contract-repair")
    assert usage.returned_operations >= 1
    assert usage.contract_rejected_operations == 1
    assert usage.failed_operations == 0

    decision = dict(projection.pending_decisions[0])
    completed = await runtime.resume(
        "run-contract-repair",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
        },
    )

    assert completed.status == "completed", completed.failure
    cast_keys = [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "cast"
    ]
    assert len(cast_keys) == 2
    assert all(":repair-" not in operation_key for operation_key in cast_keys)
    assert stores.operations.read("run-contract-repair", cast_keys[1]).status == "succeeded"
    retry_request = next(
        request
        for request in provider.stage_requests
        if request.stage_id == "cast" and request.attempt == 2
    )
    assert "revision_request" not in retry_request.context["material"]


@pytest.mark.asyncio
async def test_volume_boundary_count_must_match_the_frozen_scale(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_proposal = provider.generate_proposal

    async def generate_two_natural_volume_arcs(request):
        if request.proposal_type != "volume_boundary":
            return await original_generate_proposal(request)
        provider.proposal_requests.append(request)
        turn_refs = [
            item["id"]
            for item in request.context["material"]["story_spine"]["turns"]
        ]
        boundary_index = max(1, len(turn_refs) // 2)
        return StructuredProviderResult(
            payload={
                "proposals": [
                    {
                        "boundary_key": "boundary-1",
                        "turn_refs": turn_refs[:boundary_index],
                        "reason": "建立并升级冲突",
                    },
                    {
                        "boundary_key": "boundary-2",
                        "turn_refs": turn_refs[boundary_index:],
                        "reason": "完成冲突闭合",
                    },
                ]
            },
            usage={"total_tokens": 2},
        )

    provider.generate_proposal = generate_two_natural_volume_arcs
    _create_run(stores, "run-volume-range")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-volume-range")

    assert projection.status == "failed"
    assert projection.failure is not None
    assert "requires exactly 1" in projection.failure["message"]
    boundary_request = next(
        request
        for request in provider.proposal_requests
        if request.proposal_type == "volume_boundary"
    )
    scale_plan = boundary_request.context["material"]["scale_plan"]
    assert scale_plan["volume_target"] == 1
    assert scale_plan["volume_range"] == [1, 1]


@pytest.mark.asyncio
async def test_volume_boundary_count_rejects_extra_model_authored_volumes(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_proposal = provider.generate_proposal

    async def generate_two_boundaries(request):
        if request.proposal_type != "volume_boundary":
            return await original_generate_proposal(request)
        provider.proposal_requests.append(request)
        turn_refs = [
            item["id"]
            for item in request.context["material"]["story_spine"]["turns"]
        ]
        boundary_index = max(1, len(turn_refs) // 2)
        return StructuredProviderResult(
            payload={
                "proposals": [
                    {
                        "boundary_key": "boundary-1",
                        "turn_refs": turn_refs[:boundary_index],
                        "reason": "第一阶段冲突形成局部闭合",
                    },
                    {
                        "boundary_key": "boundary-2",
                        "turn_refs": turn_refs[boundary_index:],
                        "reason": "第二阶段完成终局闭合",
                    },
                ]
            },
            usage={"total_tokens": 2},
        )

    provider.generate_proposal = generate_two_boundaries
    _create_run(
        stores,
        "run-volume-cap",
        volume_candidate_cap=1,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-volume-cap")

    assert projection.status == "failed"
    assert projection.failure is not None
    assert "requires exactly 1" in projection.failure["message"]


@pytest.mark.asyncio
async def test_guarded_failure_appends_terminal_run_failed_event(tmp_path) -> None:
    """SSE observers must see exactly one terminal event when the graph halts.

    `derive_cast_demand` failures previously ended the graph without any
    run.failed event, leaving live monitors showing an auto-advancing run.
    """
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()

    original_generate_proposal = provider.generate_proposal

    async def generate_role_demand_always_invalid(request):
        if request.proposal_type == "role_demand":
            raise ProviderResponseError("unauthorized", "Provider rejected the API key")
        return await original_generate_proposal(request)

    provider.generate_proposal = generate_role_demand_always_invalid
    _create_run(stores, "run-halt-event")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await runtime.start("run-halt-event")

    assert projection.status == "failed"
    terminal = [
        event for event in stores.events.read("run-halt-event") if event.type == "run.failed"
    ]
    assert len(terminal) == 1
    assert terminal[0].payload["node_id"] == "cast.derive_role_demand"
    assert "rejected the API key" in terminal[0].payload["message"]


@pytest.mark.asyncio
async def test_role_demand_contract_failure_uses_one_private_repair_operation(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = ContractFailingRoleDemandProvider()
    run_id = "run-role-demand-contract-repair"
    _create_run(stores, run_id, quality_mode="balanced", word_target_soft=4_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(run_id)
    for expected_stage in ("brief", "spine"):
        assert paused.active_stage_id == expected_stage
        decision = dict(paused.pending_decisions[0])
        paused = await runtime.resume(
            run_id,
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert paused.status == "awaiting_decision", paused.failure
    assert paused.active_stage_id == "cast"
    role_requests = [
        request
        for request in provider.proposal_requests
        if request.proposal_type == "role_demand"
    ]
    assert [request.operation_key for request in role_requests] == [
        f"{run_id}:role_demand:proposal:1",
        f"{run_id}:role_demand:proposal:1:contract-repair-1",
    ]
    assert "revision_request" not in role_requests[0].context["material"]
    assert role_requests[1].context["material"]["revision_request"]["direction"].startswith(
        "上一份 Role Demand 候选未通过冻结合同"
    )

    first = stores.operations.read(run_id, role_requests[0].operation_key)
    second = stores.operations.read(run_id, role_requests[1].operation_key)
    assert first.status == "failed"
    assert first.diagnostic["code"] == "structured_contract_invalid"
    assert second.status == "succeeded"
    snapshots = stores.operations.provider_inputs.list(run_id)
    first_snapshot = next(
        item for item in snapshots if item.operation_key == role_requests[0].operation_key
    )
    second_snapshot = next(
        item for item in snapshots if item.operation_key == role_requests[1].operation_key
    )
    assert first_snapshot.request_signature != second_snapshot.request_signature
    assert "revision_request" not in first_snapshot.input.structured_context["material"]
    assert "revision_request" in second_snapshot.input.structured_context["material"]


@pytest.mark.asyncio
async def test_stage_unit_transient_network_error_retries_and_completes(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_stage = provider.generate_stage
    dropped_once = {"done": False}
    observed_keys: list[str] = []

    async def generate_stage_with_one_network_drop(request):
        observed_keys.append(request.operation_key)
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
    brief_key = "run-network-retry:brief:generate:1"
    assert observed_keys[:2] == [brief_key, brief_key]
    brief_keys = [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "brief"
    ]
    assert brief_keys == [brief_key]
    receipt = stores.operations.read("run-network-retry", brief_key)
    assert receipt.status == "succeeded"
    assert receipt.diagnostic["transport_attempts"] == 2
    snapshots = [
        item
        for item in stores.operations.provider_inputs.list("run-network-retry")
        if item.operation_key == brief_key
    ]
    assert len(snapshots) == 1


@pytest.mark.asyncio
async def test_planning_proposal_transient_network_error_reuses_one_frozen_operation(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_proposal = provider.generate_proposal
    dropped_once = {"done": False}
    observed_keys: list[str] = []

    async def generate_proposal_with_one_network_drop(request):
        if request.proposal_type == "spine_review":
            observed_keys.append(request.operation_key)
            if not dropped_once["done"]:
                dropped_once["done"] = True
                raise ProviderResponseError(
                    "network_error", "Provider network error: APIConnectionError"
                )
        return await original_generate_proposal(request)

    provider.generate_proposal = generate_proposal_with_one_network_drop
    _create_run(stores, "run-proposal-network-retry")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-proposal-network-retry")

    assert projection.status == "completed", projection.failure
    operation_key = "run-proposal-network-retry:spine_review:proposal:1:initial"
    assert observed_keys[:2] == [operation_key, operation_key]
    receipt = stores.operations.read("run-proposal-network-retry", operation_key)
    assert receipt.status == "succeeded"
    assert receipt.diagnostic["transport_attempts"] == 2
    snapshots = [
        item
        for item in stores.operations.provider_inputs.list("run-proposal-network-retry")
        if item.operation_key == operation_key
    ]
    assert len(snapshots) == 1


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

    for scene_index in (1, 2):
        receipt = stores.operations.read(
            "run-provider-replay",
            f"run-provider-replay:chapter-1:scene-{scene_index}:generate:1.1",
        )
        assert receipt.status == "succeeded"
    assert [request.operation_key for request in provider.chapter_requests] == [
        "run-provider-replay:chapter-1:scene-1:generate:1.1",
        "run-provider-replay:chapter-1:scene-2:generate:1.1",
    ]

    monkeypatch.setattr(stores.chapters, "write", original_write)
    recovered = await runtime.recover("run-provider-replay")

    assert recovered.status == "completed", recovered.failure
    assert [request.operation_key for request in provider.chapter_requests] == [
        "run-provider-replay:chapter-1:scene-1:generate:1.1",
        "run-provider-replay:chapter-1:scene-2:generate:1.1",
        "run-provider-replay:chapter-2:scene-1:generate:1.1",
        "run-provider-replay:chapter-2:scene-2:generate:1.1",
    ]


@pytest.mark.asyncio
async def test_detail_layout_receipt_replays_without_a_second_provider_call(
    tmp_path,
    monkeypatch,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-detail-layout-replay")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    original_succeed = stores.operations.succeed
    stopped = False

    def stop_after_layout_receipt(run_id, operation_key, *args, **kwargs):
        nonlocal stopped
        result = original_succeed(run_id, operation_key, *args, **kwargs)
        if (
            operation_key
            == "run-detail-layout-replay:detail_layout:proposal:1:volume-1:turn-window-1"
            and not stopped
        ):
            stopped = True
            raise SimulatedProcessStop("process stopped after Detail layout receipt")
        return result

    monkeypatch.setattr(stores.operations, "succeed", stop_after_layout_receipt)
    with pytest.raises(SimulatedProcessStop, match="Detail layout receipt"):
        await runtime.start("run-detail-layout-replay")

    receipt = stores.operations.read(
        "run-detail-layout-replay",
        "run-detail-layout-replay:detail_layout:proposal:1:volume-1:turn-window-1",
    )
    assert receipt.status == "succeeded"
    assert [
        request.proposal_type
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    ] == ["detail_layout"]

    monkeypatch.setattr(stores.operations, "succeed", original_succeed)
    recovered = await runtime.recover("run-detail-layout-replay")

    assert recovered.status == "completed", recovered.failure
    assert [
        request.proposal_type
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    ] == ["detail_layout"]


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
    _create_run(stores, "run-cast-batches", word_target_soft=60_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-cast-batches")

    assert projection.status == "completed", projection.failure
    cast_requests = [request for request in provider.stage_requests if request.stage_id == "cast"]
    assert [len(request.context["material"]["subject_refs"]) for request in cast_requests] == [5, 1]
    artifact = stores.artifacts.latest("run-cast-batches", "cast").payload
    assert [subject["id"] for subject in artifact["subjects"]] == [
        f"subject-{index}" for index in range(1, 7)
    ]
    assert artifact["subjects"][0]["debut"] == "chapter:1"
    # The 60k Run freezes 24 chapters (20-30 feasible). Cast projection must
    # follow that exact target instead of pulling every debut toward chapter 20.
    assert artifact["subjects"][1]["debut"] == "chapter:1-5"
    relation_request = next(
        request
        for request in provider.proposal_requests
        if request.proposal_type == "cast_relation"
    )
    assert len(relation_request.context["material"]["subjects"]) == 6


@pytest.mark.asyncio
async def test_large_fake_flow_stays_distinct_after_detail_catalog_cycle(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(
        stores,
        "run-large-fake-detail-cycle",
        word_target_soft=65_000,
        include_cover_image=False,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-large-fake-detail-cycle")

    assert projection.status == "completed", projection.failure
    detail = stores.artifacts.latest("run-large-fake-detail-cycle", "detail").payload
    assert len(detail["chapters"]) == 26
    assert stores.operations.usage_summary(
        "run-large-fake-detail-cycle"
    ).failed_operations == 0


@pytest.mark.asyncio
async def test_cast_regeneration_keeps_stage_feedback_inside_each_dossier_batch(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider(subject_count=6)
    _create_run(stores, "run-cast-batch-revision", quality_mode="balanced", word_target_soft=60_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-cast-batch-revision")
    for stage_id in ("brief", "spine"):
        assert projection.active_stage_id == stage_id
        decision = dict(projection.pending_decisions[0])
        projection = await runtime.resume(
            "run-cast-batch-revision",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert projection.active_stage_id == "cast"
    decision = dict(projection.pending_decisions[0])
    direction = "主体一延后登台，主体二保持历史主体，其余人物保持原有职责。"
    revised = await runtime.resume(
        "run-cast-batch-revision",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
            "direction": direction,
        },
    )

    assert revised.status == "awaiting_decision", revised.failure
    second_attempt = [
        request
        for request in provider.stage_requests
        if request.stage_id == "cast" and request.attempt == 2
    ]
    assert [len(request.context["material"]["subject_refs"]) for request in second_attempt] == [
        5,
        1,
    ]
    assert all(
        request.context["material"]["revision_request"] == {"direction": direction}
        for request in second_attempt
    )
    assert {
        ref["id"]
        for request in second_attempt
        for ref in request.context["material"]["subject_refs"]
    } == {f"subject-{index}" for index in range(1, 7)}


@pytest.mark.asyncio
async def test_volume_generation_isolates_each_boundary_and_regeneration_attempt(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original_generate_stage = provider.generate_stage
    original_generate_proposal = provider.generate_proposal

    async def generate_twelve_turn_spine(request):
        result = await original_generate_stage(request)
        if request.stage_id != "spine":
            return result
        return result.model_copy(
            update={
                "payload": {
                    **result.payload,
                        "turns": fake_spine_payload(12)["turns"],
                }
            }
        )

    async def generate_two_volume_boundaries(request):
        if request.proposal_type != "volume_boundary":
            return await original_generate_proposal(request)
        provider.proposal_requests.append(request)
        return StructuredProviderResult(
            payload={
                "proposals": [
                    {
                        "boundary_key": "boundary-1",
                        "turn_refs": [f"turn-{index}" for index in range(1, 7)],
                        "reason": "启动调查并形成第一份可公开证据",
                    },
                    {
                        "boundary_key": "boundary-2",
                        "turn_refs": [f"turn-{index}" for index in range(7, 13)],
                        "reason": "广播行动完成终局公开",
                    },
                ]
            },
            usage={"total_tokens": 2},
        )

    provider.generate_stage = generate_twelve_turn_spine
    provider.generate_proposal = generate_two_volume_boundaries
    _create_run(
        stores,
        "run-volume-isolation",
        quality_mode="balanced",
        word_target_soft=60_000,
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-volume-isolation")
    while projection.active_stage_id != "volumes":
        assert projection.pending_decisions, (
            projection.status,
            projection.active_stage_id,
            projection.failure,
        )
        decision = dict(projection.pending_decisions[0])
        assert decision["type"] == "stage_artifact_decision"
        projection = await runtime.resume(
            "run-volume-isolation",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert projection.status == "awaiting_decision", projection.failure
    first_attempt = [
        request for request in provider.stage_requests if request.stage_id == "volumes"
    ]
    assert [request.operation_key for request in first_attempt] == [
        f"run-volume-isolation:volumes:generate:1:volume-{index}"
        for index in range(1, 3)
    ]
    expected_turns = [
        [f"turn-{index}" for index in range(1, 7)],
        [f"turn-{index}" for index in range(7, 13)],
    ]
    for request, turn_refs in zip(first_attempt, expected_turns):
        material = request.context["material"]
        assert "story_spine" not in material
        assert "volume_boundaries" not in material
        assert "thread_ids" not in material
        assert [turn["id"] for turn in material["volume_spine_turns"]] == turn_refs
        assert material["volume_boundary"]["turn_refs"] == turn_refs
    assert "previous_volume_handoff" not in first_attempt[0].context["material"]
    assert first_attempt[1].context["material"]["previous_volume_handoff"] == {
        "title": "雾港1卷",
        "closure": "旧案真相公开但记忆受损",
    }
    assert first_attempt[1].context["material"]["reserved_titles"] == ["雾港1卷"]

    candidate_ref = projection.pending_decisions[0]["artifact_ref"]
    candidate = stores.artifacts.read("run-volume-isolation", candidate_ref).payload
    assert [volume["turn_refs"] for volume in candidate["volumes"]] == expected_turns
    assert all("thread_ids" not in volume for volume in candidate["volumes"])

    decision = dict(projection.pending_decisions[0])
    revised = await runtime.resume(
        "run-volume-isolation",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
            "direction": "保持代码冻结的两卷规模，重新调整自然边界并确保每卷不提前消费下一卷事件。",
        },
    )

    assert revised.status == "awaiting_decision", revised.failure
    all_volume_requests = [
        request for request in provider.stage_requests if request.stage_id == "volumes"
    ]
    assert [request.operation_key for request in all_volume_requests[2:]] == [
        f"run-volume-isolation:volumes:generate:2:volume-{index}"
        for index in range(1, 3)
    ]
    assert all(
        request.context["material"]["revision_request"]["direction"].startswith(
            "保持代码冻结的两卷规模"
        )
        for request in all_volume_requests[2:]
    )
    boundary_requests = [
        request
        for request in provider.proposal_requests
        if request.proposal_type == "volume_boundary"
    ]
    assert [request.operation_key for request in boundary_requests] == [
        "run-volume-isolation:volume_boundary:proposal:1",
        "run-volume-isolation:volume_boundary:proposal:2",
    ]
    assert boundary_requests[1].context["material"]["volume_boundaries"] == {
        "proposals": []
    }
    assert boundary_requests[1].context["material"]["revision_request"] == {
        "direction": "保持代码冻结的两卷规模，重新调整自然边界并确保每卷不提前消费下一卷事件。"
    }


@pytest.mark.asyncio
async def test_cast_group_name_collision_requires_explicit_regeneration(tmp_path) -> None:
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
            payload["subjects"][0]["name"] = "林岚"
            return result.model_copy(update={"payload": payload})
        return result

    provider.generate_stage = generate_stage_with_name_collision
    _create_run(stores, "run-cast-collision", word_target_soft=60_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-cast-collision")

    assert projection.status == "awaiting_decision"
    assert projection.failure is not None
    assert projection.failure["retryable"] is True
    assert projection.pending_decisions[0]["type"] == "stage_failure_decision"
    second_group_requests = [
        request
        for request in provider.stage_requests
        if request.stage_id == "cast"
        and request.context["material"]["subject_refs"][0]["id"] == "subject-6"
    ]
    assert len(second_group_requests) == 1
    assert ":repair-" not in second_group_requests[0].operation_key
    assert second_group_requests[0].context["material"]["reserved_names"] == ["林岚", "周屿", "苏禾", "陈砚", "顾遥"]

    decision = dict(projection.pending_decisions[0])
    completed = await runtime.resume(
        "run-cast-collision",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
        },
    )

    assert completed.status == "completed", completed.failure
    second_group_requests = [
        request
        for request in provider.stage_requests
        if request.stage_id == "cast"
        and request.context["material"]["subject_refs"][0]["id"] == "subject-6"
    ]
    assert len(second_group_requests) == 2
    assert "revision_request" not in second_group_requests[1].context["material"]
    assert all(":repair-" not in request.operation_key for request in second_group_requests)
    assert second_group_requests[1].context["material"]["reserved_names"] == ["林岚", "周屿", "苏禾", "陈砚", "顾遥"]


@pytest.mark.asyncio
async def test_cast_regeneration_rederives_role_demands_and_can_shrink_named_cast(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider(subject_count=4)
    original_generate_proposal = provider.generate_proposal

    async def generate_proposal_with_cast_revision(request):
        result = await original_generate_proposal(request)
        revision = request.context["material"].get("revision_request")
        if request.proposal_type != "role_demand" or not revision:
            return result
        return result.model_copy(
            update={"payload": {"proposals": result.payload["proposals"][:3]}}
        )

    provider.generate_proposal = generate_proposal_with_cast_revision
    _create_run(stores, "run-cast-demand-redraft", quality_mode="balanced", word_target_soft=40_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start("run-cast-demand-redraft")
    for stage_id in ("brief", "spine"):
        assert paused.active_stage_id == stage_id
        decision = dict(paused.pending_decisions[0])
        paused = await runtime.resume(
            "run-cast-demand-redraft",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert paused.active_stage_id == "cast"
    first_candidate = stores.artifacts.read(
        "run-cast-demand-redraft", paused.pending_decisions[0]["artifact_ref"]
    )
    assert len(first_candidate.payload["subjects"]) == 4

    decision = dict(paused.pending_decisions[0])
    revised = await runtime.resume(
        "run-cast-demand-redraft",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
            "direction": "机构保持非人格化，只保留不可合并的具名行动者。",
        },
    )

    assert revised.status == "awaiting_decision", revised.failure
    assert revised.active_stage_id == "cast"
    second_candidate = stores.artifacts.read(
        "run-cast-demand-redraft", revised.pending_decisions[0]["artifact_ref"]
    )
    assert len(second_candidate.payload["subjects"]) == 3
    role_requests = [
        request
        for request in provider.proposal_requests
        if request.proposal_type == "role_demand"
    ]
    assert [request.operation_key for request in role_requests] == [
        "run-cast-demand-redraft:role_demand:proposal:1",
        "run-cast-demand-redraft:role_demand:proposal:2",
    ]
    assert role_requests[-1].context["material"]["revision_request"] == {
        "direction": "机构保持非人格化，只保留不可合并的具名行动者。"
    }
    relation_requests = [
        request
        for request in provider.proposal_requests
        if request.proposal_type == "cast_relation"
    ]
    assert relation_requests[-1].context["material"]["revision_request"] == {
        "direction": "机构保持非人格化，只保留不可合并的具名行动者。"
    }


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
    assert revised.manifest.optional[-2] == "revision.source_draft"
    assert json.loads(revised.manifest.snippets[-2].text)["content"]
    assert revised_pause.context_manifest_ref == revised.manifest_id
    assert [request.chapter_id for request in provider.chapter_requests] == [
        "chapter-1",
        "chapter-1",
        "chapter-1",
        "chapter-1",
    ]
    provider_manifest = provider.chapter_requests[-1].context["material"]
    assert set(provider_manifest) == {"chapter_context_manifest"}
    scene_manifest = provider_manifest["chapter_context_manifest"]
    assert scene_manifest["task"] == revised.manifest.task
    assert "scene.execution" in scene_manifest["required"]
    assert any(
        snippet["ref"] == "revision.source_draft"
        for snippet in scene_manifest["snippets"]
    )

    replay = await runtime.resume("run-revision-manifest", command)

    assert replay.pending_decisions == revised_pause.pending_decisions
    assert len(provider.chapter_requests) == 4
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
async def test_chapter_writeback_clears_recovery_refs_before_next_decision(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    source_run_id = "run-writeback-branch-source"
    _create_run(stores, source_run_id, quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    first_pause = await _advance_to_first_chapter(runtime, source_run_id)
    decision = dict(first_pause.pending_decisions[0])

    second_pause = await runtime.resume(
        source_run_id,
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "accept",
        },
    )

    state = await runtime.state(source_run_id)
    assert second_pause.active_chapter_number == 2
    assert state["pending_evidence_refs"] == []
    assert state["pending_writeback_ref"] == ""
    branch = await NarrativeBranchService(runtime).create(
        source_run_id=source_run_id,
        target_run_id="run-writeback-branch-target",
        checkpoint_id=second_pause.checkpoint_id,
    )
    assert branch.status == "awaiting_decision"
    assert branch.active_chapter_number == 2


async def _advance_to_detail_decision(runtime: NarrativeRuntime, run_id: str):
    projection = await runtime.start(run_id)
    for stage_id in ("brief", "spine", "cast", "volumes"):
        assert projection.active_stage_id == stage_id
        decision = dict(projection.pending_decisions[0])
        projection = await runtime.resume(
            run_id,
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )
    assert projection.status == "awaiting_decision"
    assert projection.active_stage_id == "detail"
    return projection


@pytest.mark.asyncio
async def test_branch_can_replace_only_future_provider_bindings(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    source_run_id = "run-future-binding-source"
    target_run_id = "run-future-binding-target"
    _create_run(stores, source_run_id, quality_mode="balanced", word_target_soft=60_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    paused = await _advance_to_detail_decision(runtime, source_run_id)
    replacement = provider_binding("text", model="deepseek-v4-pro")
    override = BranchBindingOverride(
        source_workflow_id="workflow-current",
        source_workflow_revision="29.2.0-scene-text",
        source_workflow_digest="b" * 64,
        stages=["text"],
    )

    await NarrativeBranchService(runtime).create(
        source_run_id=source_run_id,
        target_run_id=target_run_id,
        checkpoint_id=paused.checkpoint_id,
        provider_binding_overrides={"text": replacement},
        binding_override=override,
    )

    source = stores.runs.definition(source_run_id)
    target = stores.runs.definition(target_run_id)
    assert source.provider_bindings["text"].model == "fake-model"
    assert target.provider_bindings["text"].model == "deepseek-v4-pro"
    assert target.provider_bindings["detail"] == source.provider_bindings["detail"]
    assert target.branch_origin is not None
    assert target.branch_origin.binding_override == override
    branch_event = stores.events.read(target_run_id)[0]
    assert branch_event.type == "branch.created"
    assert branch_event.payload["binding_override"] == override.model_dump(mode="json")


@pytest.mark.asyncio
async def test_branch_replaces_binding_for_current_artifact_decision(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    source_run_id = "run-current-binding-source"
    target_run_id = "run-current-binding-target"
    _create_run(stores, source_run_id, quality_mode="balanced", word_target_soft=60_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    paused = await _advance_to_detail_decision(runtime, source_run_id)
    override = BranchBindingOverride(
        source_workflow_id="workflow-current",
        source_workflow_revision="29.2.0-scene-text",
        source_workflow_digest="b" * 64,
        stages=["detail"],
    )

    branch = await NarrativeBranchService(runtime).create(
        source_run_id=source_run_id,
        target_run_id=target_run_id,
        checkpoint_id=paused.checkpoint_id,
        provider_binding_overrides={
            "detail": provider_binding("detail", model="deepseek-v4-pro")
        },
        binding_override=override,
    )

    assert branch.status == "awaiting_decision"
    assert stores.runs.definition(target_run_id).provider_bindings["detail"].model == "deepseek-v4-pro"


@pytest.mark.asyncio
async def test_branch_from_committed_stage_boundary_resumes_at_next_stage(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    source_run_id = "run-brief-boundary-source"
    target_run_id = "run-brief-boundary-target"
    _create_run(stores, source_run_id, quality_mode="balanced", word_target_soft=100_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(source_run_id)
    brief_decision = dict(paused.pending_decisions[0])
    paused = await runtime.resume(
        source_run_id,
        {
            "decision_id": brief_decision["decision_id"],
            "domain_revision": brief_decision["domain_revision"],
            "action": "accept",
        },
    )
    assert paused.active_stage_id == "spine"
    boundary = next(
        event
        for event in stores.events.read(source_run_id)
        if event.type == "checkpoint.saved"
        and event.stage_id == "brief"
        and event.payload == {"next": ["spine"]}
    )

    replacement_stages = ["spine", "cast", "volumes", "detail", "text", "cover"]
    replacements = {
        stage_id: provider_binding(stage_id, model="deepseek-v4-pro")
        for stage_id in replacement_stages
    }
    override = BranchBindingOverride(
        source_workflow_id="workflow-current",
        source_workflow_revision="29.29.0-first-visible-draft-stability",
        source_workflow_digest="b" * 64,
        stages=replacement_stages,
    )

    with pytest.raises(BranchConflictError, match="completed"):
        await NarrativeBranchService(runtime).create(
            source_run_id=source_run_id,
            target_run_id="run-brief-boundary-invalid",
            checkpoint_id=boundary.checkpoint_id,
            provider_binding_overrides={
                "brief": provider_binding("brief", model="deepseek-v4-pro")
            },
            binding_override=override.model_copy(update={"stages": ["brief"]}),
            branch_mode="stage_boundary",
        )
    assert not stores.runs.exists("run-brief-boundary-invalid")

    branch = await NarrativeBranchService(runtime).create(
        source_run_id=source_run_id,
        target_run_id=target_run_id,
        checkpoint_id=boundary.checkpoint_id,
        provider_binding_overrides=replacements,
        cover_asset_binding_override=cover_asset_binding(model="deepseek-image-v1"),
        binding_override=override,
        branch_mode="stage_boundary",
    )

    assert branch.status == "running"
    assert branch.active_stage_id == "brief"
    assert branch.pending_decisions == []
    assert set(branch.artifact_refs) == {"brief"}
    target = stores.runs.definition(target_run_id)
    assert target.branch_origin is not None
    assert target.branch_origin.frontier_mode == "stage_boundary"
    assert target.provider_bindings["spine"].model == "deepseek-v4-pro"
    assert target.provider_bindings["brief"].model == "fake-model"

    resumed = await runtime.recover(target_run_id)

    assert resumed.status == "awaiting_decision"
    assert resumed.active_stage_id == "spine"
    assert resumed.pending_decisions[0]["type"] == "stage_artifact_decision"
    assert set(resumed.artifact_refs) == {"brief"}


@pytest.mark.asyncio
async def test_branch_still_rejects_binding_override_for_completed_checkpoint_stage(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    source_run_id = "run-completed-binding-source"
    target_run_id = "run-completed-binding-target"
    _create_run(stores, source_run_id, quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    paused = await runtime.start(source_run_id)
    assert paused.active_stage_id == "brief"
    brief_decision = dict(paused.pending_decisions[0])
    paused = await runtime.resume(
        source_run_id,
        {
            "decision_id": brief_decision["decision_id"],
            "domain_revision": brief_decision["domain_revision"],
            "action": "accept",
        },
    )
    override = BranchBindingOverride(
        source_workflow_id="workflow-current",
        source_workflow_revision="29.2.0-scene-text",
        source_workflow_digest="b" * 64,
        stages=["brief"],
    )

    with pytest.raises(BranchConflictError, match="completed"):
        await NarrativeBranchService(runtime).create(
            source_run_id=source_run_id,
            target_run_id=target_run_id,
            checkpoint_id=paused.checkpoint_id,
            provider_binding_overrides={"brief": provider_binding("brief", model="deepseek-v4-pro")},
            binding_override=override,
        )
    assert not stores.runs.exists(target_run_id)


@pytest.mark.asyncio
async def test_cast_decision_branch_copies_all_referenced_provider_provenance(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider(subject_count=6)
    source_run_id = "run-cast-branch-source"
    target_run_id = "run-cast-branch-target"
    _create_run(stores, source_run_id, quality_mode="balanced", word_target_soft=60_000)
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(source_run_id)
    for stage_id in ("brief", "spine"):
        assert paused.active_stage_id == stage_id
        decision = dict(paused.pending_decisions[0])
        paused = await runtime.resume(
            source_run_id,
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert paused.status == "awaiting_decision"
    assert paused.active_stage_id == "cast"
    assert paused.pending_decisions[0]["type"] == "stage_artifact_decision"
    role_demand_key = next(
        request.operation_key
        for request in provider.proposal_requests
        if request.proposal_type == "role_demand"
    )
    dossier_keys = [
        request.operation_key
        for request in provider.stage_requests
        if request.stage_id == "cast"
    ]
    cast_relation_key = next(
        request.operation_key
        for request in provider.proposal_requests
        if request.proposal_type == "cast_relation"
    )
    assert len(dossier_keys) == 2
    cast_operation_keys = [role_demand_key, *dossier_keys, cast_relation_key]

    await NarrativeBranchService(runtime).create(
        source_run_id=source_run_id,
        target_run_id=target_run_id,
        checkpoint_id=paused.checkpoint_id,
    )

    target_receipts = {
        receipt.operation_key: receipt for receipt in stores.operations.list(target_run_id)
    }
    for source_key in cast_operation_keys:
        target_key = source_key.replace(source_run_id, target_run_id, 1)
        source_receipt = stores.operations.read(source_run_id, source_key)
        target_receipt = target_receipts[target_key]
        assert source_receipt.status == target_receipt.status == "succeeded"
        assert source_receipt.result == target_receipt.result
        source_input = stores.operations.provider_inputs.read(
            source_run_id,
            source_receipt.provider_input_ref,
        )
        target_input = stores.operations.provider_inputs.read(
            target_run_id,
            target_receipt.provider_input_ref,
        )
        assert source_input.input == target_input.input
        assert target_input.operation_key == target_key

    target_provider_receipts = [
        receipt for receipt in target_receipts.values() if receipt.provider_profile_id
    ]
    target_snapshots = stores.operations.provider_inputs.list(target_run_id)
    assert {receipt.provider_input_ref for receipt in target_provider_receipts} == {
        snapshot.snapshot_ref for snapshot in target_snapshots
    }


@pytest.mark.asyncio
async def test_branch_rejects_invalid_provider_snapshot_before_creating_target(
    tmp_path,
    monkeypatch,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-branch-invalid-source", quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    paused = await runtime.start("run-branch-invalid-source")
    original_read = stores.operations.provider_inputs.read

    def reject_source_snapshot(run_id: str, snapshot_ref: str):
        if run_id == "run-branch-invalid-source":
            raise ValueError("Provider input snapshot contains forbidden header field")
        return original_read(run_id, snapshot_ref)

    monkeypatch.setattr(stores.operations.provider_inputs, "read", reject_source_snapshot)

    with pytest.raises(ValueError, match="forbidden header field"):
        await NarrativeBranchService(runtime).create(
            source_run_id="run-branch-invalid-source",
            target_run_id="run-branch-invalid-target",
            checkpoint_id=paused.checkpoint_id,
        )

    assert not stores.runs.exists("run-branch-invalid-target")


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
    volume = {"volumes": [{"id": "volume-1", "title": "雾港残响", "promise": "p", "conflict": "c", "climax": "x", "climax_turn_ref": "turn-2", "closure": "z", "turn_refs": ["turn-2"], "cast_ids": ["subject-lin"], "length_hint": "short"}]}
    with pytest.raises(ValueError, match="unknown spine turns"):
        validate_artifact_vnext("volumes", volume, subject_ids={"subject-lin"}, turn_ids={"turn-1"})


@pytest.mark.asyncio
async def test_stage_candidate_allows_only_one_targeted_regeneration(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_run(stores, "run-stage-regeneration-limit", quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start("run-stage-regeneration-limit")
    decision = dict(paused.pending_decisions[0])
    second = await runtime.resume(
        "run-stage-regeneration-limit",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
            "direction": "收紧创作承诺",
        },
    )

    assert second.active_stage_id == "brief"
    assert second.pending_decisions[0]["allowed_actions"] == ["accept", "cancel"]
    assert second.pending_decisions[0]["regeneration_used"] == 1


@pytest.mark.asyncio
async def test_chapter_candidate_allows_only_one_targeted_regeneration(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    run_id = "run-chapter-regeneration-limit"
    _create_run(stores, run_id, quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    paused = await _advance_to_first_chapter(runtime, run_id)
    decision = dict(paused.pending_decisions[0])

    second = await runtime.resume(
        run_id,
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
            "direction": "减少解释并保持 handoff",
        },
    )

    assert second.pending_decisions[0]["chapter_id"] == "chapter-1"
    assert second.pending_decisions[0]["allowed_actions"] == ["accept", "cancel"]
    assert second.pending_decisions[0]["regeneration_used"] == 1


@pytest.mark.asyncio
async def test_fast_mode_stops_visibly_after_one_failed_hard_gate_regeneration(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = DeterministicConflictProvider()
    run_id = "run-fast-hard-blocker-exhausted"
    _create_run(stores, run_id, quality_mode="fast")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(run_id)

    assert paused.status == "awaiting_decision"
    decision = paused.pending_decisions[0]
    assert decision["type"] == "chapter_author_decision"
    assert decision["allowed_actions"] == ["cancel"]
    assert decision["quality_decision"]["structure_contract"] == "blocked"
    assert decision["quality_decision"]["regeneration_used"] == 1
    assert decision["quality_decision"]["contract_blockers"][0]["code"] == "time_rule_conflict"
    state = await runtime.state(run_id)
    assert state["chapter_attempts"]["chapter-1"] == 2


@pytest.mark.asyncio
async def test_fast_mode_stops_when_a_required_review_is_unavailable(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = UnavailableRequiredReviewProvider()
    run_id = "run-fast-required-review-unavailable"
    _create_run(stores, run_id, quality_mode="fast")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(run_id)

    assert paused.status == "awaiting_decision"
    decision = paused.pending_decisions[0]
    assert decision["type"] == "chapter_author_decision"
    assert decision["allowed_actions"] == ["cancel"]
    assert decision["review_status"]["required_review_unavailable"] == ["continuity"]
    blocker = decision["quality_decision"]["contract_blockers"][0]
    assert blocker["code"] == "required_review_unavailable"
    assert blocker["resolution"] == "manual"
    assert len(
        [request for request in provider.review_requests if request.role == "continuity"]
    ) == 1


@pytest.mark.asyncio
async def test_fast_mode_stops_before_cover_on_a_manuscript_contract_blocker(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = UnbalancedQuoteProvider()
    run_id = "run-fast-manuscript-blocker"
    _create_run(stores, run_id, quality_mode="fast")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await runtime.start(run_id)

    assert paused.status == "awaiting_decision"
    decision = paused.pending_decisions[0]
    assert decision["type"] == "manuscript_quality_decision"
    assert decision["allowed_actions"] == ["cancel"]
    assert decision["quality_report"]["blockers"][0]["code"] == (
        "punctuation_quote_unbalanced"
    )
    assert provider.cover_requests == []


@pytest.mark.asyncio
async def test_llm_chapter_finding_warns_and_projects_revision_evidence(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = HardConflictReviewProvider()
    run_id = "run-hard-review-gate"
    _create_run(stores, run_id, quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    paused = await _advance_to_first_chapter(runtime, run_id)
    decision = paused.pending_decisions[0]

    assert decision["allowed_actions"] == ["accept", "regenerate", "cancel"]
    quality_decision = decision["quality_decision"]
    assert paused.quality_decision is not None
    assert paused.quality_decision.model_dump(mode="json") == quality_decision
    assert quality_decision["contract_blockers"] == []
    assert quality_decision["review_warnings"][0]["code"] == "time_rule_conflict"
    assert quality_decision["review_warnings"][0]["source_severity"] == "blocking"
    assert "只修复以下审校问题" in quality_decision["regeneration_recommendation"]["direction"]
    required = next(
        event
        for event in stores.events.read(run_id)
        if event.type == "decision.required"
        and event.payload
        and event.payload.get("decision_id") == decision["decision_id"]
    )
    assert required.payload["quality_decision"] == quality_decision

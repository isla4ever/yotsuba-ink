from __future__ import annotations

import asyncio
import io
import json
import struct
import zipfile
import zlib
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ChapterGenerationRequest,
    ChapterReviewRequest,
    ChapterReviewResult,
    CoverImageRequest,
    ReviewFinding,
    StageGenerationRequest,
    StructuredProviderResult,
)
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.runtime.graph.branch_service import NarrativeBranchService
from novel_workflow.runtime.graph.chapter_decision import save_edited_chapter_candidate
from novel_workflow.runtime.graph.chapter_review import DEFAULT_REVIEWERS, freeze_review_roles
from novel_workflow.runtime.graph.execution_service import NarrativeExecutionService
from novel_workflow.runtime.graph.runtime import (
    DecisionReplayConflict,
    NarrativeRuntime,
    filesystem_stores,
)
from novel_workflow.runtime.graph.runtime import open_sqlite_runtime
from novel_workflow.storage.narrative_run_repository import (
    CoverAssetBinding,
    ExportPreferences,
    ProviderBinding,
)
from novel_workflow.workflows.book_scale_plan import BookScalePlan, build_book_scale_plan


def _run_contract_args() -> dict[str, Any]:
    return {
        "cover_asset_binding": CoverAssetBinding(
            provider_profile_id="fake-image",
            model="fake-image-model",
            candidate_count=3,
            size="256x384",
            quality="medium",
            failure_policy="fail_run",
        ),
        "export_preferences": ExportPreferences(format="zip"),
    }


def _book_plan(chapter_count: int) -> BookScalePlan:
    return build_book_scale_plan(
        target_mode="total_chapters",
        target_value=chapter_count,
    )


def test_deep_mode_freezes_every_parallel_reviewer_as_required() -> None:
    balanced = freeze_review_roles(DEFAULT_REVIEWERS, "balanced")
    deep = freeze_review_roles(DEFAULT_REVIEWERS, "deep")

    assert balanced["active_review_roles"][-1] == {"role": "prose", "required": False}
    assert all(item["required"] for item in deep["active_review_roles"])


class FakeNarrativeProvider:
    def __init__(self, chapter_count: int = 2) -> None:
        self.chapter_count = chapter_count
        self.stage_calls: list[str] = []
        self.stage_requests: list[StageGenerationRequest] = []
        self.chapter_calls: list[str] = []
        self.chapter_requests: list[ChapterGenerationRequest] = []
        self.review_calls: list[str] = []
        self.review_requests: list[ChapterReviewRequest] = []
        self.evidence_calls: list[str] = []
        self.image_calls: list[str] = []

    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        self.stage_calls.append(request.operation_key)
        self.stage_requests.append(request)
        payload = _stage_payload(request.stage_id, chapter_count=self.chapter_count)
        material = request.context.get("material") or {}
        if request.stage_id == "outline" and material.get("target_volume"):
            target = material["target_volume"]
            payload["volumes"][0]["id"] = target["id"]
            payload["volumes"][0]["chapter_window"] = target["chapter_window"]
        if request.stage_id == "detail" and material.get("target_chapters"):
            targets = {item["id"] for item in material["target_chapters"]}
            payload["chapters"] = [
                chapter for chapter in payload["chapters"] if chapter["id"] in targets
            ]
        return _response(payload)

    async def generate_chapter(self, request: ChapterGenerationRequest) -> StructuredProviderResult:
        self.chapter_calls.append(request.operation_key)
        self.chapter_requests.append(request)
        attempt = int(request.operation_key.rsplit(":", 1)[-1])
        return _response({
            "chapter_id": request.chapter_id,
            "version_id": f"{request.chapter_id}-v{attempt}",
            "title": f"第{request.chapter_number}章",
            "content": f"{request.chapter_id} 的冻结正文。",
            "author_status": "candidate",
        })

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage:
        self.image_calls.append(request.operation_key)
        return GeneratedImage(
            content=_png(256, 384, request.candidate_index),
            mime_type="image/png",
            provider_asset_id=f"provider-cover-{request.candidate_index}",
            usage={"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
        )

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        self.review_calls.append(request.operation_key)
        self.review_requests.append(request)
        return _response(ChapterReviewResult(role=request.role).model_dump(mode="json"))

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult:
        self.evidence_calls.append(request.operation_key)
        quote = request.content
        result = ChapterEvidenceResult.model_validate({
            "claims": [{
                "kind": "summary",
                "claim": f"{request.chapter_id} 已完成。",
                "spans": [{"start": 0, "end": len(quote), "quote": quote}],
            }]
        })
        return _response(result.model_dump(mode="json"))


class BlockingReviewProvider(FakeNarrativeProvider):
    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        self.review_calls.append(request.operation_key)
        findings = []
        if request.role == "continuity":
            findings.append(
                ReviewFinding(
                    code="continuity-conflict",
                    severity="blocking",
                    claim="本章与冻结交接冲突。",
                    evidence="候选正文中的明确句子。",
                )
            )
        result = ChapterReviewResult(role=request.role, findings=findings)
        return _response(result.model_dump(mode="json"))


class FailingStageProvider(FakeNarrativeProvider):
    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        self.stage_calls.append(request.operation_key)
        raise RuntimeError("stage provider unavailable")


class FailingChapterProvider(FakeNarrativeProvider):
    async def generate_chapter(self, request: ChapterGenerationRequest) -> StructuredProviderResult:
        self.chapter_calls.append(request.operation_key)
        raise RuntimeError("chapter provider unavailable")


class MismatchedChapterTargetProvider(FakeNarrativeProvider):
    async def generate_chapter(
        self, request: ChapterGenerationRequest
    ) -> StructuredProviderResult:
        response = await super().generate_chapter(request)
        return response.model_copy(
            update={"payload": {**response.payload, "chapter_id": "chapter-wrong"}}
        )


class FailingEvidenceProvider(FakeNarrativeProvider):
    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        response = await super().generate_stage(request)
        payload = response.payload
        if request.stage_id == "detail":
            return _response({"chapters": payload["chapters"][:1]})
        return response

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult:
        self.evidence_calls.append(request.operation_key)
        raise RuntimeError("evidence provider unavailable")


class SimulatedProcessStop(BaseException):
    pass


class InterruptedParallelReviewProvider(FakeNarrativeProvider):
    def __init__(self) -> None:
        super().__init__(chapter_count=1)
        self.interrupt_reviews = True
        self._continuity_done = asyncio.Event()
        self._prose_done = asyncio.Event()

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        self.review_calls.append(request.operation_key)
        if not self.interrupt_reviews:
            return _response(ChapterReviewResult(role=request.role).model_dump(mode="json"))
        if request.role == "continuity":
            self._continuity_done.set()
            return _response(ChapterReviewResult(role=request.role).model_dump(mode="json"))
        if request.role == "prose":
            self._prose_done.set()
            return _response(ChapterReviewResult(role=request.role).model_dump(mode="json"))
        await self._continuity_done.wait()
        await self._prose_done.wait()
        await asyncio.sleep(0.05)
        raise SimulatedProcessStop("simulated process stop during parallel review")


class UnavailableRequiredAndOptionalReviewProvider(FakeNarrativeProvider):
    def __init__(self) -> None:
        super().__init__(chapter_count=1)

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        self.review_calls.append(request.operation_key)
        if request.role in {"continuity", "prose"}:
            raise RuntimeError(f"{request.role} reviewer unavailable")
        return _response(ChapterReviewResult(role=request.role).model_dump(mode="json"))


class MismatchedReviewRoleProvider(FakeNarrativeProvider):
    async def review_chapter(
        self, request: ChapterReviewRequest
    ) -> StructuredProviderResult:
        self.review_calls.append(request.operation_key)
        role = "character" if request.role == "continuity" else request.role
        return _response(ChapterReviewResult(role=role).model_dump(mode="json"))


def _response(payload: dict[str, Any]) -> StructuredProviderResult:
    return StructuredProviderResult(
        payload=payload,
        usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        diagnostic={"finish_reason": "stop"},
    )


@pytest.mark.asyncio
async def test_langgraph_is_the_single_runtime_with_interrupts_and_sequential_chapters(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-graph-1",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-graph-1")
    decision_types: list[str] = []
    while projection.pending_decisions:
        decision = projection.pending_decisions[0]
        decision_types.append(str(decision["type"]))
        projection = await runtime.resume(
            "run-graph-1",
            _accept_command(stores, "run-graph-1", decision),
        )

    assert projection.status == "completed"
    assert decision_types == (
        ["stage_artifact_decision"] * 5
        + ["chapter_author_decision"] * 2
        + ["stage_artifact_decision"] * 2
    )
    assert provider.stage_calls == [
        "run-graph-1:info:generate:1",
        "run-graph-1:characters:generate:1",
        "run-graph-1:summary:generate:1",
        "run-graph-1:outline:generate:1:volume-1",
        "run-graph-1:detail:generate:1:chapters-1-2",
        "run-graph-1:cover:generate:1",
    ]
    assert provider.chapter_calls == [
        "run-graph-1:chapter-1:generate:1",
        "run-graph-1:chapter-2:generate:1",
    ]
    assert len(provider.review_calls) == 6
    assert provider.evidence_calls == [
        "run-graph-1:chapter-1:evidence:chapter-1-v1-accepted",
        "run-graph-1:chapter-2:evidence:chapter-2-v1-accepted",
    ]
    assert all("chapter-1" in item for item in provider.review_calls[:3])
    assert all("chapter-2" in item for item in provider.review_calls[3:])
    contexts = {request.stage_id: request.context for request in provider.stage_requests}
    assert contexts["info"]["sources"] == {}
    assert contexts["info"]["material"]["project_brief"] == {"genre": "悬疑"}
    assert set(contexts["characters"]["material"]) == {"book_scale_plan", "story_brief"}
    assert set(contexts["summary"]["material"]) == {
        "book_scale_plan",
        "story_brief",
        "character_bible",
    }
    assert set(contexts["outline"]["material"]) == {
        "book_scale_plan",
        "story_brief",
        "character_bible",
        "summary",
        "target_volume",
    }
    assert set(contexts["detail"]["material"]) == {
        "book_scale_plan",
        "story_brief",
        "character_bible",
        "summary",
        "outline",
        "obligation_registry",
        "target_chapters",
    }
    assert contexts["detail"]["material"]["obligation_registry"] == {
        "character": [{"id": "char-lin", "label": "林默"}],
        "thread": [],
        "world_rule": [
            {"id": "world-rule-1", "label": "公开广播会覆盖个人记忆"}
        ],
        "promise": [
            {
                "id": "thematic-question",
                "label": "共同记忆是否值得以个人真相为代价？",
            },
            {"id": "ending-promise", "label": "真相会被公开。"},
        ],
    }
    assert contexts["outline"]["material"]["target_volume"]["chapter_window"] == "chapter:1-2"
    assert contexts["detail"]["material"]["target_chapters"] == [
        {"id": "chapter-1", "number": 1},
        {"id": "chapter-2", "number": 2},
    ]
    assert set(contexts["cover"]["material"]) == {
        "story",
        "cast",
        "narrative_arc",
        "volume_objectives",
        "chapter_motifs",
    }
    assert all("project_inputs" not in json.dumps(context) for context in contexts.values())
    assert all("upstream_artifacts" not in json.dumps(context) for context in contexts.values())
    assert provider.chapter_requests[0].context["material"]["previous_accepted_chapter"] is None
    previous = provider.chapter_requests[1].context["material"]["previous_accepted_chapter"]
    assert previous["version_id"] == "chapter-1-v1-accepted"
    assert previous["content"] == "chapter-1 的冻结正文。"
    reviews = {request.role: request.context["material"] for request in provider.review_requests[:3]}
    assert all(material["chapter"]["content"] == "chapter-1 的冻结正文。" for material in reviews.values())
    assert "character_bible" in reviews["character"]
    assert "previous_accepted_chapter" in reviews["continuity"]
    assert "voice" in reviews["prose"]
    assert "character_bible" not in reviews["prose"]
    assert [item.artifact.author_status for item in stores.chapters.list("run-graph-1")].count("accepted") == 2
    assert stores.artifacts.latest("run-graph-1", "export").payload["chapter_version_ids"] == [
        "chapter-1-v1-accepted",
        "chapter-2-v1-accepted",
    ]
    exports = stores.exports.list("run-graph-1")
    assert len(exports) == 1
    export_record, export_content = stores.exports.content(
        "run-graph-1", exports[0].export_id
    )
    assert export_record.format == "zip"
    assert export_record.chapter_version_ids == [
        "chapter-1-v1-accepted",
        "chapter-2-v1-accepted",
    ]
    with zipfile.ZipFile(io.BytesIO(export_content)) as archive:
        assert archive.namelist() == ["雾港母带.md", "cover.png", "manifest.json"]
        manuscript = archive.read("雾港母带.md").decode("utf-8")
        assert "chapter-1 的冻结正文。" in manuscript
        assert "chapter-2 的冻结正文。" in manuscript
    assert len(stores.evidence.list("run-graph-1")) == 2
    assert len(stores.canon.facts("run-graph-1")) == 2
    assert len(stores.wiki.list("run-graph-1")) == 2
    events = stores.events.read("run-graph-1")
    assert [event.type for event in events].count("evidence.proposed") == 2
    assert [event.type for event in events].count("writeback.committed") == 2
    assert [event.type for event in events].count("review.started") == 6
    # Export has no author interrupt, but its deterministic policy acceptance
    # uses the same receipt contract as the eight explicit decisions above.
    assert [event.type for event in events].count("decision.resolved") == 9
    assert [event.type for event in events].count("checkpoint.saved") > 0

    usage = stores.operations.usage_summary("run-graph-1")
    assert usage.provider_operations == 19
    assert usage.succeeded_operations == 19
    assert usage.failed_operations == 0
    assert usage.total_tokens == 175
    assert stores.runs.read("run-graph-1").provider_usage == usage
    latest_node_usage = next(
        event.payload["provider_usage"]
        for event in reversed(events)
        if event.type == "node.completed" and event.payload
    )
    assert latest_node_usage["provider_operations"] == 19
    assert latest_node_usage["total_tokens"] == 175

    graph_state = await runtime.state("run-graph-1")
    serialized = json.dumps(graph_state, ensure_ascii=False)
    assert "冻结正文" not in serialized
    assert "upstream_artifacts" not in serialized
    assert graph_state["chapter_version_refs"] == {
        "chapter-1": "chapter-1-v1-accepted",
        "chapter-2": "chapter-2-v1-accepted",
    }


@pytest.mark.asyncio
async def test_fast_mode_completes_three_chapters_through_the_same_graph_policy(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "fast-three-chapter-runtime")
    provider = FakeNarrativeProvider(chapter_count=3)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-fast-three",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="fast",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(3),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-fast-three")

    assert projection.status == "completed"
    assert projection.pending_decisions == []
    assert provider.chapter_calls == [
        f"run-fast-three:chapter-{number}:generate:1" for number in range(1, 4)
    ]
    assert len(provider.review_calls) == 9
    assert len(stores.evidence.list("run-fast-three")) == 3
    assert len(stores.canon.facts("run-fast-three")) == 3
    assert stores.artifacts.latest("run-fast-three", "export").payload[
        "chapter_version_ids"
    ] == [f"chapter-{number}-v1-accepted" for number in range(1, 4)]


@pytest.mark.asyncio
async def test_long_outline_and_detail_use_receipted_structured_units(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "long-structured-runtime")
    provider = FakeNarrativeProvider(chapter_count=18)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-long-structured",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(18),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-long-structured")
    while projection.pending_decisions:
        decision = projection.pending_decisions[0]
        if decision["node_id"] == "detail.human_decision":
            break
        projection = await runtime.resume(
            "run-long-structured",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert provider.stage_calls[-5:] == [
        "run-long-structured:outline:generate:1:volume-1",
        "run-long-structured:outline:generate:1:volume-2",
        "run-long-structured:detail:generate:1:chapters-1-8",
        "run-long-structured:detail:generate:1:chapters-9-16",
        "run-long-structured:detail:generate:1:chapters-17-18",
    ]
    detail = stores.artifacts.latest("run-long-structured", "detail", status="candidate")
    assert [chapter["id"] for chapter in detail.payload["chapters"]] == [
        f"chapter-{number}" for number in range(1, 19)
    ]
    for operation_key in provider.stage_calls[-5:]:
        receipt = stores.operations.read("run-long-structured", operation_key)
        assert receipt.kind == "stage_generation_unit"
        assert receipt.status == "succeeded"


@pytest.mark.asyncio
async def test_sqlite_checkpoint_resumes_the_same_interrupt_without_duplicate_provider_call(tmp_path) -> None:
    root = tmp_path / "durable-runtime"
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores = filesystem_stores(root)
    stores.runs.create(
        run_id="run-durable-1",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as first_runtime:
        first = await first_runtime.start("run-durable-1")
        info_decision = first.pending_decisions[0]
    async with open_sqlite_runtime(root, provider) as resumed_runtime:
        second = await resumed_runtime.resume(
            "run-durable-1",
            {
                "decision_id": info_decision["decision_id"],
                "domain_revision": info_decision["domain_revision"],
                "action": "accept",
            },
        )

    assert second.status == "awaiting_decision"
    assert second.active_stage_id == "characters"
    assert provider.stage_calls == [
        "run-durable-1:info:generate:1",
        "run-durable-1:characters:generate:1",
    ]


@pytest.mark.asyncio
async def test_duplicate_stage_decision_is_idempotent_and_conflicts_do_not_fail_the_run(tmp_path) -> None:
    root = tmp_path / "decision-replay-runtime"
    provider = FakeNarrativeProvider(chapter_count=1)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores = filesystem_stores(root)
    stores.runs.create(
        run_id="run-decision-replay",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as runtime:
        first = await runtime.start("run-decision-replay")
        decision = first.pending_decisions[0]
        command = {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "accept",
        }
        after_accept = await runtime.resume("run-decision-replay", command)

    async with open_sqlite_runtime(root, provider) as recovered:
        replayed = await recovered.resume("run-decision-replay", command)
        with pytest.raises(DecisionReplayConflict):
            await recovered.resume(
                "run-decision-replay",
                command | {"action": "cancel"},
            )

    assert after_accept.pending_decisions == replayed.pending_decisions
    assert replayed.active_stage_id == "characters"
    assert replayed.status == "awaiting_decision"
    assert provider.stage_calls == [
        "run-decision-replay:info:generate:1",
        "run-decision-replay:characters:generate:1",
    ]
    assert not any(event.type == "run.failed" for event in stores.events.read("run-decision-replay"))


@pytest.mark.asyncio
async def test_duplicate_chapter_decision_does_not_repeat_writeback_or_advance_again(tmp_path) -> None:
    root = tmp_path / "chapter-decision-replay-runtime"
    provider = FakeNarrativeProvider(chapter_count=2)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores = filesystem_stores(root)
    stores.runs.create(
        run_id="run-chapter-decision-replay",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as runtime:
        first = await _advance_to_first_chapter(runtime, "run-chapter-decision-replay")
        decision = first.pending_decisions[0]
        command = {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "accept",
        }
        after_accept = await runtime.resume("run-chapter-decision-replay", command)

    async with open_sqlite_runtime(root, provider) as recovered:
        replayed = await recovered.resume("run-chapter-decision-replay", command)

    assert after_accept.pending_decisions == replayed.pending_decisions
    assert replayed.pending_decisions[0]["chapter_id"] == "chapter-2"
    assert provider.evidence_calls == [
        "run-chapter-decision-replay:chapter-1:evidence:chapter-1-v1-accepted"
    ]
    assert len(stores.canon.facts("run-chapter-decision-replay")) == 1
    assert len(stores.wiki.list("run-chapter-decision-replay")) == 1


@pytest.mark.asyncio
async def test_parallel_review_pending_writes_resume_only_the_unfinished_lane(tmp_path) -> None:
    root = tmp_path / "parallel-review-recovery-runtime"
    provider = InterruptedParallelReviewProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores = filesystem_stores(root)
    stores.runs.create(
        run_id="run-parallel-review-recovery",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as runtime:
        projection = await runtime.start("run-parallel-review-recovery")
        while projection.pending_decisions:
            decision = projection.pending_decisions[0]
            command = {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            }
            if decision["node_id"] == "detail.human_decision":
                with pytest.raises(SimulatedProcessStop):
                    await runtime.resume("run-parallel-review-recovery", command)
                snapshot = await runtime.graph.aget_state(
                    {"configurable": {"thread_id": "run-parallel-review-recovery"}},
                    subgraphs=True,
                )
                chapter_snapshot = snapshot.tasks[0].state
                assert hasattr(chapter_snapshot, "tasks")
                pending_writes = repr([task.result for task in chapter_snapshot.tasks])
                assert ":continuity" in pending_writes
                assert ":prose" in pending_writes
                break
            projection = await runtime.resume("run-parallel-review-recovery", command)
        else:
            raise AssertionError("Detail decision was not reached")

    provider.interrupt_reviews = False
    execution = NarrativeExecutionService(root, lambda: provider)
    await execution.recover_incomplete()
    await execution.wait("run-parallel-review-recovery")
    projection = execution.stores.runs.read("run-parallel-review-recovery")

    assert projection.pending_decisions[0]["type"] == "chapter_author_decision"
    assert projection.pending_decisions[0]["reason"] == {
        "required_review_unavailable": [],
        "optional_review_unavailable": [],
        "blocking_findings": [],
        "reviewed_roles": ["character", "continuity", "prose"],
    }
    calls_by_role = [key.rsplit(":", 1)[-1] for key in provider.review_calls]
    assert calls_by_role.count("continuity") == 1
    assert calls_by_role.count("prose") == 1
    assert calls_by_role.count("character") == 2


@pytest.mark.asyncio
async def test_required_and_optional_review_failures_share_one_author_decision_without_fallback(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "review-unavailable-runtime")
    provider = UnavailableRequiredAndOptionalReviewProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-review-unavailable",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await _advance_to_first_chapter(runtime, "run-review-unavailable")

    assert projection.pending_decisions[0]["reason"] == {
        "required_review_unavailable": ["continuity"],
        "optional_review_unavailable": ["prose"],
        "blocking_findings": [],
        "reviewed_roles": ["character", "continuity", "prose"],
    }
    assert len(provider.review_calls) == 3
    assert not any("fallback" in event.node_id for event in stores.events.read("run-review-unavailable"))


@pytest.mark.asyncio
async def test_local_review_contract_failure_keeps_usage_and_closes_the_receipt(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "review-contract-runtime")
    provider = MismatchedReviewRoleProvider(chapter_count=1)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in (
            "info",
            "characters",
            "summary",
            "outline",
            "detail",
            "text",
            "cover",
        )
    }
    stores.runs.create(
        run_id="run-review-contract",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await _advance_to_first_chapter(runtime, "run-review-contract")

    receipt = stores.operations.read(
        "run-review-contract",
        "run-review-contract:chapter-1:review:chapter-1-v1:continuity",
    )
    assert receipt.status == "failed"
    assert receipt.usage["total_tokens"] == 10
    assert stores.operations.usage_summary("run-review-contract").pending_operations == 0
    assert projection.pending_decisions[0]["reason"]["required_review_unavailable"] == [
        "continuity"
    ]


@pytest.mark.asyncio
async def test_edited_chapter_is_saved_as_an_immutable_candidate_before_acceptance(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "edited-chapter-runtime")
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-edited-chapter",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await _advance_to_first_chapter(runtime, "run-edited-chapter")
    decision = projection.pending_decisions[0]
    source_version_id = str(decision["artifact_ref"])
    source = stores.chapters.read(
        "run-edited-chapter", "chapter-1", source_version_id
    )
    edited_payload = source.artifact.model_dump(mode="json")
    edited_payload["content"] = "人工编辑后的第一章正文。"

    edited = save_edited_chapter_candidate(
        stores.chapters,
        stores.events,
        run_id="run-edited-chapter",
        chapter_id="chapter-1",
        source_version_id=source_version_id,
        payload=edited_payload,
    )
    projection = await runtime.resume(
        "run-edited-chapter",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "accept",
            "candidate_chapter_version_id": edited.version_id,
        },
    )

    assert edited.version_id.startswith("chapter-1-edit-")
    assert edited.artifact.author_status == "edited"
    assert stores.chapters.read(
        "run-edited-chapter", "chapter-1", source_version_id
    ).artifact.content == "chapter-1 的冻结正文。"
    accepted = stores.chapters.read(
        "run-edited-chapter", "chapter-1", f"{edited.version_id}-accepted"
    )
    assert accepted.artifact.content == "人工编辑后的第一章正文。"
    assert accepted.artifact.author_status == "accepted"
    assert projection.pending_decisions[0]["chapter_id"] == "chapter-2"


@pytest.mark.asyncio
async def test_targeted_chapter_regeneration_carries_direction_and_repeats_review(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "chapter-regeneration-runtime")
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-regenerate-chapter",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    projection = await _advance_to_first_chapter(runtime, "run-regenerate-chapter")
    first_decision = projection.pending_decisions[0]

    projection = await runtime.resume(
        "run-regenerate-chapter",
        {
            "decision_id": first_decision["decision_id"],
            "domain_revision": first_decision["domain_revision"],
            "action": "regenerate",
            "direction": "收紧追逐节奏，并保留母带线索。",
        },
    )

    assert provider.chapter_calls == [
        "run-regenerate-chapter:chapter-1:generate:1",
        "run-regenerate-chapter:chapter-1:generate:2",
    ]
    revision = provider.chapter_requests[1].context["material"]["revision_request"]
    assert revision["direction"] == "收紧追逐节奏，并保留母带线索。"
    assert revision["source_chapter"]["version_id"] == "chapter-1-v1"
    assert revision["source_chapter"]["content"] == "chapter-1 的冻结正文。"
    assert projection.pending_decisions[0]["artifact_ref"] == "chapter-1-v2"
    assert len(provider.review_calls) == 6
    assert all(":chapter-1-v1:" in item for item in provider.review_calls[:3])
    assert all(":chapter-1-v2:" in item for item in provider.review_calls[3:])
    resolved = [
        event
        for event in stores.events.read("run-regenerate-chapter")
        if event.type == "decision.resolved" and event.chapter_id == "chapter-1"
    ]
    assert resolved[0].payload == {
        "decision_id": first_decision["decision_id"],
        "action": "regenerate",
        "artifact_ref": "chapter-1-v1",
        "direction": "收紧追逐节奏，并保留母带线索。",
    }


@pytest.mark.asyncio
async def test_stage_interrupt_accepts_an_immutable_edited_candidate(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-edited-candidate",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-edited-candidate")
    decision = projection.pending_decisions[0]
    edited_payload = _stage_payload("info") | {"title": "雾港回声"}
    edited = stores.artifacts.save_candidate(
        "run-edited-candidate",
        "info",
        edited_payload,
        source=f"user-decision:{decision['decision_id']}",
    )

    projection = await runtime.resume(
        "run-edited-candidate",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "accept",
            "candidate_artifact_id": edited.artifact_id,
        },
    )

    committed = stores.artifacts.latest("run-edited-candidate", "info")
    assert committed.payload["title"] == "雾港回声"
    assert committed.source == f"decision:{decision['decision_id']}"
    assert projection.active_stage_id == "characters"
    assert provider.stage_calls == [
        "run-edited-candidate:info:generate:1",
        "run-edited-candidate:characters:generate:1",
    ]


@pytest.mark.asyncio
async def test_branch_copies_checkpoint_lineage_and_resumes_under_a_new_run_identity(tmp_path) -> None:
    root = tmp_path / "branch-runtime"
    stores = filesystem_stores(root)
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-branch-source",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as runtime:
        source = await runtime.start("run-branch-source")
        branch = await NarrativeBranchService(runtime).create(
            source_run_id="run-branch-source",
            target_run_id="run-branch-target",
            checkpoint_id=source.checkpoint_id,
        )
        decision = branch.pending_decisions[0]
        resumed = await runtime.resume(
            "run-branch-target",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert branch.status == "awaiting_decision"
    assert decision["thread_id"] == "run-branch-target"
    assert decision["decision_id"].startswith("run-branch-target:info:")
    assert resumed.active_stage_id == "characters"
    assert stores.runs.read("run-branch-source").status == "awaiting_decision"
    assert stores.runs.definition("run-branch-target").branch_origin is not None
    assert stores.artifacts.latest("run-branch-target", "info").payload["title"] == "雾港母带"
    branch_events = stores.events.read("run-branch-target")
    assert [event.type for event in branch_events[:3]] == [
        "branch.created",
        "artifact.candidate_ready",
        "decision.required",
    ]
    assert branch_events[1].payload_ref == decision["artifact_ref"]
    assert branch_events[2].payload == decision
    assert all(event.run_id == event.thread_id == "run-branch-target" for event in branch_events)
    assert provider.stage_calls == [
        "run-branch-source:info:generate:1",
        "run-branch-target:characters:generate:1",
    ]


@pytest.mark.asyncio
async def test_branch_from_older_sqlite_checkpoint_excludes_later_source_history(tmp_path) -> None:
    root = tmp_path / "older-checkpoint-branch-runtime"
    stores = filesystem_stores(root)
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-older-source",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as runtime:
        info = await runtime.start("run-older-source")
        info_checkpoint_id = info.checkpoint_id
        source_at_characters = await runtime.resume(
            "run-older-source",
            {
                "decision_id": info.pending_decisions[0]["decision_id"],
                "domain_revision": info.pending_decisions[0]["domain_revision"],
                "action": "accept",
            },
        )
        assert source_at_characters.active_stage_id == "characters"
        assert stores.artifacts.latest(
            "run-older-source", "characters", status="candidate"
        ).status == "candidate"

        branch = await NarrativeBranchService(runtime).create(
            source_run_id="run-older-source",
            target_run_id="run-older-target",
            checkpoint_id=info_checkpoint_id,
        )
        with pytest.raises(FileNotFoundError):
            stores.artifacts.latest("run-older-target", "characters", status="candidate")

        decision = branch.pending_decisions[0]
        resumed = await runtime.resume(
            "run-older-target",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert branch.active_stage_id == "info"
    assert resumed.active_stage_id == "characters"
    assert provider.stage_calls == [
        "run-older-source:info:generate:1",
        "run-older-source:characters:generate:1",
        "run-older-target:characters:generate:1",
    ]


@pytest.mark.asyncio
async def test_branch_from_resolved_interrupt_excludes_appended_future_writes(tmp_path) -> None:
    root = tmp_path / "resolved-interrupt-branch-runtime"
    stores = filesystem_stores(root)
    provider = FakeNarrativeProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-resolved-source",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as runtime:
        info = await runtime.start("run-resolved-source")
        characters = await runtime.resume(
            "run-resolved-source",
            {
                "decision_id": info.pending_decisions[0]["decision_id"],
                "domain_revision": info.pending_decisions[0]["domain_revision"],
                "action": "accept",
            },
        )
        characters_checkpoint_id = characters.checkpoint_id
        summary = await runtime.resume(
            "run-resolved-source",
            {
                "decision_id": characters.pending_decisions[0]["decision_id"],
                "domain_revision": characters.pending_decisions[0]["domain_revision"],
                "action": "accept",
            },
        )
        assert summary.active_stage_id == "summary"

        branch = await NarrativeBranchService(runtime).create(
            source_run_id="run-resolved-source",
            target_run_id="run-resolved-target",
            checkpoint_id=characters_checkpoint_id,
        )
        branch_snapshot = await runtime.graph.aget_state(
            {"configurable": {"thread_id": "run-resolved-target"}},
            subgraphs=True,
        )
        branch_child = branch_snapshot.tasks[0].state
        with pytest.raises(FileNotFoundError):
            stores.artifacts.latest(
                "run-resolved-target", "characters", status="committed"
            )
        resumed = await runtime.resume(
            "run-resolved-target",
            {
                "decision_id": branch.pending_decisions[0]["decision_id"],
                "domain_revision": branch.pending_decisions[0]["domain_revision"],
                "action": "accept",
            },
        )

    assert branch.active_stage_id == "characters"
    assert branch.stage_status["characters"] == "awaiting_decision"
    assert branch.pending_decisions[0]["domain_revision"] == 1
    assert branch_child.values["domain_revision"] == 1
    assert "characters" not in branch_child.values["artifact_refs"]
    assert stores.artifacts.latest(
        "run-resolved-target", "characters", status="candidate"
    ).artifact_id == branch.pending_decisions[0]["artifact_ref"]
    assert resumed.active_stage_id == "summary"
    assert provider.stage_calls == [
        "run-resolved-source:info:generate:1",
        "run-resolved-source:characters:generate:1",
        "run-resolved-source:summary:generate:1",
        "run-resolved-target:summary:generate:1",
    ]


@pytest.mark.asyncio
async def test_branch_at_chapter_interrupt_keeps_stage_and_chapter_references_isolated(tmp_path) -> None:
    root = tmp_path / "chapter-branch-runtime"
    stores = filesystem_stores(root)
    provider = BlockingReviewProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-chapter-branch-source",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )

    async with open_sqlite_runtime(root, provider) as runtime:
        source = await runtime.start("run-chapter-branch-source")
        while source.pending_decisions[0]["type"] == "stage_artifact_decision":
            decision = source.pending_decisions[0]
            source = await runtime.resume(
                "run-chapter-branch-source",
                {
                    "decision_id": decision["decision_id"],
                    "domain_revision": decision["domain_revision"],
                    "action": "accept",
                },
            )
        assert source.pending_decisions[0]["type"] == "chapter_author_decision"

        branch = await NarrativeBranchService(runtime).create(
            source_run_id="run-chapter-branch-source",
            target_run_id="run-chapter-branch-target",
            checkpoint_id=source.checkpoint_id,
        )
        decision = branch.pending_decisions[0]
        resumed = await runtime.resume(
            "run-chapter-branch-target",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    assert stores.runs.read("run-chapter-branch-source").status == "awaiting_decision"
    assert stores.chapters.read(
        "run-chapter-branch-target", "chapter-1", "chapter-1-v1"
    ).artifact.author_status == "candidate"
    assert stores.artifacts.latest("run-chapter-branch-target", "detail").stage_id == "detail"
    assert provider.chapter_calls == [
        "run-chapter-branch-source:chapter-1:generate:1",
        "run-chapter-branch-target:chapter-2:generate:1",
    ]
    assert resumed.active_stage_id == "text"
    assert resumed.status == "awaiting_decision"


@pytest.mark.asyncio
async def test_stage_provider_failure_terminates_through_graph_failure_nodes(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "stage-failure-runtime")
    provider = FailingStageProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-stage-failure",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-stage-failure")
    events = stores.events.read("run-stage-failure")

    assert projection.status == "failed"
    assert projection.failure is not None
    assert projection.failure["node_id"] == "info.generate_candidate"
    assert projection.failure["evidence_ref"] == "run-stage-failure:info:generate:1"
    assert [(event.type, event.node_id) for event in events if event.type == "run.failed"] == [
        ("run.failed", "info.generate_candidate")
    ]
    assert [(event.type, event.node_id) for event in events if event.type == "node.failed"] == [
        ("node.failed", "info.generate_candidate")
    ]
    assert {
        event.payload_ref
        for event in events
        if event.type in {"node.failed", "run.failed"}
    } == {"run-stage-failure:info:generate:1"}


@pytest.mark.asyncio
async def test_chapter_provider_failure_terminates_through_graph_failure_nodes(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "chapter-failure-runtime")
    provider = FailingChapterProvider()
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-chapter-failure",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(2),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-chapter-failure")
    while projection.pending_decisions:
        decision = projection.pending_decisions[0]
        projection = await runtime.resume(
            "run-chapter-failure",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )
    events = stores.events.read("run-chapter-failure")

    assert projection.status == "failed"
    assert projection.failure is not None
    assert projection.failure["node_id"] == "text.generate_prose"
    assert projection.failure["evidence_ref"] == "run-chapter-failure:chapter-1:generate:1"
    assert [(event.type, event.node_id) for event in events if event.type == "run.failed"] == [
        ("run.failed", "text.generate_prose")
    ]
    assert [(event.type, event.node_id) for event in events if event.type == "node.failed"] == [
        ("node.failed", "text.generate_prose")
    ]
    assert {
        event.payload_ref
        for event in events
        if event.type in {"node.failed", "run.failed"}
    } == {"run-chapter-failure:chapter-1:generate:1"}


@pytest.mark.asyncio
async def test_local_chapter_target_failure_keeps_usage_and_closes_the_receipt(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "chapter-contract-runtime")
    provider = MismatchedChapterTargetProvider(chapter_count=1)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-chapter-contract",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-chapter-contract")
    while projection.pending_decisions:
        decision = projection.pending_decisions[0]
        projection = await runtime.resume(
            "run-chapter-contract",
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )

    operation_key = "run-chapter-contract:chapter-1:generate:1"
    receipt = stores.operations.read("run-chapter-contract", operation_key)
    assert projection.status == "failed"
    assert projection.failure is not None
    assert projection.failure["node_id"] == "text.generate_prose"
    assert receipt.status == "failed"
    assert receipt.usage["total_tokens"] == 10
    assert stores.operations.usage_summary("run-chapter-contract").pending_operations == 0
    assert stores.chapters.list("run-chapter-contract") == []


@pytest.mark.asyncio
async def test_evidence_failure_keeps_prose_but_never_creates_a_writeback(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "evidence-failure-runtime")
    provider = FailingEvidenceProvider(chapter_count=1)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="run-evidence-failure",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-evidence-failure")
    while projection.pending_decisions:
        decision = projection.pending_decisions[0]
        projection = await runtime.resume(
            "run-evidence-failure",
            _accept_command(stores, "run-evidence-failure", decision),
        )

    operation_key = "run-evidence-failure:chapter-1:evidence:chapter-1-v1-accepted"
    events = stores.events.read("run-evidence-failure")
    assert projection.status == "completed"
    assert stores.operations.read("run-evidence-failure", operation_key).status == "failed"
    assert [item.artifact.author_status for item in stores.chapters.list("run-evidence-failure")] == [
        "candidate",
        "accepted",
    ]
    assert stores.evidence.list("run-evidence-failure") == []
    assert stores.canon.facts("run-evidence-failure") == []
    assert stores.wiki.list("run-evidence-failure") == []
    assert not any(event.type == "evidence.proposed" for event in events)
    assert not any(event.type.startswith("writeback.") for event in events)


async def _advance_to_first_chapter(
    runtime: NarrativeRuntime,
    run_id: str,
):
    projection = await runtime.start(run_id)
    while (
        projection.pending_decisions
        and projection.pending_decisions[0]["type"] == "stage_artifact_decision"
    ):
        decision = projection.pending_decisions[0]
        projection = await runtime.resume(
            run_id,
            {
                "decision_id": decision["decision_id"],
                "domain_revision": decision["domain_revision"],
                "action": "accept",
            },
        )
    assert projection.pending_decisions[0]["type"] == "chapter_author_decision"
    assert projection.pending_decisions[0]["chapter_id"] == "chapter-1"
    return projection


def _accept_command(stores: Any, run_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    command = {
        "decision_id": decision["decision_id"],
        "domain_revision": decision["domain_revision"],
        "action": "accept",
    }
    if decision.get("node_id") != "cover.human_decision":
        return command
    source = stores.artifacts.read(run_id, str(decision["artifact_ref"]))
    assets = stores.cover_assets.list(run_id)
    attempt = max(item.generation_attempt for item in assets)
    active = [item for item in assets if item.generation_attempt == attempt]
    payload = {**source.payload, "selected_asset_id": active[0].asset_id}
    selected = stores.artifacts.save_candidate(
        run_id,
        "cover",
        payload,
        source=f"test-decision:{decision['decision_id']}",
        cover_asset_ids={item.asset_id for item in active},
    )
    command["candidate_artifact_id"] = selected.artifact_id
    return command


def _stage_payload(stage_id: str, *, chapter_count: int = 2) -> dict[str, Any]:
    if stage_id == "info":
        return {
            "title": "雾港母带",
            "premise": "声音档案员追查一卷会改写公共记忆的母带。",
            "story_promise": {"genre": "悬疑", "audience": "成人", "tone": "克制"},
            "world_rules": ["公开广播会覆盖个人记忆"],
            "thematic_question": "共同记忆是否值得以个人真相为代价？",
            "ending_promise": "真相会被公开。",
            "voice": {"viewpoint": "第三人称限知", "tense": "过去时", "texture": "听觉细节", "avoid": []},
            "cast_requirements": [{"function": "调查真相", "importance": "protagonist"}],
        }
    if stage_id == "characters":
        return {
            "characters": [
                {
                    "id": "char-lin",
                    "name": "林默",
                    "tier": "protagonist",
                    "narrative_function": "承担调查",
                    "external_goal": "找到母带",
                    "inner_need": "承认恐惧",
                    "arc": {"start": "拒绝合作", "turning_point": "共享证据", "end": "接受共同记忆"},
                    "first_appearance_window": "chapter:1",
                    "hard_boundaries": [],
                }
            ],
            "relationships": [],
            "npc_slots": [],
        }
    if stage_id == "summary":
        return {
            "beats": [{"id": "beat-1", "phase": "opening", "event": "发现母带", "consequence": "开始调查"}],
            "climax": "公开母带",
            "resolution": "港区恢复个人记忆",
            "character_outcomes": [{"character_id": "char-lin", "outcome": "接受共同记忆"}],
        }
    if stage_id == "outline":
        return {
            "volumes": [
                {
                    "id": "volume-1",
                    "chapter_window": f"chapter:1-{chapter_count}",
                    "objective": "找到并公开母带",
                    "turns": [{"id": "turn-1", "event": "找到副本", "consequence": "追捕升级"}],
                    "ending_state": "真相公开",
                    "character_windows": [{"character_id": "char-lin", "entry_state": "独行", "exit_state": "合作", "turn_id": "turn-1"}],
                    "thread_windows": [],
                }
            ]
        }
    if stage_id == "detail":
        return {
            "chapters": [
                {
                    "id": f"chapter-{number}",
                    "number": number,
                    "purpose": "推进母带调查",
                    "pov_character_id": "char-lin",
                    "scenes": [{"id": f"scene-{number}", "location": "雾港", "goal": "寻找线索", "obstacle": "广播干扰", "turn": "发现副本", "outcome": "获得证据"}],
                    "obligations": [],
                    "handoff": {"unresolved_actions": [], "emotional_carryover": [], "next_pressure": "追捕升级"},
                }
                for number in range(1, chapter_count + 1)
            ]
        }
    if stage_id == "cover":
        return {
            "concept": "雾中的港区与磁带",
            "image_prompt": "一座被广播塔切开的潮湿港区，前景是一卷旧磁带",
            "palette": ["冷灰", "警示红"],
            "negative_constraints": ["人物正脸", "文字"],
        }
    raise AssertionError(f"Provider must not generate stage {stage_id}")


def _png(width: int, height: int, color: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    row = b"\x00" + bytes((color % 255, 40, 80)) * width
    pixels = row * height

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        signature
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )

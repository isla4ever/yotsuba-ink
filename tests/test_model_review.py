from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from novel_workflow.orchestration.model_review import chapter_model_reviewer
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.quality.model_review import (
    primary_revision_instruction,
    run_model_review,
    upsert_tension_entry,
)
from novel_workflow.workflows.schemas import NovelRunState, StoryBibleState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import FakeImageProvider, FakeTextProvider, fake_model_review_output
from tests.workflow_runner_harness import (
    CapturingPlanningProvider,
    build_runner,
    chapter_text_fixture,
    detail_outline_fixture,
    planning_workflow,
    run_and_approve,
)

CHAPTER_CONTENT = "第1章 正文。林澈承接上一章的伏笔，沿着旧港堤岸追查雾钟的来历，脚步在浓雾里逐渐坚定。" * 3


class CountingReviewProvider(FakeTextProvider):
    def __init__(self) -> None:
        self.review_calls = 0

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        if task_name == "model_review":
            self.review_calls += 1
        return await super().generate_structured(prompt, task_name=task_name, context=context, schema=schema)


class FailingReviewProvider(FakeTextProvider):
    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        if task_name == "model_review":
            raise RuntimeError("review provider down")
        return await super().generate_structured(prompt, task_name=task_name, context=context, schema=schema)


def _registry(provider: FakeTextProvider) -> ProviderRegistry:
    return ProviderRegistry(
        text_provider=provider,
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": provider},
        image_providers={"openai-compatible-image": FakeImageProvider()},
    )


def _text_node() -> Any:
    node = deepcopy(next(item for item in default_workflow().nodes if item.id == "text"))
    node.provider_profile_id = "openai-compatible"
    node.fallback_targets = []
    return node


def _state(mode: str = "balanced") -> NovelRunState:
    return NovelRunState(
        run_id="model-review-test",
        project_id="p-review",
        workflow_id="default-novel-workflow",
        inputs={"quality_mode": mode},
    )


class _StubRunStore:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def update_state(self, run_id: str, state: Any) -> None:
        del run_id, state

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        del run_id
        self.events.append(event)


@pytest.mark.asyncio
async def test_run_model_review_success_parses_report_and_bills_model_review_scope() -> None:
    node = _text_node()
    state = _state()
    report = await run_model_review(
        _registry(FakeTextProvider()),
        node,
        state,
        chapter="第1章",
        content=CHAPTER_CONTENT,
        run_store=None,
        chapter_version=0,
    )
    assert report.status == "completed"
    assert report.overall_score == 7.6
    assert [item.dimension for item in report.dimensions] == ["连续性", "语言质感"]
    assert report.tension.score == 6.5
    assert report.tension.basis
    assert report.voice.drift is False
    assert report.content_signature
    scope = state.budget_state["scopes"]["text:第1章"]
    assert scope["attempts"]["model_review"] == 1
    assert scope["limits"]["model_review"] == 2  # balanced: initial review + one post-regeneration re-review
    operations = [item for item in scope["operations"] if item["kind"] == "model_review"]
    assert len(operations) == 1
    assert operations[0]["status"] == "completed"
    assert operations[0]["consumed_tokens"] > 0


@pytest.mark.asyncio
async def test_run_model_review_failure_degrades_to_unavailable_without_fake_scores() -> None:
    node = _text_node()
    state = _state()
    report = await run_model_review(
        _registry(FailingReviewProvider()),
        node,
        state,
        chapter="第1章",
        content=CHAPTER_CONTENT,
        run_store=None,
    )
    assert report.status == "unavailable"
    assert "review provider down" in report.error
    assert report.dimensions == []
    assert report.overall_score == 0.0


def test_upsert_tension_entry_is_idempotent_per_chapter() -> None:
    bible = StoryBibleState()
    upsert_tension_entry(bible, chapter="第1章", score=4.0, basis="铺垫")
    upsert_tension_entry(bible, chapter="第2章", score=7.0, basis="冲突升级")
    upsert_tension_entry(bible, chapter="第1章", score=5.5, basis="重评")
    assert len(bible.tension_track) == 2
    first = next(item for item in bible.tension_track if item["chapter"] == "第1章")
    assert first == {"chapter": "第1章", "score": 5.5, "basis": "重评", "source": "model_review"}


def test_primary_revision_instruction_prefers_lowest_scored_dimension() -> None:
    review = {
        "status": "completed",
        "dimensions": [
            {"dimension": "连续性", "score": 9.0, "revision_instruction": "高分指令不应被选中"},
            {"dimension": "语言质感", "score": 4.0, "revision_instruction": ""},
            {"dimension": "模板味", "score": 5.0, "revision_instruction": "压缩模板化比喻"},
        ],
    }
    assert primary_revision_instruction(review) == "压缩模板化比喻"
    assert primary_revision_instruction({"status": "unavailable", "dimensions": []}) == ""
    assert primary_revision_instruction(None) == ""


@pytest.mark.asyncio
async def test_reviewer_closure_reuses_cached_review_for_same_chapter_version() -> None:
    provider = CountingReviewProvider()
    node = _text_node()
    state = _state()
    runner = SimpleNamespace(providers=_registry(provider), run_store=_StubRunStore())
    workflow = SimpleNamespace(quality_mode="balanced")
    reviewer = chapter_model_reviewer(runner, node, state, workflow, "run-cache")
    first, first_events = await reviewer("第1章", CHAPTER_CONTENT)
    second, second_events = await reviewer("第1章", CHAPTER_CONTENT)
    assert provider.review_calls == 1
    assert first is not None and second is not None
    assert second["content_signature"] == first["content_signature"]
    assert any(event["type"] == "chapter_tension_scored" for event in first_events)
    assert second_events == []
    assert state.budget_state["scopes"]["text:第1章"]["attempts"]["model_review"] == 1


@pytest.mark.asyncio
async def test_reviewer_closure_recalls_after_chapter_content_changes() -> None:
    provider = CountingReviewProvider()
    node = _text_node()
    state = _state("deep")
    runner = SimpleNamespace(providers=_registry(provider), run_store=_StubRunStore())
    workflow = SimpleNamespace(quality_mode="deep")
    reviewer = chapter_model_reviewer(runner, node, state, workflow, "run-recall")
    await reviewer("第1章", CHAPTER_CONTENT)
    await reviewer("第1章", CHAPTER_CONTENT + "\n重生成后的新结尾。")
    assert provider.review_calls == 2


def test_reviewer_closure_disabled_for_fast_mode_and_non_chapter_nodes() -> None:
    runner = SimpleNamespace(providers=_registry(FakeTextProvider()), run_store=_StubRunStore())
    node = _text_node()
    assert chapter_model_reviewer(runner, node, _state("fast"), SimpleNamespace(quality_mode="fast"), "r") is None
    summary_node = deepcopy(next(item for item in default_workflow().nodes if item.id == "summary"))
    assert chapter_model_reviewer(runner, summary_node, _state(), SimpleNamespace(quality_mode="balanced"), "r") is None


class BalancedRevisionProvider(CapturingPlanningProvider):
    """Chapter text without handoff signals -> L1 warning -> model review drives the directive."""

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        if task_name == "chapter_text":
            return {
                "chapter_title": "测试章节",
                "content": (
                    "陌生山城的清晨，无关旅人从旅馆醒来，开始寻找一封没有来源的旧信。"
                    "这段伏笔与旧港人物、物证和前章结果都没有关联，像另一部故事突然开场。"
                ),
                "summary": "测试正文缺少承接信号。",
                "wiki_writebacks": [],
                "character_shift": "人物状态推进。",
                "foreshadow_updates": [],
            }
        if task_name == "detail_outline":
            return detail_outline_fixture()
        return await super().generate_structured(prompt, task_name=task_name, context=context, schema=schema)


@pytest.mark.asyncio
async def test_balanced_run_uses_model_review_instruction_and_tracks_tension(tmp_path) -> None:
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    provider = BalancedRevisionProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "balanced-model-review"
    inputs = {
        "project_id": "p-balanced-review",
        "title": "平衡评审测试",
        "quality_mode": "balanced",
        "stage_configs": {"detail": {"chapter_count": 3}, "text": {"chapter_count": 3}},
    }
    store.create(run_id, workflow, inputs)
    events = await run_and_approve(runner, workflow, store, run_id, inputs)

    assert events[-1]["type"] == "run_completed"
    review_calls = [call for call in provider.calls if call["task_name"] == "model_review"]
    assert len(review_calls) == 3
    directives = [event for event in events if event["type"] == "revision_directive_created"]
    assert directives
    expected_instruction = fake_model_review_output()["dimensions"][1]["revision_instruction"]
    assert all(event["directive"]["instruction"] == expected_instruction for event in directives)

    tension_events = [event for event in events if event["type"] == "chapter_tension_scored"]
    assert [event["chapter"] for event in tension_events] == ["第1章", "第2章", "第3章"]
    assert all(event["source"] == "model_review" and event["basis"] for event in tension_events)

    state = store.read(run_id)["state"]
    track = state["story_bible"]["tension_track"]
    assert [item["chapter"] for item in track] == ["第1章", "第2章", "第3章"]
    assert all(item["score"] == 6.5 and item["source"] == "model_review" for item in track)
    assert any(event["type"] == "model_review_completed" for event in events)
    # balanced mode keeps the review in run state, not on the chapter artifact
    assert all("model_review" not in chapter for chapter in state["artifacts"]["chapters"]["chapters"])


@pytest.mark.asyncio
async def test_deep_run_attaches_model_review_report_to_chapter_artifact(tmp_path) -> None:
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "deep"
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "deep-model-review"
    inputs = {"project_id": "p-deep-review", "title": "精细评审测试", "quality_mode": "deep"}
    store.create(run_id, workflow, inputs)
    events = await run_and_approve(runner, workflow, store, run_id, inputs)

    assert any(call["task_name"] == "model_review" for call in provider.calls)
    state = store.read(run_id)["state"]
    chapters = state["artifacts"]["chapters"]["chapters"]
    assert chapters
    for chapter in chapters:
        assert chapter["model_review"]["status"] == "completed"
        assert chapter["model_review"]["dimensions"]
        assert chapter["model_review"]["tension"]["score"] == 6.5
    assert state["story_bible"]["tension_track"]
    assert any(event["type"] == "chapter_tension_scored" for event in events)


@pytest.mark.asyncio
async def test_fast_run_never_calls_model_review(tmp_path) -> None:
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "fast"
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "fast-no-review"
    inputs = {"project_id": "p-fast-review", "title": "极速零评审", "quality_mode": "fast"}
    store.create(run_id, workflow, inputs)
    events = await run_and_approve(runner, workflow, store, run_id, inputs)

    assert events[-1]["type"] == "run_completed"
    assert not [call for call in provider.calls if call["task_name"] == "model_review"]
    assert not [event for event in events if event["type"] in {"chapter_tension_scored", "model_review_completed"}]
    state = store.read(run_id)["state"]
    assert state["story_bible"]["tension_track"] == []
    assert state["model_review_state"] == {}


class FailingReviewPlanningProvider(CapturingPlanningProvider):
    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        if task_name == "model_review":
            raise RuntimeError("模型评审接口超时")
        return await super().generate_structured(prompt, task_name=task_name, context=context, schema=schema)


@pytest.mark.asyncio
async def test_review_failure_degrades_without_blocking_chapter_commit(tmp_path) -> None:
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    provider = FailingReviewPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "review-degrade"
    inputs = {"project_id": "p-degrade", "title": "评审降级测试", "quality_mode": "balanced"}
    store.create(run_id, workflow, inputs)
    events = await run_and_approve(runner, workflow, store, run_id, inputs)

    assert events[-1]["type"] == "run_completed"
    unavailable = [event for event in events if event["type"] == "model_review_unavailable"]
    assert unavailable
    assert all(event["reason"] for event in unavailable)
    state = store.read(run_id)["state"]
    chapters = state["artifacts"]["chapters"]["chapters"]
    assert chapters and all(item["status"] == "completed" for item in chapters)
    assert state["story_bible"]["tension_track"] == []
    entries = state["model_review_state"]
    assert entries and all(entry["status"] == "unavailable" for entry in entries.values())
    assert all(entry["report"]["overall_score"] == 0.0 for entry in entries.values())

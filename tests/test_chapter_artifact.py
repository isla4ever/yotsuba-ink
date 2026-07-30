from __future__ import annotations

import asyncio
import copy

import pytest

from novel_workflow.orchestration.chapter_artifact import (
    complete_chapter_commit,
    drafting_chapter,
    empty_chapter_artifact,
    prepare_chapter_commit,
    upsert_chapter,
)
from novel_workflow.orchestration.chapter_final_artifact import commit_chapter_artifact_writebacks
from novel_workflow.orchestration.chapters import run_chapter_text_node
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.providers.base import TextProvider
from novel_workflow.workflows.schemas import ChapterContextPacket, ChapterDraft, ChapterProgressItem, NovelRunState
from tests.workflow_runner_harness import CapturingPlanningProvider, build_runner, planning_workflow


class CapturingChapterProvider(TextProvider):
    name = "capturing-chapter-resume"

    def __init__(self) -> None:
        self.text_calls = 0

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, object]) -> str:
        raise AssertionError("runner should request structured output")

    async def generate_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, object],
        schema: dict[str, object] | None = None,
    ) -> object:
        assert task_name == "chapter_text"
        self.text_calls += 1
        return {
            "chapter_title": f"第{self.text_calls}章 恢复后的正文",
            "content": "恢复后只生成未提交章节。" * 50,
            "summary": "恢复后完成剩余章节。",
            "wiki_writebacks": [],
            "character_shift": "人物继续推进调查。",
            "foreshadow_updates": [],
        }


def test_chapter_artifact_is_self_contained_and_signature_is_stable():
    packet = _context_packet(1)
    draft = drafting_chapter(
        {
            "chapter_title": "第1章 雾中母带",
            "summary": "林澈发现母带异常。",
            "wiki_writebacks": [{"target": "母带", "fact": "包含异常声纹"}],
            "character_shift": "林澈决定保留证据。",
            "foreshadow_updates": [{"name": "父亲签章", "status": "投放"}],
        },
        index=1,
        content="第1章 正文\n\n林澈保留了母带中的异常声纹。",
        context_packet=packet,
    )
    first = prepare_chapter_commit(draft, content=draft["content"], quality_report={"score": 0.9}, revision_history=[])
    second = prepare_chapter_commit(draft, content=draft["content"], quality_report={"score": 0.9}, revision_history=[])
    artifact = upsert_chapter(empty_chapter_artifact(1), complete_chapter_commit(first))

    assert first["commit_signature"] == second["commit_signature"]
    assert artifact["status"] == "completed"
    assert artifact["context_packets"] == [packet.model_dump()]
    assert artifact["chapter_summaries"] == [{"chapter": "第1章", "summary": "林澈发现母带异常。"}]
    assert artifact["wiki_writebacks"] == [{"target": "母带", "fact": "包含异常声纹"}]

    artifact["chapters"][0]["summary_dirty"] = True
    validation = validate_stage_artifact("chapter_text", artifact)
    assert validation.valid is False
    assert any("summary_dirty" in error for error in validation.errors)


@pytest.mark.asyncio
async def test_drafting_chapter_resumes_without_provider_call(tmp_path):
    provider = CapturingChapterProvider()
    store, runner = build_runner(tmp_path, provider)
    workflow = planning_workflow(["text"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "deep"
    node = workflow.nodes[0]
    run_id = "resume-drafting-chapter"
    inputs = _inputs(1)
    store.create(run_id, workflow, inputs)
    state = NovelRunState(run_id=run_id, project_id="p-resume-draft", workflow_id=workflow.id, inputs=inputs)
    draft = drafting_chapter(
        {
            "chapter_title": "第1章 已保存候选",
            "summary": "候选已经生成，只需继续质量检查。",
            "wiki_writebacks": [],
            "character_shift": "",
            "foreshadow_updates": [],
        },
        index=1,
        content="第1章 正文\n\n" + "已保存的正文内容用于断线恢复。" * 40,
        context_packet=_context_packet(1),
    )
    state.artifacts["chapters"] = upsert_chapter(empty_chapter_artifact(1), draft)
    store.update_state(run_id, state)

    events = [event async for event in run_chapter_text_node(runner, node, state, workflow, run_id, 0, 1)]

    assert provider.text_calls == 0
    assert not any(event["type"] == "chapter_started" for event in events)
    assert state.artifacts["chapters"]["chapters"][0]["status"] == "completed"
    assert state.artifacts["chapters"]["chapters"][0]["commit_signature"]
    assert state.wiki_refs == []


def test_confirmed_chapter_artifact_replaces_summary_and_writes_memory_once(tmp_path):
    provider = CapturingChapterProvider()
    store, runner = build_runner(tmp_path, provider)
    workflow = planning_workflow(["text"], provider_profile_id="openai-compatible")
    node = workflow.nodes[0]
    run_id = "confirmed-chapter-writeback"
    inputs = _inputs(1)
    store.create(run_id, workflow, inputs)
    state = NovelRunState(run_id=run_id, project_id="p-confirmed-chapter", workflow_id=workflow.id, inputs=inputs)
    state.chapter_progress = [ChapterProgressItem(volume="第一卷", chapter="第1章", status="completed", node_id="text")]
    draft = drafting_chapter(
        {
            "chapter_title": "第1章 人工定稿",
            "summary": "人工确认后的章节摘要。",
            "wiki_writebacks": [{"target": "父亲签章", "fact": "仍是未回收线索"}],
            "character_shift": "苏迟决定继续核验母带。",
            "foreshadow_updates": [{"name": "父亲签章", "status": "推进"}],
        },
        index=1,
        content="第1章 人工定稿\n\n" + "苏迟重新核对母带并保留父亲签章线索。" * 30,
        context_packet=_context_packet(1),
    )
    artifact = upsert_chapter(
        empty_chapter_artifact(1),
        complete_chapter_commit(
            prepare_chapter_commit(draft, content=draft["content"], quality_report={"score": 0.93}, revision_history=[]),
        ),
    )
    store.update_state(run_id, state)

    first_events = commit_chapter_artifact_writebacks(runner, node, artifact, state, run_id)
    second_events = commit_chapter_artifact_writebacks(runner, node, artifact, state, run_id)

    assert [event["type"] for event in first_events] == [
        "memory_writeback_completed", "story_bible_updated", "character_graph_updated", "worldbuilding_updated", "canon_facts_committed"
    ]
    assert second_events == []
    assert state.story_bible.chapter_summaries == [
        {"chapter": "第1章", "summary": "人工确认后的章节摘要。", "context_kind": "first"}
    ]
    assert state.artifacts["chapters_text"] == draft["content"]
    assert len(state.wiki_refs) == 2
    assert state.stage_display_artifacts["text_confirmed_writeback"]["status"] == "committed"


@pytest.mark.asyncio
async def test_deep_chapter_approval_commits_edited_text_and_summary(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "deep"
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "deep-chapter-edited"
    edited_content = "第1章 人工定稿\n\n苏迟确认父亲签章仍是未回收线索，并决定继续调查。"
    edited_summary = "苏迟在人工定稿中确认父亲签章线索。"
    inputs = {
        "project_id": "p-deep-chapter-edited",
        "title": "正文人工定稿门禁",
        "quality_mode": "deep",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 1},
            "detail": {"chapter_count": 1},
            "text": {"chapter_count": 1, "chapter_words": 900},
        },
    }
    store.create(run_id, workflow, inputs)

    async def approve_stages() -> None:
        approved: set[str] = set()
        for _ in range(500):
            await asyncio.sleep(0.02)
            stored = store.read(run_id)
            approval = stored.get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id not in approved:
                artifact = copy.deepcopy(approval["artifact"])
                if node_id == "text":
                    artifact["chapters"][0].update(
                        {
                            "content": edited_content,
                            "words": len(edited_content),
                            "summary": edited_summary,
                            "summary_dirty": False,
                            "commit_signature": "",
                            "version": artifact["chapters"][0].get("version", 1) + 1,
                        }
                    )
                    artifact["chapter_summaries"] = [{"chapter": "第1章", "summary": edited_summary}]
                store.approve_artifact(run_id, node_id=node_id, output_key=str(approval["output_key"]), artifact=artifact)
                approved.add(node_id)
            if (stored.get("state") or {}).get("runtime_phase") in {"completed", "failed"}:
                return

    approver = asyncio.create_task(approve_stages())
    events: list[dict] = []
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            events.append(event)
    finally:
        await approver

    state = store.read(run_id)["state"]
    text_memory_events = [
        event for event in events
        if event["type"] == "memory_writeback_completed" and event.get("node_id") == "text"
    ]
    assert state["artifacts"]["chapters"]["chapters"][0]["content"] == edited_content
    assert state["artifacts"]["chapters_text"] == edited_content
    assert state["story_bible"]["chapter_summaries"][0]["summary"] == edited_summary
    assert len(text_memory_events) == 1


@pytest.mark.asyncio
async def test_persisted_candidate_resumes_without_regenerating_variant(tmp_path):
    provider = CapturingChapterProvider()
    store, runner = build_runner(tmp_path, provider)
    workflow = planning_workflow(["text"], provider_profile_id="openai-compatible")
    node = workflow.nodes[0]
    run_id = "resume-persisted-candidate"
    inputs = _inputs(1)
    store.create(run_id, workflow, inputs)
    state = NovelRunState(run_id=run_id, project_id="p-resume-candidate", workflow_id=workflow.id, inputs=inputs)
    result = {
        "chapter_title": "第1章 已落盘候选",
        "content": "候选在中断前已经生成。" * 50,
        "summary": "候选恢复后继续质量检查。",
        "wiki_writebacks": [],
        "character_shift": "人物继续推进调查。",
        "foreshadow_updates": [],
    }
    state.chapter_drafts = [
        ChapterDraft(
            chapter="第1章",
            content="第1章 正文\n\n" + str(result["content"]),
            status="completed",
            words=len(str(result["content"])),
            variant_id="text-c1-v1",
            score=0.9,
            artifact=result,
        )
    ]
    store.update_state(run_id, state)

    events = [event async for event in run_chapter_text_node(runner, node, state, workflow, run_id, 0, 1)]

    assert provider.text_calls == 0
    assert any(event["type"] == "chapter_completed" for event in events)
    assert state.artifacts["chapters"]["chapters"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_committing_and_completed_chapters_are_idempotent_on_resume(tmp_path):
    provider = CapturingChapterProvider()
    provider.text_calls = 1
    store, runner = build_runner(tmp_path, provider)
    workflow = planning_workflow(["text"], provider_profile_id="openai-compatible")
    node = workflow.nodes[0]
    run_id = "resume-committing-chapter"
    inputs = _inputs(2)
    store.create(run_id, workflow, inputs)
    state = NovelRunState(run_id=run_id, project_id="p-resume-commit", workflow_id=workflow.id, inputs=inputs)
    state.story_bible.chapter_summaries = [{"chapter": "第1章", "summary": "第一章已有摘要", "context_kind": "first"}]
    draft = drafting_chapter(
        {
            "chapter_title": "第1章 已完成生成",
            "summary": "第一章已有摘要",
            "wiki_writebacks": [{"target": "母带", "fact": "已经写入一次"}],
            "character_shift": "林澈开始追查。",
            "foreshadow_updates": [{"name": "父亲签章", "status": "投放"}],
        },
        index=1,
        content="第1章 正文\n\n" + "第一章内容已经准备提交。" * 40,
        context_packet=_context_packet(1),
    )
    committing = prepare_chapter_commit(draft, content=draft["content"], quality_report={"score": 0.91}, revision_history=[])
    state.artifacts["chapters"] = upsert_chapter(empty_chapter_artifact(2), committing)
    store.update_state(run_id, state)

    first_events = [event async for event in run_chapter_text_node(runner, node, state, workflow, run_id, 0, 1)]
    first_snapshot = (
        provider.text_calls,
        len(state.wiki_refs),
        len(state.story_bible.chapter_summaries),
        len(state.stage_usage_summaries),
    )
    second_events = [event async for event in run_chapter_text_node(runner, node, state, workflow, run_id, 0, 1)]
    second_snapshot = (
        provider.text_calls,
        len(state.wiki_refs),
        len(state.story_bible.chapter_summaries),
        len(state.stage_usage_summaries),
    )

    assert provider.text_calls == 2
    assert sum(event["type"] == "chapter_started" for event in first_events) == 1
    assert not any(event["type"] == "chapter_started" for event in second_events)
    assert first_snapshot == second_snapshot
    assert len(state.artifacts["chapters"]["chapters"]) == 2
    assert all(item["status"] == "completed" for item in state.artifacts["chapters"]["chapters"])
    assert len({item["chapter"] for item in state.story_bible.chapter_summaries}) == 2


def _context_packet(index: int) -> ChapterContextPacket:
    return ChapterContextPacket(
        chapter=f"第{index}章",
        chapter_index=index,
        chapter_kind="first" if index == 1 else "normal",
        chapter_outline=f"第{index}章目标与冲突",
        previous_chapter_summary="" if index == 1 else "上一章摘要",
        world_rules=["世界观硬设定不得被推翻"],
    )


def _inputs(chapters: int) -> dict[str, object]:
    return {
        "project_id": "p-resume",
        "title": "正文恢复门禁",
        "quality_mode": "balanced",
        "stage_configs": {"text": {"chapter_count": chapters, "chapter_words": 900}},
    }

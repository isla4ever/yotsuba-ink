from __future__ import annotations

import pytest

from novel_workflow.providers.base import TextProvider
from tests.workflow_runner_harness import (
    CapturingPlanningProvider,
    build_runner,
    detail_outline_fixture,
    outline_fixture,
    planning_workflow,
    run_and_approve,
    story_brief_fixture,
    summary_fixture,
)


@pytest.mark.asyncio
async def test_planning_chain_generates_one_text_chapter_with_writebacks(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    workflow.nodes[-1].variant_policy.enabled = False
    workflow.stage_configs["text"].variant_policy = workflow.nodes[-1].variant_policy
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "planning-text-one-chapter"
    inputs = {
        "project_id": "p-text-one",
        "title": "正文单章真实门禁",
        "quality_mode": "balanced",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 1, "conflict_density": "中高"},
            "detail": {"chapter_count": 1, "must_include": ["目标", "冲突", "伏笔", "章末钩子"]},
            "text": {"chapter_count": 1, "chapter_words": 900, "batch_generate": False},
        },
    }
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[-1] == "run_completed"
    assert [event["node_id"] for event in events if event["type"] == "node_started"] == [
        "info",
        "summary",
        "outline",
        "detail",
        "text",
    ]
    assert "cover" not in {str(event.get("node_id") or "") for event in events}
    assert "export" not in {str(event.get("node_id") or "") for event in events}
    assert "chapter_context_built" in event_types
    assert "chapter_started" in event_types
    assert "variant_generated" not in event_types
    assert "chapter_delta" in event_types
    assert "chapter_completed" in event_types
    assert "wiki_state_updated" in event_types
    assert "story_bible_updated" in event_types
    chapter_steps = [
        event for event in events
        if event["type"] == "chapter_pipeline_step_completed"
        and event.get("chapter") == "第1章"
    ]
    assert [event["step"] for event in chapter_steps] == list(range(1, 11))
    assert chapter_steps[-1]["step_key"] == "chapter_settled"
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "text" for event in events)

    assert [call["task_name"] for call in provider.calls] == [
        "info_recommend",
        "summary",
        "outline",
        "detail_outline",
        "chapter_text",
        "model_review",
    ]
    text_call = next(call for call in provider.calls if call["task_name"] == "chapter_text")
    assert text_call["schema"] is None
    assert "当前调用只生成一个章节" in text_call["prompt"]
    assert "chapter_title" in text_call["prompt"]
    assert "章节上下文包" in text_call["prompt"]

    deltas = [event["delta"] for event in events if event["type"] == "chapter_delta"]
    assert len(deltas) >= 2
    assert all(delta.strip() for delta in deltas)

    state = store.read(run_id)["state"]
    chapters_artifact = state["artifacts"]["chapters"]
    generated = chapters_artifact["chapters"]
    assert state["runtime_phase"] == "completed"
    assert state["completed_stage_ids"] == ["info", "summary", "outline", "detail", "text"]
    assert state["progress"]["text"] == {"status": "completed", "output_key": "chapters"}
    assert len(generated) == 1
    assert generated[0]["title"] == "第1章"
    assert "7A-13 母带" in generated[0]["content"]
    assert generated[0]["words"] >= 350
    assert state["artifacts"]["chapters_text"] == generated[0]["content"]
    assert len(state["chapter_context_packets"]) == 1
    assert state["chapter_context_packets"][0]["chapter"] == "第1章"
    assert state["chapter_progress"][0]["status"] == "completed"
    assert state["chapter_progress"][0]["words"] == generated[0]["words"]
    assert state["story_bible"]["updated_by"] == "text:第1章"
    assert len(state["story_bible"]["chapter_summaries"]) == 1
    assert state["continuity_state"]["chapter_summaries"] == 1
    assert len(state["wiki_refs"]) >= 5
    assert state["wiki_state"]["documents"] == len(state["wiki_refs"])
    assert not state["errors"]


class CapturingMultiChapterProvider(TextProvider):
    name = "capturing-multi-chapter"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
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
        self.calls.append({"prompt": prompt, "task_name": task_name, "context": context, "schema": schema})
        if task_name == "info_recommend":
            return story_brief_fixture(str(context.get("title") or "雾港多章"))
        if task_name == "summary":
            return summary_fixture()
        if task_name == "outline":
            return outline_fixture()
        if task_name == "detail_outline":
            return detail_outline_fixture()
        if task_name == "chapter_text":
            self.text_calls += 1
            return _multi_chapter_fixture(self.text_calls)
        raise AssertionError(f"unexpected task: {task_name}")


@pytest.mark.asyncio
async def test_planning_chain_generates_two_text_chapters_with_previous_context(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    workflow.nodes[-1].variant_policy.enabled = False
    workflow.stage_configs["text"].variant_policy = workflow.nodes[-1].variant_policy
    provider = CapturingMultiChapterProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "planning-text-two-chapters"
    inputs = {
        "project_id": "p-text-two",
        "title": "正文多章连续性门禁",
        "quality_mode": "balanced",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 2, "conflict_density": "中高"},
            "detail": {"chapter_count": 2, "must_include": ["目标", "冲突", "伏笔", "章末钩子"]},
            "text": {"chapter_count": 2, "chapter_words": 900, "batch_generate": True},
        },
    }
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[-1] == "run_completed"
    assert event_types.count("chapter_context_built") == 2
    assert event_types.count("chapter_started") == 2
    assert event_types.count("chapter_completed") == 2
    assert event_types.count("stage_usage_finalized") == 2
    assert event_types.count("wiki_state_updated") == 2
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "text" for event in events)

    text_calls = [call for call in provider.calls if call["task_name"] == "chapter_text"]
    assert len(text_calls) == 2
    assert "上一章摘要: 暂无" in str(text_calls[0]["prompt"])
    assert "上一章摘要: 暂无" not in str(text_calls[1]["prompt"])
    assert "章节上下文包" in str(text_calls[1]["prompt"])

    state = store.read(run_id)["state"]
    chapters_artifact = state["artifacts"]["chapters"]
    generated = chapters_artifact["chapters"]
    assert state["runtime_phase"] == "completed"
    assert state["completed_stage_ids"] == ["info", "summary", "outline", "detail", "text"]
    assert state["progress"]["text"] == {"status": "completed", "output_key": "chapters"}
    assert len(generated) == 2
    assert generated[0]["title"] == "第1章"
    assert generated[1]["title"] == "第2章"
    assert "7A-13 母带" in generated[0]["content"]
    assert "承接第1章" in generated[1]["content"]
    assert state["artifacts"]["chapters_text"] == "\n\n".join(item["content"] for item in generated)
    assert len(state["chapter_context_packets"]) == 2
    assert state["chapter_context_packets"][0]["previous_chapter_summary"] == ""
    assert state["chapter_context_packets"][1]["previous_chapter_summary"]
    assert len(state["chapter_progress"]) == 2
    assert all(item["status"] == "completed" for item in state["chapter_progress"])
    assert len(state["story_bible"]["chapter_summaries"]) == 2
    assert state["continuity_state"]["chapter_summaries"] == 2
    assert len(chapters_artifact["chapter_summaries"]) == 2
    assert len(chapters_artifact["wiki_writebacks"]) == 2
    assert len(state["wiki_refs"]) >= 6
    assert not state["errors"]


@pytest.mark.asyncio
async def test_planning_chain_generates_three_text_chapters_with_foreshadow_continuity(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text"], provider_profile_id="openai-compatible")
    workflow.nodes[-1].variant_policy.enabled = False
    workflow.stage_configs["text"].variant_policy = workflow.nodes[-1].variant_policy
    provider = CapturingMultiChapterProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "planning-text-three-chapters"
    inputs = {
        "project_id": "p-text-three",
        "title": "正文三章连续性门禁",
        "quality_mode": "balanced",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 3, "conflict_density": "中高"},
            "detail": {"chapter_count": 3, "must_include": ["目标", "冲突", "伏笔", "章末钩子"]},
            "text": {"chapter_count": 3, "chapter_words": 900, "batch_generate": True},
        },
    }
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[-1] == "run_completed"
    assert event_types.count("chapter_context_built") == 3
    assert event_types.count("chapter_started") == 3
    assert event_types.count("chapter_completed") == 3
    assert event_types.count("story_bible_updated") >= 6
    assert event_types.count("wiki_state_updated") == 3
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "text" for event in events)

    text_calls = [call for call in provider.calls if call["task_name"] == "chapter_text"]
    assert len(text_calls) == 3
    assert "上一章摘要: 暂无" in str(text_calls[0]["prompt"])
    assert "上一章摘要: 暂无" not in str(text_calls[1]["prompt"])
    assert "上一章摘要: 暂无" not in str(text_calls[2]["prompt"])

    state = store.read(run_id)["state"]
    chapters_artifact = state["artifacts"]["chapters"]
    generated = chapters_artifact["chapters"]
    assert state["runtime_phase"] == "completed"
    assert len(generated) == 3
    assert [item["title"] for item in generated] == ["第1章", "第2章", "第3章"]
    assert "承接第1章" in generated[1]["content"]
    assert "承接第2章" in generated[2]["content"]
    assert state["artifacts"]["chapters_text"] == "\n\n".join(item["content"] for item in generated)
    assert len(state["chapter_context_packets"]) == 3
    assert state["chapter_context_packets"][2]["previous_chapter_summary"]
    assert len(state["story_bible"]["chapter_summaries"]) == 3
    assert state["continuity_state"]["chapter_summaries"] == 3
    assert len(chapters_artifact["chapter_summaries"]) == 3
    assert len(chapters_artifact["wiki_writebacks"]) == 3
    assert len(state["wiki_refs"]) >= 7
    assert not state["errors"]


def _multi_chapter_fixture(index: int) -> dict[str, object]:
    if index == 1:
        return {
            "chapter_title": "第1章 7A-13 母带",
            "content": (
                "林澈把 7A-13 母带推进修复机时，旧港档案馆的灯正好暗了一下。"
                "底噪像潮水贴着耳膜涌来，求救声却在第三遍降噪后清晰叫出他的名字。"
                "他截下波形，发现父亲签章对应的旧式校验音藏在最后半秒，这不是传说，"
                "而是雾钟声纹证词系统留下的技术线索。\n\n"
                "主管要求他停止拷贝，林澈却把备用通道切到离线。许望舒发来消息，提醒他删改日志今晚会被清理。"
                "林澈第一次没有把旧案推回档案柜深处，他保留了母带，也把父亲签章这个伏笔压进自己的工作日志。"
            ),
            "summary": "林澈在 7A-13 母带中听见求救声，发现父亲签章与雾钟系统有关，并决定保留证据。",
            "wiki_writebacks": [{"target": "7A-13 母带", "fact": "包含求救声与父亲签章校验音", "source_chapter": "第1章"}],
            "character_shift": "林澈从回避旧案转向主动保留证据。",
            "foreshadow_updates": [{"name": "父亲签章", "status": "投放"}],
        }
    if index == 2:
        return {
            "chapter_title": "第2章 雾钟码头",
            "content": (
                "承接第1章的母带异常，许望舒在雾钟码头等到林澈时，手里只有一份被水汽泡皱的删改日志。"
                "她没有先谈报道，而是指出上一章留下的父亲签章并非孤例，蓝潮名单里还有三处相同缩写。"
                "林澈继续追问母带来源，周泊言却在黑市摊位后退半步，拒绝承认自己是幸存者。\n\n"
                "码头灯牌接连熄灭，黑市开始清理同批磁带。许望舒把周泊言推入仓库夹道，"
                "用采访材料换来他的第一句证词：雾钟不是制造记忆的机器，而是筛选谁有资格被听见。"
                "这条线索推进了父亲签章伏笔，也把三人的调查同盟推到无法回头的位置。"
            ),
            "summary": "许望舒带林澈到雾钟码头追查删改日志，周泊言被迫暴露幸存者线索，父亲签章伏笔继续推进。",
            "wiki_writebacks": [{"target": "雾钟码头", "fact": "黑市磁带与档案馆母带同批", "source_chapter": "第2章"}],
            "character_shift": "许望舒从追报道转向保护周泊言，林澈继续追查父亲签章。",
            "foreshadow_updates": [{"name": "父亲签章", "status": "推进"}],
        }
    return {
        "chapter_title": "第3章 旧港灯塔",
        "content": (
            "承接第2章的码头线索，林澈和许望舒把周泊言带到旧港灯塔下的备电机房。"
            "灯塔里残留的声纹回放证明，雾钟并不只是筛选证词，父亲签章也不是单独存在的旧物，"
            "它和一份尚未公开的备电日志绑定在一起。\n\n"
            "周泊言终于承认，他曾在灯塔里见过删改证词的操作人。林澈顺着前两章留下的伏笔，把母带、码头、"
            "灯塔三处证据连成一条闭环，决定在下一步公开完整链路，而不是只公布第一层真相。"
        ),
        "summary": "林澈和许望舒在旧港灯塔把母带、码头和备电日志连成闭环，周泊言承认见过删改证词的操作人。",
        "wiki_writebacks": [{"target": "旧港灯塔", "fact": "与备电日志和删改证词操作链有关", "source_chapter": "第3章"}],
        "character_shift": "林澈从追查单条线索转向掌握完整证据闭环。",
        "foreshadow_updates": [{"name": "备电日志", "status": "投放"}],
    }

from __future__ import annotations

import re
from typing import Any

from novel_workflow.orchestration.constants import TEXT_NODE_TYPES, VARIANT_NODE_TYPES
from novel_workflow.workflows.schemas import (
    ChapterDraft,
    ChapterProgressItem,
    CharacterEdge,
    CharacterGraph,
    CharacterNode,
    NovelRunState,
    QualityEvent,
    SelectedVariant,
    VariantPolicy,
)


def memory_query(node: Any, state: NovelRunState) -> str:
    parts = [str(state.inputs.get("title") or ""), str(state.inputs.get("theme") or ""), node.type]
    for ref in node.input_refs:
        if ref in state.artifacts:
            parts.append(str(state.artifacts[ref])[:800])
    return "\n".join(part for part in parts if part)


def effective_variant_policy(node: Any, workflow: Any) -> VariantPolicy:
    policy = node.variant_policy
    mode = workflow.quality_mode
    if node.type == "info_recommend":
        return VariantPolicy(enabled=False, candidate_count=1, retry_on_fail=False, dimensions=policy.dimensions)
    if mode == "fast":
        return VariantPolicy(enabled=False, candidate_count=1, retry_on_fail=False, dimensions=policy.dimensions)
    if mode == "balanced":
        enabled = bool(policy.enabled)
        return VariantPolicy(
            enabled=enabled,
            candidate_count=2 if enabled else 1,
            judge_provider_profile_id=policy.judge_provider_profile_id,
            judge_model=policy.judge_model,
            dimensions=policy.dimensions,
            retry_on_fail=enabled,
        )
    if mode == "deep" and node.type in VARIANT_NODE_TYPES:
        return VariantPolicy(
            enabled=True,
            candidate_count=max(3, min(5, policy.candidate_count or 3)),
            judge_provider_profile_id=policy.judge_provider_profile_id,
            judge_model=policy.judge_model,
            dimensions=policy.dimensions,
            retry_on_fail=True,
        )
    return policy


def node_with_mode_policy(node: Any, workflow: Any) -> Any:
    cloned = node.model_copy(deep=True)
    cloned.variant_policy = effective_variant_policy(cloned, workflow)
    if workflow.quality_mode == "fast":
        cloned.quality_policy.retry_on_fail = False
    if workflow.quality_mode == "deep" and cloned.type in TEXT_NODE_TYPES:
        cloned.quality_policy.retry_on_fail = True
        cloned.quality_policy.min_score = max(cloned.quality_policy.min_score, 0.84)
    return cloned


def variant_score(result: Any, index: int) -> float:
    text = str(result or "")
    length_bonus = min(len(text) / 1600, 1.0) * 0.08
    specificity = 0.04 if any(token in text for token in ("人物", "冲突", "伏笔", "世界观", "关系")) else 0.0
    return round(min(0.78 + index * 0.03 + length_bonus + specificity, 0.96), 2)


def chapter_count(node: Any, state: NovelRunState) -> int:
    stage_configs = state.inputs.get("stage_configs", {})
    detail_config = stage_configs.get("detail", {}) if isinstance(stage_configs, dict) else {}
    text_config = stage_configs.get(node.id, {}) if isinstance(stage_configs, dict) else {}
    for value in (detail_config.get("chapter_count"), text_config.get("chapter_count"), node.params.get("chapters")):
        if isinstance(value, int) and value > 0:
            return min(value, 12)
        if isinstance(value, str) and value.isdigit():
            return min(int(value), 12)
    return 3


def detail_outline_issue(node: Any, state: NovelRunState) -> str:
    target = chapter_count(node, state)
    detail = str(state.artifacts.get("detail_outline") or "")
    found = len(set(int(match) for match in re.findall(r"第\s*(\d+)\s*章", detail)))
    if found < target:
        return f"章节细纲不完整：目标 {target} 章，当前仅识别到 {found} 章，已停止进入正文创作。"
    return ""


def chapter_content(result: Any, chapter_index: int, candidate_count: int, variant_index: int) -> str:
    base = str(result or "").strip()
    marker = f"第{chapter_index}章"
    suffix = "" if candidate_count == 1 else f"\n\n[候选版本 {variant_index + 1}] 该版本强化了{'人物关系' if variant_index % 2 else '伏笔推进'}。"
    if marker in base:
        return f"{base}{suffix}"
    return f"{marker} 正文\n\n{base}{suffix}"


def chapter_deltas(content: str) -> list[str]:
    paragraphs = [part.strip() for part in content.split("\n") if part.strip()]
    if len(paragraphs) >= 2:
        return paragraphs
    size = max(80, len(content) // 3)
    return [content[index : index + size] for index in range(0, len(content), size) if content[index : index + size]]


def update_worldbuilding_state(node: Any, result: Any, state: NovelRunState, chapter_name: str = "") -> None:
    text = str(result or "")
    if node.type == "info_recommend":
        state.worldbuilding_state = {
            "source": "创作立项定稿",
            "seed": text[:320],
            "hard_rules": ["世界观硬设定不得被后续阶段推翻", "人物关系变化必须有事件触发", "伏笔需在细纲或正文中记录状态"],
            "tone": "悬疑、强情节、群像关系、信息差",
            "updated_by": node.id,
        }
        return
    if node.type == "chapter_text":
        state.worldbuilding_state.setdefault("chapter_impacts", []).append({"chapter": chapter_name, "impact": text[:180]})
        state.worldbuilding_state["updated_by"] = f"{node.id}:{chapter_name}"
        return
    if node.type in {"summary", "outline", "detail_outline"}:
        state.worldbuilding_state.setdefault("planning_updates", []).append({"stage": node.type, "summary": text[:220]})
        state.worldbuilding_state["updated_by"] = node.id


def wiki_state(runner: Any, state: NovelRunState) -> dict[str, Any]:
    return {
        "documents": len(state.wiki_refs),
        "latest_refs": state.wiki_refs[-5:],
        "constraint_kinds": ["人物状态", "世界观硬设定", "未回收伏笔", "章节摘要", "关系拓扑"],
        "status": runner.wiki_store.status(state.project_id),
        "story_bible": state.story_bible.model_dump(),
    }


def continuity_state(state: NovelRunState) -> dict[str, Any]:
    open_foreshadows = [item for item in state.story_bible.foreshadow_ledger if item.get("status") != "recovered"]
    blocking_findings = [
        finding
        for report in state.quality_reports
        if isinstance(report, dict)
        for finding in report.get("findings", [])
        if isinstance(finding, dict) and finding.get("blocking")
    ]
    return {
        "open_foreshadows": len(open_foreshadows),
        "chapter_summaries": len(state.story_bible.chapter_summaries),
        "world_rules": len(state.story_bible.world_rules),
        "blocking_findings": blocking_findings[-5:],
        "revision_directives": len(state.revision_directives),
    }


def quality_event(node: Any, result: Any) -> QualityEvent:
    text = str(result or "")
    length_score = min(len(text) / 1200, 1.0) * 0.22
    structure_score = 0.24 if any(token in text for token in ("章节", "梗概", "大纲", "正文", "世界观")) else 0.16
    continuity_score = 0.22 if node.memory_policy.read else 0.18
    specificity_score = 0.22 if any(token in text for token in ("人物", "冲突", "伏笔", "关系")) else 0.14
    score = round(min(0.18 + length_score + structure_score + continuity_score + specificity_score, 0.96), 2)
    warnings: list[str] = []
    if len(text) < 80:
        warnings.append("输出偏短，需要补充细节")
    if node.memory_policy.read and "Wiki" not in text and node.type in {"summary", "outline", "detail_outline", "chapter_text"}:
        warnings.append("已读取 Wiki 约束，请关注产物是否体现连续性")
    passed = score >= node.quality_policy.min_score
    if not passed:
        warnings.append("低于阶段最低质量分，建议重试或调高上下文约束")
    return QualityEvent(
        node_id=node.id,
        node_type=node.type,
        label=node.label,
        score=score,
        min_score=node.quality_policy.min_score,
        passed=passed,
        checks={
            "continuity": score >= 0.8,
            "character_consistency": "人物" in text or node.type == "info_recommend",
            "worldbuilding_conflict": True,
            "repetition": len(set(text.split())) >= max(1, len(text.split()) // 5),
        },
        warnings=warnings,
    )


def character_graph(node_id: str) -> CharacterGraph:
    nodes = [
        CharacterNode(id="c1", name="林雾", role="主角", faction="旧港调查线", status="追查记忆失真"),
        CharacterNode(id="c2", name="沈白", role="盟友/嫌疑人", faction="档案馆", status="掌握旧案碎片"),
        CharacterNode(id="c3", name="周砚", role="对手", faction="港务集团", status="隐藏关键证据"),
        CharacterNode(id="c4", name="阿青", role="线索人物", faction="码头旧友", status="关系摇摆"),
        CharacterNode(id="c5", name="许檀", role="幕后推动者", faction="记忆实验室", status="未公开真实目的"),
    ]
    edges = [
        CharacterEdge(source="c1", target="c2", relation="互信未稳", strength=0.62),
        CharacterEdge(source="c1", target="c3", relation="调查/压制", strength=0.78),
        CharacterEdge(source="c2", target="c5", relation="旧案关联", strength=0.54),
        CharacterEdge(source="c3", target="c5", relation="利益同盟", strength=0.7),
        CharacterEdge(source="c1", target="c4", relation="童年旧识", strength=0.66),
    ]
    return CharacterGraph(nodes=nodes, edges=edges, updated_by=node_id)


def chapter_progress(node: Any, result: Any, quality_score: float) -> list[ChapterProgressItem]:
    text = str(result or "")
    target = int(node.params.get("chapters") or 3)
    words = max(800, len(text))
    return [
        ChapterProgressItem(
            volume="第一卷",
            chapter=f"第{index}章",
            status="completed" if index <= min(target, 3) else "planned",
            words=words // max(1, min(target, 3)) if index <= min(target, 3) else 0,
            quality_score=quality_score if index <= min(target, 3) else 0.0,
            node_id=node.id,
        )
        for index in range(1, target + 1)
    ]


def chapter_draft(chapter_name: str, content: str, variant_id: str, score: float) -> ChapterDraft:
    return ChapterDraft(chapter=chapter_name, content=content, status="completed", words=len(content), variant_id=variant_id, score=score)


def selected_variant(node_id: str, variant_id: str, score: float, *, chapter: str = "") -> SelectedVariant:
    return SelectedVariant(
        node_id=node_id,
        chapter=chapter,
        variant_id=variant_id,
        score=score,
        reason="综合连续性、人物一致性、伏笔推进、语言质感和模板味选择。",
    )

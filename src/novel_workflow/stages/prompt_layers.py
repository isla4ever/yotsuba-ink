"""Phase 10.0C constraint pyramid: layered prompt sections and cropping.

Layer semantics (docs/architecture/phase-10-workbench-refactor-and-stage-contract.md §4.2):
  L0 hard constraints    -> system, never cropped
  L1 stage task + rubric -> user, never cropped
  L2 upstream artifacts  -> user, truncated last
  L3 entity state        -> user, on-demand hits only
  L4 voice spec          -> user, dropped second
  L5 references          -> user, dropped first
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from novel_workflow.orchestration.character_network import compact_graph_lines
from novel_workflow.providers.base import PROMPT_SYSTEM_SPLIT, split_system_prompt  # noqa: F401 (re-export)
from novel_workflow.workflows.schemas import NovelRunState, WorkflowNode

PROMPT_CHAR_BUDGET = 24000

STAGE_QUOTA_TEXT: dict[str, str] = {
    "info_recommend": "主要人物 5-9 名（tier 仅限 protagonist/major/supporting，每名人物给出 faction 阵营）；世界观硬设定不超过 12 条；relationships 8-20 条并给出 kind/polarity。",
    "summary": "禁止新增任何人物、地点或组织；只能引用创作立项已确认的人物并深化其弧线；发现人物阵容不足时在 consistency_checks 中说明，而不是私自新增。",
    "outline": "每卷最多通过 new_characters 新增 4 名配角（tier=supporting，需给定位与立场）；不得新增主角级人物；世界揭示必须引用已确认世界观锚点；不得修改既有硬设定。",
    "detail_outline": "每章最多通过 new_npcs 新增 2 名 NPC（不承担关键剧情功能）；POV 和 character_shift 只能引用已注册的非 NPC 人物；不得新增世界观硬规则。",
    "chapter_text": "禁止引入任何未注册的人物、地点或组织；新的事实只能通过 wiki_writebacks 提案写回；正文出现未注册专有名词将被质量阀门阻断。",
}


@dataclass
class PromptSection:
    layer: int
    name: str
    text: str


@dataclass
class PromptPlan:
    system: str
    user: str
    dropped_layers: list[str] = field(default_factory=list)

    def render(self) -> str:
        return f"{self.system}{PROMPT_SYSTEM_SPLIT}{self.user}"


def assemble_user(sections: list[PromptSection], *, char_budget: int = PROMPT_CHAR_BUDGET) -> tuple[str, list[str]]:
    """Render user sections in layer order, cropping L5 -> L4 -> L3 when over budget.

    L0 lives in the system prompt and is never passed here; L1/L2 sections are
    kept and only tail-truncated as a last resort.
    """
    ordered = sorted((section for section in sections if section.text.strip()), key=lambda item: item.layer)
    dropped: list[str] = []
    for crop_layer in (5, 4, 3):
        text = "\n\n".join(section.text for section in ordered)
        if len(text) <= char_budget:
            break
        survivors = [section for section in ordered if section.layer != crop_layer]
        dropped.extend(section.name for section in ordered if section.layer == crop_layer)
        ordered = survivors
    text = "\n\n".join(section.text for section in ordered)
    if len(text) > char_budget:
        text = text[:char_budget] + "\n（上下文超出预算，已截断低优先级内容。）"
    return text, dropped


def hard_constraints(node: WorkflowNode, state: NovelRunState) -> str:
    lines: list[str] = ["## 硬约束（不可违背，优先级最高）"]
    world_rules = list(state.story_bible.world_rules)
    extra_rules = state.worldbuilding_state.get("hard_rules") if isinstance(state.worldbuilding_state, dict) else None
    if isinstance(extra_rules, list):
        world_rules.extend(str(item) for item in extra_rules if str(item).strip())
    unique_rules = list(dict.fromkeys(rule for rule in world_rules if rule))[:15]
    if unique_rules:
        lines.append("世界观硬设定：")
        lines.extend(f"- {rule}" for rule in unique_rules)
    conflicts = [item for item in state.canon_conflicts if isinstance(item, dict) and item.get("status") == "pending"][:3]
    if conflicts:
        lines.append("未决事实冲突（禁止在冲突裁决前采用任一说法为既定事实）：")
        lines.extend(f"- {item.get('target', '')}｜{item.get('claim_key', '')}" for item in conflicts)
    brief = state.artifacts.get("info_recommend")
    if isinstance(brief, dict):
        constraints = [str(item) for item in brief.get("downstream_constraints", []) if str(item).strip()][:8]
        if constraints:
            lines.append("创作立项下游约束：")
            lines.extend(f"- {item}" for item in constraints)
    quota = STAGE_QUOTA_TEXT.get(node.type)
    if quota:
        lines.append(f"阶段拓展配额：{quota}")
    if len(lines) == 1:
        lines.append("- 本阶段暂无既有硬约束；你的输出将成为后续阶段的硬约束来源。")
    return "\n".join(lines)


def entity_state(node: WorkflowNode, state: NovelRunState) -> str:
    if node.type == "info_recommend":
        return "## 人物与阵营现状\n本阶段建立人物基线，暂无既有图谱。"
    graph = state.character_graph
    if not graph.nodes:
        return "## 人物与阵营现状\n暂无已注册人物。"
    only_names: set[str] | None = None
    if node.type == "chapter_text" and state.chapter_context_packets:
        packet = state.chapter_context_packets[-1]
        haystack = f"{packet.chapter_outline}\n{packet.previous_chapter_summary}"
        only_names = {item.name for item in graph.nodes if item.name and item.name in haystack}
        if not only_names:
            only_names = {item.name for item in graph.nodes if item.tier in {"protagonist", "major"}}
    lines = compact_graph_lines(graph, only_names=only_names)
    factions = "、".join(f"{item.name}({item.stance})" for item in graph.factions) or "暂无"
    scope = "（仅注入本章相关人物）" if only_names is not None else ""
    return "## 人物与阵营现状" + scope + "\n阵营：" + factions + "\n" + "\n".join(lines)


def voice_spec_section(node: WorkflowNode, state: NovelRunState) -> str:
    brief = state.artifacts.get("info_recommend")
    spec = brief.get("voice_spec") if isinstance(brief, dict) else None
    if not isinstance(spec, dict):
        return ""
    lines = ["## 风格规格（Voice Spec）"]
    if spec.get("narration"):
        lines.append(f"- 叙事：{spec['narration']}")
    if spec.get("rhythm"):
        lines.append(f"- 节奏：{spec['rhythm']}")
    banned = [str(item) for item in spec.get("banned_words", []) if str(item).strip()]
    if banned:
        lines.append(f"- 禁用词：{'、'.join(banned[:20])}")
    cliches = [str(item) for item in spec.get("cliche_slots", []) if str(item).strip()]
    if cliches:
        lines.append(f"- 需要规避的陈词槽：{'、'.join(cliches[:10])}")
    sheets = [item for item in spec.get("per_character", []) if isinstance(item, dict)]
    if node.type == "chapter_text" and state.chapter_context_packets:
        haystack = state.chapter_context_packets[-1].chapter_outline
        hit = [item for item in sheets if str(item.get("character") or "") and str(item.get("character")) in haystack]
        sheets = hit or sheets
    for item in sheets[:8]:
        detail = "；".join(
            part
            for part in (
                str(item.get("habits") or ""),
                f"口头禅：{item.get('catchphrase')}" if item.get("catchphrase") else "",
                f"语域：{item.get('speech_register')}" if item.get("speech_register") else "",
                f"绝不说：{item.get('never_says')}" if item.get("never_says") else "",
            )
            if part
        )
        lines.append(f"- {item.get('character', '')}：{detail or '未记录'}")
    return "\n".join(lines) if len(lines) > 1 else ""

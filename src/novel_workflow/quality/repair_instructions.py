from __future__ import annotations

from typing import Any


def quality_revision_instruction(finding: Any) -> str:
    dimension = finding.get("dimension") if isinstance(finding, dict) else getattr(finding, "dimension", "")
    evidence = str(finding.get("evidence") if isinstance(finding, dict) else getattr(finding, "evidence", "") or "")
    voice_instruction = _voice_drift_instruction(dimension, evidence)
    if voice_instruction:
        return voice_instruction
    instructions = {
        "chapter_handoff": "在当前章节开头或关键转折处补足上一章事件承接，不改变章节主目标。",
        "foreshadowing": "加入一个与未回收伏笔相关的动作、线索或人物反应，避免直接揭底。",
        "template_taste": "压缩重复表达，增加具体感官、动作和人物动机。",
        "structure": "补齐缺失结构字段，保持与上游 Story Brief 和 Wiki 约束一致。",
    }
    return instructions.get(dimension, "局部修订该问题，保持主线、人物状态和世界观硬设定不变。")


def _voice_drift_instruction(dimension: str, evidence: str) -> str:
    """Targeted rewrite semantics: drift never rolls back committed text."""
    detail = f"（命中：{evidence}）" if evidence else ""
    instructions = {
        "voice_banned_word": f"定向修写：替换 Voice Spec 禁用词{detail}，保持情节、人物状态和既有段落结构不变。",
        "voice_cliche": f"定向修写：用具体动作、感官或人物动机改写命中的陈词槽{detail}，不回滚已定稿内容。",
        "voice_dialogue_ratio": f"定向修写：按 Voice Spec 声明的对话叙述比调整对话与叙述配比{detail}，不改变本章事件与结局。",
        "voice_sentence_length": f"定向修写：拆分超长句、压缩冗余从句以贴合 Voice Spec 句长偏好{detail}，保持语义与信息量不变。",
    }
    return instructions.get(dimension, "")

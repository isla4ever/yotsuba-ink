from __future__ import annotations

import json
from typing import Any, Iterable

from novel_workflow.output_contracts.provider_tasks import SpineSemanticFinding


_SYSTEMIC_FINDING_CODES = {
    "premature_resolution",
    "redundant_progress",
    "causal_handoff",
}

# These phrases describe a resolved institutional or public outcome. They are
# intentionally narrow: ordinary setup such as "资格面临吊销" is allowed, but
# a pre-climax turn that already says "最终裁决" or "正式吊销" leaves the
# code-owned climax with only repetition or aftermath.
_RESOLUTION_MARKERS = (
    "最终裁决",
    "最终听证",
    "正式裁决",
    "公开全部真相",
    "公开了全部真相",
    "被正式吊销",
    "正式吊销执业资格",
    "工程重新启动",
    "工程恢复",
    "工程正式开工",
    "正式平反",
    "警方结案",
    "免于起诉",
    "被正式解雇",
    "被正式开除",
    "正式解除职务",
    "被判处",
    "永久吊销",
    "失去调度员资格",
)


def deterministic_spine_resolution_findings(
    payload: dict[str, Any],
) -> list[SpineSemanticFinding]:
    """Catch terminal outcomes placed before the code-owned climax.

    The model review remains the literary judge, but this ordering invariant is
    too important to leave to a single probabilistic pass. The gate only flags
    explicit resolution language and never infers a story result from generic
    words such as "调查" or "证据".
    """

    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) < 2:
        return []
    climax_index = next(
        (
            index
            for index, turn in enumerate(turns)
            if isinstance(turn, dict)
            and "climax" in (turn.get("milestones") or [])
        ),
        len(turns) - 2,
    )
    if climax_index <= 0:
        return []
    findings: list[SpineSemanticFinding] = []
    for index, turn in enumerate(turns[:climax_index]):
        if not isinstance(turn, dict):
            continue
        text = " ".join(str(turn.get(field) or "") for field in ("cause", "change"))
        markers = [marker for marker in _RESOLUTION_MARKERS if marker in text]
        if not markers:
            continue
        findings.append(
            SpineSemanticFinding(
                code="premature_resolution",
                turn_refs=[f"turn-{index + 1}", f"turn-{climax_index + 1}"],
                claim=(
                    f"turn-{index + 1} already states terminal outcome language "
                    f"({', '.join(markers)}) before the code-owned climax turn-{climax_index + 1}."
                ),
                required_fix=(
                    f"Move the decisive public or institutional outcome to turn-{climax_index + 1}; "
                    f"make turn-{index + 1} a non-final pressure, choice, or failed attempt."
                ),
            )
        )
        if len(findings) >= 3:
            break
    return findings


def build_spine_repair_material(
    base_material: dict[str, Any],
    rejected_spine: dict[str, Any],
    findings: Iterable[SpineSemanticFinding],
) -> dict[str, Any]:
    """Build one private repair context without preserving a broken chain by accident."""

    finding_list = list(findings)
    finding_payload = [item.model_dump(mode="json") for item in finding_list]
    systemic_count = len(
        _SYSTEMIC_FINDING_CODES.intersection(item.code for item in finding_list)
    )
    requires_fresh_replan = len(finding_list) >= 4 or systemic_count >= 2
    common_direction = (
        "保持 Story Brief、精确 turn 数、代码锚点位置和 ending_promise 不变。"
        "不得新增具名人物、改变终局承诺或用更多取证步骤填充。专业、法律或纪律后果必须"
        "来自受罚者自己的行为、疏忽、职责或责任；他人的公开行为只能触发暴露与追责，不能替其承担过错。"
        "无辜家属的疾病、悲伤或关系伤害可以是他人选择的连带代价，不要求受害者先作出应受伤害的选择。"
        "Cast 前只使用稳定功能称谓，不得为了行动主体而取人名；真正由机构程序完成的听证、审计或裁决"
        "可以保持机构主体。只遵守 Brief 明示的世界规则，不得额外发明法定程序。"
    )
    serialized_findings = json.dumps(
        finding_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if requires_fresh_replan:
        direction = (
            "以下问题证明原草稿的因果架构失效。不要复原、改写或沿用原草稿；从冻结 Story Brief 独立设计"
            "一条全新的完整因果链，再一次性返回全部 turns。每个前高潮 turn 必须产生不同种类的新压力、"
            "关系选择或行动限制，主案裁决与核心代价只在代码指定 climax 完成，aftermath 只落下余波。"
            + common_direction
            + serialized_findings
        )
        return {
            **base_material,
            "discarded_spine_failure": {
                "strategy": "fresh_causal_replan",
                "findings": finding_payload,
            },
            "revision_request": {"direction": direction},
        }

    direction = (
        "只重写 findings 指向的 turn 及相邻因果桥，并核对改动后的前后交接。"
        + common_direction
        + serialized_findings
    )
    return {
        **base_material,
        "rejected_spine_draft": rejected_spine,
        "revision_request": {"direction": direction},
    }


__all__ = [
    "build_spine_repair_material",
    "deterministic_spine_resolution_findings",
]

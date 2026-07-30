from __future__ import annotations

from typing import Any


CHAPTER_PIPELINE_STEPS = {
    1: ("chapter_located", "章节定位"),
    2: ("context_assembled", "上下文装配"),
    3: ("execution_script_built", "执行剧本"),
    4: ("draft_generated", "正文生成"),
    5: ("contract_validated", "合同校验"),
    6: ("draft_persisted", "章节落盘"),
    7: ("quality_audited", "文风与连续性审计"),
    8: ("postprocessed", "章后处理"),
    9: ("tension_scored", "张力评分"),
    10: ("chapter_settled", "章节结算"),
}


def chapter_pipeline_step_event(
    run_id: str,
    node: Any,
    chapter: str,
    step: int,
    **payload: Any,
) -> dict[str, Any]:
    key, label = CHAPTER_PIPELINE_STEPS[step]
    return {
        "type": "chapter_pipeline_step_completed",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "label": node.label,
        "chapter": chapter,
        "step": step,
        "step_key": key,
        "step_label": label,
        "step_status": "completed",
        **payload,
    }


def canon_commit_event(
    run_id: str,
    node: Any,
    chapter: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "canon_facts_committed",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "label": node.label,
        "chapter": chapter,
        "committed": summary.get("committed", []),
        "resolved": summary.get("resolved", []),
        "pending_conflicts": summary.get("pending_conflicts", []),
        "message": "结构化 Canon 事实已按来源和冲突决策写入。",
    }

from __future__ import annotations

from typing import Any

from novel_workflow.orchestration.helpers import effective_variant_policy, selected_variant, variant_score
from novel_workflow.usage import record_stage_usage


async def execute_with_variants(runner: Any, node: Any, state: Any, workflow: Any) -> tuple[Any, list[dict[str, Any]]]:
    policy = effective_variant_policy(node, workflow)
    if not policy.enabled or node.type not in {"summary", "outline", "detail_outline", "chapter_text"}:
        result = await runner.stages.execute(node, state)
        record_stage_usage(
            state,
            stage_key=node.id,
            node=node,
            prompt_text=runner.stages.prompt_builder.build(node, state),
            output_text=str(result or ""),
        )
        return result, []

    candidates = []
    events: list[dict[str, Any]] = []
    prompt_text = runner.stages.prompt_builder.build(node, state)
    for index in range(policy.candidate_count):
        result = await runner.stages.execute(node, state)
        variant_id = f"{node.id}-v{index + 1}"
        score = variant_score(result, index)
        candidate = {"variant_id": variant_id, "node_id": node.id, "result": result, "score": score, "index": index + 1}
        candidates.append(candidate)
        events.append(
            {
                "type": "variant_generated",
                "node_id": node.id,
                "node_type": node.type,
                "label": node.label,
                "variant": {key: value for key, value in candidate.items() if key != "result"},
                "preview": str(result)[:280],
            }
        )
    best = max(candidates, key=lambda item: item["score"])
    events.append(
        {
            "type": "variant_judged",
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "variants": [{key: value for key, value in item.items() if key != "result"} for item in candidates],
            "dimensions": policy.dimensions,
        }
    )
    selected = selected_variant(node.id, str(best["variant_id"]), float(best["score"]))
    state.selected_variants.append(selected)
    summary = record_stage_usage(
        state,
        stage_key=node.id,
        node=node,
        prompt_text=prompt_text,
        output_text=str(best["result"] or ""),
        candidate_count=policy.candidate_count,
    )
    events.append({"type": "best_variant_selected", "node_id": node.id, "node_type": node.type, "label": node.label, "selected": selected.model_dump()})
    events.append({"type": "token_estimate_updated", "node_id": node.id, "token_estimates": state.token_estimates})
    events.append({"type": "stage_usage_updated", "node_id": node.id, "node_type": node.type, "usage": summary.model_dump()})
    events.append({"type": "stage_usage_finalized", "node_id": node.id, "node_type": node.type, "usage": summary.model_dump()})
    return best["result"], events

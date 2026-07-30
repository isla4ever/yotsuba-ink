from __future__ import annotations

from typing import Any

from novel_workflow.orchestration.chapter_artifact import upsert_chapter_draft, upsert_selected_variant
from novel_workflow.orchestration.helpers import chapter_content, chapter_draft, selected_variant, variant_score
from novel_workflow.output_contracts import validate_chapter_generation
from novel_workflow.usage import BudgetExceededError, drain_budget_events


async def generate_chapter_candidates(
    runner: Any,
    node: Any,
    state: Any,
    run_id: str,
    chapter_index: int,
    chapter_name: str,
    candidate_count: int,
    policy: Any,
) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]]]:
    candidates: list[tuple[Any, dict[str, Any]]] = []
    events: list[dict[str, Any]] = []
    for variant_index in range(candidate_count):
        variant_id = f"{node.id}-c{chapter_index}-v{variant_index + 1}"
        saved = next(
            (
                item for item in state.chapter_drafts
                if item.chapter == chapter_name and item.variant_id == variant_id and item.content and item.artifact
            ),
            None,
        )
        if saved is not None:
            candidates.append((saved, saved.artifact))
            continue
        try:
            validation = validate_chapter_generation(await runner.stages.execute(node, state))
            events.extend(drain_budget_events(state))
        except BudgetExceededError:
            events.extend(drain_budget_events(state))
            raise
        except Exception as exc:
            events.extend(drain_budget_events(state))
            validation = None
            event = _event("variant_failed", run_id, node, chapter=chapter_name, variant_index=variant_index + 1, error=str(exc))
            runner.run_store.append_event(run_id, event)
            events.append(event)
        if validation is None or not validation.valid:
            if validation is not None:
                event = _event(
                    "variant_failed",
                    run_id,
                    node,
                    chapter=chapter_name,
                    variant_index=variant_index + 1,
                    error="; ".join(validation.errors),
                )
                runner.run_store.append_event(run_id, event)
                events.append(event)
            continue
        result = validation.artifact
        content = chapter_content(result, chapter_index, candidate_count, variant_index)
        draft = chapter_draft(
            chapter_name,
            content,
            variant_id,
            variant_score(content, variant_index),
            result,
        )
        upsert_chapter_draft(state, draft)
        candidates.append((draft, result))
        runner.run_store.update_state(run_id, state)
        if policy.enabled:
            event = _event("variant_generated", run_id, node, chapter=chapter_name, variant=draft.model_dump(), preview=content[:280])
            runner.run_store.append_event(run_id, event)
            events.append(event)
    if not candidates:
        return None, "", events
    best, result = max(candidates, key=lambda item: item[0].score)
    if policy.enabled:
        selected = selected_variant(node.id, best.variant_id, best.score, chapter=chapter_name)
        upsert_selected_variant(state, selected)
        selection_events = [
                _event(
                    "variant_judged",
                    run_id,
                    node,
                    chapter=chapter_name,
                    variants=[item[0].model_dump() for item in candidates],
                    dimensions=policy.dimensions,
                ),
                _event("best_variant_selected", run_id, node, chapter=chapter_name, selected=selected.model_dump()),
        ]
        runner.run_store.update_state(run_id, state)
        for event in selection_events:
            runner.run_store.append_event(run_id, event)
        events.extend(selection_events)
    return result, best.content, events


def _event(event_type: str, run_id: str, node: Any, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, **payload}

"""Chapter model-review orchestration (Phase 10.4a).

Bridges `quality/model_review.py` into the chapter pipeline:
- fast mode never calls the reviewer (cost contract, roadmap §10.3);
- results are bound to the chapter version signature and cached in
  `state.model_review_state`, so recovery/replay never re-bills a review;
- tension scores are upserted into `story_bible.tension_track` and announced
  via the `chapter_tension_scored` event;
- provider failures record an `unavailable` review and never block commit.
"""
from __future__ import annotations

from typing import Any

from novel_workflow.quality.model_review import (
    review_content_signature,
    run_model_review,
    upsert_tension_entry,
)
from novel_workflow.usage import drain_budget_events


def chapter_model_reviewer(runner: Any, node: Any, state: Any, workflow: Any, run_id: str) -> Any:
    """Return an async `(chapter, content) -> (review_dump | None, events)` hook, or None."""
    if workflow.quality_mode == "fast" or node.type != "chapter_text":
        return None

    async def review(chapter_name: str, content: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        version = _chapter_version(state, node, chapter_name)
        signature = review_content_signature(node.id, chapter_name, version, content)
        cached = state.model_review_state.get(chapter_name)
        if isinstance(cached, dict) and cached.get("content_signature") == signature:
            # Same chapter version already reviewed — recovery must not call or bill again.
            report = cached.get("report")
            usable = report if isinstance(report, dict) and cached.get("status") == "completed" else None
            return usable, []

        report = await run_model_review(
            runner.providers,
            node,
            state,
            chapter=chapter_name,
            content=content,
            run_store=runner.run_store,
            chapter_version=version,
        )
        events = [{"run_id": run_id, **event} for event in drain_budget_events(state)]
        dump = report.model_dump()
        state.model_review_state[chapter_name] = {
            "status": report.status,
            "content_signature": report.content_signature,
            "chapter_version": version,
            "report": dump,
        }
        if report.status == "completed":
            upsert_tension_entry(
                state.story_bible,
                chapter=chapter_name,
                score=report.tension.score,
                basis=report.tension.basis,
            )
            events.append(_event("model_review_completed", run_id, node, chapter=chapter_name, model_review=dump))
            events.append(
                _event(
                    "chapter_tension_scored",
                    run_id,
                    node,
                    chapter=chapter_name,
                    score=report.tension.score,
                    basis=report.tension.basis,
                    source="model_review",
                )
            )
        else:
            events.append(
                _event(
                    "model_review_unavailable",
                    run_id,
                    node,
                    chapter=chapter_name,
                    reason=report.error or "模型评审暂不可用",
                )
            )
        runner.run_store.update_state(run_id, state)
        for event in events:
            runner.run_store.append_event(run_id, event)
        return (dump if report.status == "completed" else None), events

    return review


def stored_model_review(state: Any, chapter_name: str) -> dict[str, Any]:
    entry = state.model_review_state.get(chapter_name) if isinstance(state.model_review_state, dict) else None
    report = entry.get("report") if isinstance(entry, dict) else None
    return report if isinstance(report, dict) else {}


def _chapter_version(state: Any, node: Any, chapter_name: str) -> int:
    artifact = state.artifacts.get(node.output_key or node.id)
    chapters = artifact.get("chapters") if isinstance(artifact, dict) else None
    if isinstance(chapters, list):
        for item in chapters:
            if isinstance(item, dict) and str(item.get("title") or "") == chapter_name:
                try:
                    return int(item.get("version") or 0)
                except (TypeError, ValueError):
                    return 0
    return 0


def _event(event_type: str, run_id: str, node: Any, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, **payload}

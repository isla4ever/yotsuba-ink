from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from novel_workflow.output_contracts.artifacts_vnext import STAGE_ORDER, StageId
from novel_workflow.runtime.graph.chapter_graph import ReviewerSpec, build_chapter_graph
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.failure import emit_terminal_failure, guarded_node
from novel_workflow.runtime.graph.stage_graph import build_stage_graph
from novel_workflow.runtime.graph.state import NarrativeRunState


def build_narrative_graph(
    executor: StageExecutor,
    *,
    checkpointer: Any,
    reviewers: tuple[ReviewerSpec, ...] | None = None,
):
    builder = StateGraph(NarrativeRunState)

    def load_run(state: NarrativeRunState) -> dict[str, Any]:
        definition = executor.runs.definition(state["run_id"])
        statuses = {stage: "locked" for stage in STAGE_ORDER}
        statuses["brief"] = "available"
        executor.events.append(
            state["run_id"],
            event_id=f"{state['run_id']}:started",
            type="run.started",
            stage_id="brief",
            node_id="load_run",
            status="running",
        )
        return {
            "project_id": definition.project_id,
            "workflow_revision": definition.workflow_revision,
            "quality_mode": definition.quality_mode,
            "scale_profile_ref": f"run-definition:{definition.run_id}:scale-profile",
            "artifact_refs": {},
            "candidate_artifact_refs": {},
            "chapter_version_refs": {},
            "chapter_attempts": {},
            "chapter_revision_directions": {},
            "context_manifest_ref": "",
            "active_stage_id": "brief",
            "active_chapter_number": 0,
            "active_chapter_id": "",
            "stage_status": statuses,
            "status": "running",
            "domain_revision": 0,
            "stage_attempts": {},
            "stage_revision_directions": {},
            "decision_actions": {},
            "decision_ids": {},
            "pending_operation_refs": [],
            "review_operation_refs": [],
            "failure": None,
        }

    def finalize_run(state: NarrativeRunState) -> dict[str, Any]:
        executor.events.append(
            state["run_id"],
            event_id=f"{state['run_id']}:completed",
            type="run.completed",
            stage_id="export",
            node_id="finalize_run",
            status="completed",
        )
        return {"status": "completed", "active_stage_id": "export"}

    def halt_run(state: NarrativeRunState) -> dict[str, Any]:
        # A guarded-node failure ends the graph cleanly, so SSE observers only
        # learn the run died if a terminal event reaches the log. Stage
        # subgraphs already announce their own failures with the same event
        # ids, so this replays as a no-op for them; top-level guarded nodes
        # (derive_cast_demand, derive_volume_boundary) rely on this net.
        # Cancellation is user-initiated and needs no announcement.
        if state.get("failure") is None:
            return {}
        stage_id = state.get("active_stage_id") or "brief"
        return emit_terminal_failure(executor, state, stage_id)

    builder.add_node("load_run", load_run)
    for stage_id in ("brief", "spine", "cast", "volumes", "detail"):
        builder.add_node(stage_id, build_stage_graph(stage_id, executor))
    builder.add_node(
        "text",
        build_chapter_graph(executor, **({"reviewers": reviewers} if reviewers is not None else {})),
    )
    for stage_id in ("cover", "export"):
        builder.add_node(stage_id, build_stage_graph(stage_id, executor))

    async def derive_role_demands(state: NarrativeRunState) -> dict[str, Any]:
        return await executor.generate_role_demand_proposal(state)

    async def derive_volume_boundaries(state: NarrativeRunState) -> dict[str, Any]:
        return await executor.generate_volume_boundary_proposal(state)

    builder.add_node(
        "derive_cast_demand",
        guarded_node(executor, "cast.derive_role_demand", "cast", derive_role_demands),
    )
    builder.add_node(
        "derive_volume_boundary",
        guarded_node(executor, "cast.derive_volume_boundary", "volumes", derive_volume_boundaries),
    )
    builder.add_node("finalize_run", finalize_run)
    builder.add_node("halt_run", halt_run)

    path = [
        "load_run",
        "brief",
        "spine",
        "derive_cast_demand",
        "cast",
        "derive_volume_boundary",
        "volumes",
        "detail",
        "text",
        "cover",
        "export",
        "finalize_run",
    ]
    builder.add_edge(START, path[0])
    for source, target in zip(path, path[1:]):
        builder.add_conditional_edges(
            source,
            _continue_or_stop,
            {"continue": target, "stop": "halt_run"},
        )
    builder.add_edge("finalize_run", END)
    builder.add_edge("halt_run", END)
    return builder.compile(checkpointer=checkpointer, name="yotsuba_narrative_runtime")


def _continue_or_stop(state: NarrativeRunState) -> str:
    return "stop" if state.get("status") in {"cancelled", "failed"} else "continue"


__all__ = ["build_narrative_graph"]

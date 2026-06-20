from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.api.bootstrap import list_provider_profiles
from novel_workflow.api.dependencies import run_state_or_404
from novel_workflow.api.sse import sse_payload, stream_response, stream_runner_events
from novel_workflow.references.context_injection import enrich_reference_summary, rag_blocking_issue
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import ArtifactApprovalRequest, BriefRegenerateRequest, NovelRunState, ProviderProfile, RunRequest, WorkflowDefinition


router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("")
async def create_run(request: Request, payload: RunRequest) -> dict[str, str]:
    try:
        workflow = WorkflowDefinition.model_validate(request.app.state.workflow_store.read(payload.workflow_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {payload.workflow_id}") from exc
    workflow.provider_profiles = list_provider_profiles(request.app)
    block = rag_blocking_issue(request.app, payload.inputs)
    if block:
        raise HTTPException(status_code=409, detail=block)
    run_id = payload.run_id or str(uuid4())
    request.app.state.run_store.create(run_id, workflow, payload.inputs)
    return {"run_id": run_id}


@router.get("/{run_id}")
async def get_run(request: Request, run_id: str) -> dict[str, object]:
    try:
        return request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc


@router.get("/{run_id}/quality")
async def get_run_quality(request: Request, run_id: str) -> dict[str, object]:
    state = run_state_or_404(request.app, run_id)
    return {
        "run_id": run_id,
        "quality_events": state.get("quality_events", []),
        "quality_reports": state.get("quality_reports", []),
        "revision_directives": state.get("revision_directives", []),
        "continuity_state": state.get("continuity_state", {}),
    }


@router.get("/{run_id}/chapters")
async def get_run_chapters(request: Request, run_id: str) -> dict[str, object]:
    return {"run_id": run_id, "chapter_progress": run_state_or_404(request.app, run_id).get("chapter_progress", [])}


@router.get("/{run_id}/character-graph")
async def get_run_character_graph(request: Request, run_id: str) -> dict[str, object]:
    return {"run_id": run_id, "character_graph": run_state_or_404(request.app, run_id).get("character_graph", {})}


@router.get("/{run_id}/writing")
async def get_run_writing(request: Request, run_id: str) -> dict[str, object]:
    state = run_state_or_404(request.app, run_id)
    return {
        "run_id": run_id,
        "current_phase": state.get("current_phase", "planning"),
        "chapter_progress": state.get("chapter_progress", []),
        "chapter_drafts": state.get("chapter_drafts", []),
        "selected_variants": state.get("selected_variants", []),
        "chapter_context_packets": state.get("chapter_context_packets", []),
        "revision_directives": state.get("revision_directives", []),
        "chapters": (state.get("artifacts") or {}).get("chapters", ""),
        "token_estimates": state.get("token_estimates", {}),
    }


@router.get("/{run_id}/worldbuilding")
async def get_run_worldbuilding(request: Request, run_id: str) -> dict[str, object]:
    state = run_state_or_404(request.app, run_id)
    return {"run_id": run_id, "worldbuilding": state.get("worldbuilding_state", {}), "story_bible": state.get("story_bible", {})}


@router.get("/{run_id}/wiki-state")
async def get_run_wiki_state(request: Request, run_id: str) -> dict[str, object]:
    state = run_state_or_404(request.app, run_id)
    return {
        "run_id": run_id,
        "wiki_state": state.get("wiki_state", {}),
        "wiki_refs": state.get("wiki_refs", []),
        "story_bible": state.get("story_bible", {}),
        "foreshadow_ledger": state.get("foreshadow_ledger", []),
    }


@router.get("/{run_id}/variants")
async def get_run_variants(request: Request, run_id: str) -> dict[str, object]:
    state = run_state_or_404(request.app, run_id)
    return {
        "run_id": run_id,
        "selected_variants": state.get("selected_variants", []),
        "chapter_drafts": state.get("chapter_drafts", []),
        "token_estimates": state.get("token_estimates", {}),
    }


@router.post("/{run_id}/events")
async def stream_run(request: Request, run_id: str, payload: RunRequest | None = None):
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    workflow = WorkflowDefinition.model_validate(stored["workflow"])
    inputs = payload.inputs if payload is not None and payload.inputs else stored.get("inputs", {})
    block = rag_blocking_issue(request.app, inputs)
    if block:
        raise HTTPException(status_code=409, detail=block)
    enrich_reference_summary(request.app, inputs)
    return stream_response(stream_runner_events(request.app, workflow, run_id, inputs))


@router.post("/{run_id}/pause")
async def pause_run(request: Request, run_id: str) -> dict[str, object]:
    try:
        request.app.state.run_store.request_pause(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    event = {"type": "run_pause_requested", "run_id": run_id}
    request.app.state.run_store.append_event(run_id, event)
    return {"ok": True, "run_id": run_id, "status": "pause_requested"}


@router.post("/{run_id}/resume")
async def resume_run(request: Request, run_id: str) -> dict[str, object]:
    try:
        request.app.state.run_store.resume(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    event = {"type": "run_resumed", "run_id": run_id}
    request.app.state.run_store.append_event(run_id, event)
    return {"ok": True, "run_id": run_id, "status": "resumed"}


@router.post("/{run_id}/approve-artifact")
async def approve_artifact(request: Request, run_id: str, payload: ArtifactApprovalRequest) -> dict[str, object]:
    try:
        approval = request.app.state.run_store.approve_artifact(run_id, node_id=payload.node_id, output_key=payload.output_key, artifact=payload.artifact)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    event = {
        "type": "artifact_approved",
        "run_id": run_id,
        "node_id": payload.node_id,
        "output_key": payload.output_key,
        "artifact": payload.artifact,
    }
    request.app.state.run_store.append_event(run_id, event)
    return {"ok": True, "run_id": run_id, "approval": approval}


@router.post("/{run_id}/regenerate-brief")
async def regenerate_brief(request: Request, run_id: str, payload: BriefRegenerateRequest) -> dict[str, object]:
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    workflow = WorkflowDefinition.model_validate(stored["workflow"])
    node = next((item for item in workflow.nodes if item.id == "info"), None)
    if node is None:
        raise HTTPException(status_code=409, detail="Workflow has no info stage")
    inputs = payload.inputs or stored.get("inputs", {})
    enrich_reference_summary(request.app, inputs)
    state = NovelRunState(run_id=run_id, project_id=str(inputs.get("project_id") or run_id), workflow_id=workflow.id, inputs=inputs)
    runner = NovelWorkflowRunner(
        providers=request.app.state.providers,
        wiki_store=request.app.state.wiki_store,
        run_store=request.app.state.run_store,
    )
    result, _ = await runner._execute_with_variants(node, state, workflow)
    event = {"type": "brief_regenerated", "run_id": run_id, "node_id": node.id, "output_key": node.output_key or node.id, "artifact": result}
    request.app.state.run_store.append_event(run_id, event)
    return {"ok": True, "run_id": run_id, "artifact": result, "events": inputs.get("rag_events", [])}


@router.post("/stream")
async def create_and_stream_run(request: Request, payload: RunRequest):
    try:
        workflow = WorkflowDefinition.model_validate(request.app.state.workflow_store.read(payload.workflow_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {payload.workflow_id}") from exc
    workflow.provider_profiles = [ProviderProfile.model_validate(item) for item in request.app.state.provider_store.list()]
    if payload.inputs.get("quality_mode") in {"fast", "balanced", "deep"}:
        workflow.quality_mode = payload.inputs["quality_mode"]
    block = rag_blocking_issue(request.app, payload.inputs)
    run_id = payload.run_id or str(uuid4())
    if block:
        request.app.state.run_store.create(run_id, workflow, payload.inputs)
        async def blocked_stream():
            event = {"type": "run_blocked", "run_id": run_id, "reason": block, "blocker": "knowledge_base_empty"}
            request.app.state.run_store.append_event(run_id, event)
            yield sse_payload(event)

        return stream_response(blocked_stream())
    enrich_reference_summary(request.app, payload.inputs)
    request.app.state.run_store.create(run_id, workflow, payload.inputs)
    return stream_response(stream_runner_events(request.app, workflow, run_id, payload.inputs))

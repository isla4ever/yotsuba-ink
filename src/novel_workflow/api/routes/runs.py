from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.api.bootstrap import list_provider_profiles
from novel_workflow.api.dependencies import run_state_or_404
from novel_workflow.api.sse import (
    RunStreamLeaseConflict,
    leased_stream_response,
    sse_payload,
    stream_response,
)
from novel_workflow.orchestration.draft_regeneration import DraftRegenerationError, regenerate_stage_drafts, select_stage_draft_candidate
from novel_workflow.orchestration.outline_artifact import outline_reference_errors
from novel_workflow.orchestration.detail_artifact import detail_reference_errors
from novel_workflow.orchestration.summary_artifact import summary_reference_errors
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.orchestration.chapter_review_model import chapter_review_errors
from novel_workflow.orchestration.recovery import prepare_checkpoint_recovery, recovery_required
from novel_workflow.providers.readiness import ProviderReadinessError, ensure_live_provider_readiness
from novel_workflow.references.context_injection import enrich_reference_summary, rag_blocking_issue
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import ArtifactApprovalRequest, BriefRegenerateRequest, DraftCandidateSelectRequest, DraftRegenerateRequest, NovelRunState, ProviderProfile, RunRequest, WorkflowDefinition
from novel_workflow.workflows.templates import materialize_workflow_for_execution


router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("")
async def create_run(request: Request, payload: RunRequest) -> dict[str, str]:
    try:
        workflow = WorkflowDefinition.model_validate(request.app.state.workflow_store.read(payload.workflow_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {payload.workflow_id}") from exc
    workflow.provider_profiles = list_provider_profiles(request.app)
    workflow = materialize_workflow_for_execution(workflow)
    run_id = payload.run_id or str(uuid4())
    project_id = payload.project_id or str(payload.inputs.get("project_id") or "") or run_id
    inputs = {**payload.inputs, "project_id": project_id}
    _ensure_live_execution(inputs)
    _ensure_provider_readiness(request, workflow)
    block = rag_blocking_issue(request.app, inputs)
    if block:
        raise HTTPException(status_code=409, detail=block)
    try:
        request.app.state.run_store.create(run_id, workflow, inputs, project_id=project_id)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"Run already exists: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request.app.state.project_store.touch_run(project_id, run_id)
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
        "budget_state": state.get("budget_state", {}),
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
        "budget_state": state.get("budget_state", {}),
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
    workflow = materialize_workflow_for_execution(workflow)
    inputs = payload.inputs if payload is not None and payload.inputs else stored.get("inputs", {})
    _ensure_live_execution(inputs)
    _ensure_provider_readiness(request, workflow)
    block = rag_blocking_issue(request.app, inputs)
    if block:
        raise HTTPException(status_code=409, detail=block)
    enrich_reference_summary(request.app, inputs)
    try:
        return leased_stream_response(request.app, workflow, run_id, inputs, emit_input_events=False)
    except RunStreamLeaseConflict as exc:
        raise HTTPException(status_code=409, detail="该运行已有执行流，请勿重复继续。") from exc


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
        stored = request.app.state.run_store.read(run_id)
        state_data = stored.get("state") or {}
        if state_data:
            state = NovelRunState.model_validate(state_data)
            if recovery_required(state) or state.runtime_phase == "checkpoint_recovery":
                try:
                    checkpoint = prepare_checkpoint_recovery(state)
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                request.app.state.run_store.resume(run_id)
                request.app.state.run_store.update_state(run_id, state)
                event = {
                    "type": "run_checkpoint_recovery_requested",
                    "run_id": run_id,
                    "checkpoint": checkpoint,
                    "recovery_state": state.recovery_state,
                    "message": "已解锁最后稳定检查点，继续创作将从该位置恢复。",
                }
                request.app.state.run_store.append_event(run_id, event)
                return {"ok": True, "run_id": run_id, "status": "checkpoint_recovery_requested", "checkpoint": checkpoint}
        request.app.state.run_store.resume(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    event = {"type": "run_resumed", "run_id": run_id}
    request.app.state.run_store.append_event(run_id, event)
    return {"ok": True, "run_id": run_id, "status": "resumed"}


@router.post("/{run_id}/advance")
async def advance_run(request: Request, run_id: str) -> dict[str, object]:
    raise HTTPException(status_code=410, detail="Demo advance has been removed. Use artifact approval or resume on live runs.")


@router.post("/{run_id}/replay-stage")
async def replay_run_stage(request: Request, run_id: str) -> dict[str, object]:
    raise HTTPException(status_code=410, detail="Demo replay has been removed. Regenerate the target artifact through the live provider.")


@router.post("/{run_id}/approve-artifact")
async def approve_artifact(request: Request, run_id: str, payload: ArtifactApprovalRequest) -> dict[str, object]:
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    workflow = WorkflowDefinition.model_validate(stored["workflow"])
    node = next((item for item in workflow.nodes if item.id == payload.node_id), None)
    if node is None:
        raise HTTPException(status_code=409, detail=f"Unknown stage: {payload.node_id}")
    validation = validate_stage_artifact(node.type, payload.artifact)
    if not validation.valid:
        raise HTTPException(status_code=409, detail="; ".join(validation.errors))
    if node.type == "summary":
        reference_errors = summary_reference_errors(NovelRunState.model_validate(stored.get("state") or {}), validation.artifact)
        if reference_errors:
            raise HTTPException(status_code=409, detail="; ".join(reference_errors))
    elif node.type == "outline":
        reference_errors = outline_reference_errors(NovelRunState.model_validate(stored.get("state") or {}), validation.artifact)
        if reference_errors:
            raise HTTPException(status_code=409, detail="; ".join(reference_errors))
    elif node.type == "detail_outline":
        reference_errors = detail_reference_errors(NovelRunState.model_validate(stored.get("state") or {}), validation.artifact)
        if reference_errors:
            raise HTTPException(status_code=409, detail="; ".join(reference_errors))
    elif node.type == "chapter_text":
        review_errors = chapter_review_errors(validation.artifact)
        if review_errors:
            raise HTTPException(status_code=409, detail="; ".join(review_errors))
    try:
        approval = request.app.state.run_store.approve_artifact(
            run_id,
            node_id=payload.node_id,
            output_key=payload.output_key,
            artifact=validation.artifact,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    event = {
        "type": "artifact_approved",
        "run_id": run_id,
        "node_id": payload.node_id,
        "output_key": payload.output_key,
        "artifact": validation.artifact,
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
    event = {"type": "brief_regenerated", "run_id": run_id, "node_id": node.id, "output_key": node.output_key or node.id, "artifact": result, "artifact_source": "live"}
    request.app.state.run_store.append_event(run_id, event)
    return {"ok": True, "run_id": run_id, "artifact": result, "events": inputs.get("rag_events", [])}


@router.post("/{run_id}/regenerate-draft")
async def regenerate_draft(request: Request, run_id: str, payload: DraftRegenerateRequest) -> dict[str, object]:
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    workflow = WorkflowDefinition.model_validate(stored["workflow"])
    workflow.provider_profiles = list_provider_profiles(request.app)
    workflow = materialize_workflow_for_execution(workflow)
    _ensure_provider_readiness(request, workflow)
    runner = NovelWorkflowRunner(
        providers=request.app.state.providers,
        wiki_store=request.app.state.wiki_store,
        run_store=request.app.state.run_store,
    )
    try:
        events = await regenerate_stage_drafts(
            runner,
            workflow,
            run_id=run_id,
            node_id=payload.node_id,
            direction=payload.direction,
            candidate_count=payload.candidate_count,
            request_id=payload.request_id,
        )
    except DraftRegenerationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, "events": events}


@router.post("/{run_id}/select-draft-candidate")
async def select_draft_candidate(request: Request, run_id: str, payload: DraftCandidateSelectRequest) -> dict[str, object]:
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    workflow = WorkflowDefinition.model_validate(stored["workflow"])
    workflow.provider_profiles = list_provider_profiles(request.app)
    workflow = materialize_workflow_for_execution(workflow)
    runner = NovelWorkflowRunner(
        providers=request.app.state.providers,
        wiki_store=request.app.state.wiki_store,
        run_store=request.app.state.run_store,
    )
    try:
        event = select_stage_draft_candidate(
            runner,
            workflow,
            run_id=run_id,
            node_id=payload.node_id,
            section=payload.section,
        )
    except DraftRegenerationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, "event": event}


@router.post("/stream")
async def create_and_stream_run(request: Request, payload: RunRequest):
    try:
        workflow = WorkflowDefinition.model_validate(request.app.state.workflow_store.read(payload.workflow_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {payload.workflow_id}") from exc
    workflow.provider_profiles = [ProviderProfile.model_validate(item) for item in request.app.state.provider_store.list()]
    run_id = payload.run_id or str(uuid4())
    project_id = payload.project_id or str(payload.inputs.get("project_id") or "") or run_id
    merged_inputs = {**payload.inputs, "project_id": project_id}
    _ensure_live_execution(merged_inputs)
    workflow = materialize_workflow_for_execution(workflow)
    if merged_inputs.get("quality_mode") in {"fast", "balanced", "deep"}:
        workflow.quality_mode = merged_inputs["quality_mode"]
    _ensure_provider_readiness(request, workflow)
    block = rag_blocking_issue(request.app, merged_inputs)
    if block:
        try:
            request.app.state.run_store.create(run_id, workflow, merged_inputs, project_id=project_id)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=f"Run already exists: {run_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        request.app.state.project_store.touch_run(project_id, run_id)
        async def blocked_stream():
            event = {"type": "run_blocked", "run_id": run_id, "reason": block, "blocker": "knowledge_base_empty"}
            request.app.state.run_store.append_event(run_id, event)
            yield sse_payload(event)

        return stream_response(blocked_stream())
    enrich_reference_summary(request.app, merged_inputs)
    try:
        request.app.state.run_store.create(run_id, workflow, merged_inputs, project_id=project_id)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"Run already exists: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request.app.state.project_store.touch_run(project_id, run_id)
    try:
        return leased_stream_response(request.app, workflow, run_id, merged_inputs)
    except RunStreamLeaseConflict as exc:
        raise HTTPException(status_code=409, detail="该运行已有执行流，请勿重复继续。") from exc


def _ensure_provider_readiness(request: Request, workflow: WorkflowDefinition) -> None:
    try:
        ensure_live_provider_readiness(
            workflow,
            secret_resolver=request.app.state.provider_secret_store.get_api_key,
        )
    except ProviderReadinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _ensure_live_execution(inputs: dict[str, object]) -> None:
    if inputs.get("execution_mode", "live") == "demo":
        raise HTTPException(status_code=410, detail="Demo/mock execution has been removed. Please run with execution_mode='live'.")

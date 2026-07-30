from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any


async def pause_if_requested(
    runner: Any,
    run_id: str,
    state: Any,
    *,
    node_id: str = "",
    chapter: str = "",
) -> AsyncIterator[dict[str, Any]]:
    if not runner.run_store.pause_requested(run_id):
        return
    requested = {"type": "run_pause_requested", "run_id": run_id, "node_id": node_id, "chapter": chapter}
    paused = {"type": "run_paused", "run_id": run_id, "node_id": node_id, "chapter": chapter}
    runner.run_store.append_event(run_id, requested)
    runner.run_store.mark_paused(run_id, True)
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, paused)
    yield requested
    yield paused
    while runner.run_store.read(run_id).get("paused"):
        await asyncio.sleep(0.2)
    resumed = {"type": "run_resumed", "run_id": run_id, "node_id": node_id, "chapter": chapter}
    runner.run_store.append_event(run_id, resumed)
    yield resumed


async def wait_for_artifact_approval(
    runner: Any,
    run_id: str,
    state: Any,
    *,
    node_id: str,
    output_key: str,
    artifact: Any,
) -> AsyncIterator[dict[str, Any]]:
    runner.run_store.request_approval(run_id, node_id=node_id, output_key=output_key, artifact=artifact)
    event = {
        "type": "approval_required",
        "run_id": run_id,
        "node_id": node_id,
        "output_key": output_key,
        "artifact": artifact,
        "message": "创作立项定稿需要人工确认。确认后才会进入自动梗概、大纲、细纲和正文流水线。",
    }
    runner.run_store.append_event(run_id, event)
    yield event
    while runner.run_store.approval_pending(run_id, node_id=node_id):
        await asyncio.sleep(0.2)
    stored = runner.run_store.read(run_id)
    approval = stored.get("approval") or {}
    approved_artifact = approval.get("artifact", artifact)
    state.approval_required = False
    state.artifacts[output_key] = approved_artifact
    state.approved_artifacts[output_key] = approved_artifact
    state.story_brief = {"source": "approved_artifact", "content": approved_artifact}
    approved_event = {
        "type": "artifact_approved",
        "run_id": run_id,
        "node_id": node_id,
        "output_key": output_key,
        "artifact": approved_artifact,
    }
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, approved_event)
    yield approved_event


def should_wait_for_stage_confirmation(mode: str, node_id: str, node_type: str) -> bool:
    if mode == "fast":
        return False
    if mode == "balanced":
        return node_type == "info_recommend"
    if mode == "deep":
        return node_id != "export"
    return node_type == "info_recommend"


async def wait_for_stage_confirmation(
    runner: Any,
    run_id: str,
    state: Any,
    *,
    node_id: str,
    node_type: str,
    label: str,
    output_key: str,
    artifact: Any,
    next_node_id: str = "",
) -> AsyncIterator[dict[str, Any]]:
    state.runtime_phase = "awaiting_stage_confirmation"
    state.approval_required = True
    state.current_checkpoint_stage_id = node_id
    state.stage_confirmation_state[node_id] = {
        "status": "pending",
        "node_id": node_id,
        "node_type": node_type,
        "output_key": output_key,
    }
    runner.run_store.update_state(run_id, state)
    runner.run_store.request_approval(run_id, node_id=node_id, output_key=output_key, artifact=artifact)
    checkpoint = {
        "type": "stage_checkpoint_ready",
        "run_id": run_id,
        "node_id": node_id,
        "node_type": node_type,
        "label": label,
        "output_key": output_key,
        "artifact": artifact,
        "next_node_id": next_node_id,
        "message": "当前阶段产物已生成，等待人工确认定稿。",
    }
    approval = {
        "type": "approval_required",
        "run_id": run_id,
        "node_id": node_id,
        "node_type": node_type,
        "label": label,
        "output_key": output_key,
        "artifact": artifact,
        "message": "当前阶段需要人工确认后才能继续。",
    }
    for event in (checkpoint, approval):
        runner.run_store.append_event(run_id, event)
        yield event
    while runner.run_store.approval_pending(run_id, node_id=node_id):
        await asyncio.sleep(0.2)
    stored = runner.run_store.read(run_id)
    approval_data = stored.get("approval") or {}
    approved_artifact = approval_data.get("artifact", artifact)
    state.runtime_phase = "stage_ready_to_continue"
    state.approval_required = False
    state.artifacts[output_key] = approved_artifact
    state.approved_artifacts[output_key] = approved_artifact
    state.stage_confirmation_state[node_id] = {
        "status": "confirmed",
        "node_id": node_id,
        "node_type": node_type,
        "output_key": output_key,
        "event_emitted": True,
    }
    confirmed = {
        "type": "stage_artifact_confirmed",
        "run_id": run_id,
        "node_id": node_id,
        "node_type": node_type,
        "label": label,
        "output_key": output_key,
        "artifact": approved_artifact,
    }
    approved = {"type": "artifact_approved", **{key: value for key, value in confirmed.items() if key != "type"}}
    runner.run_store.update_state(run_id, state)
    for event in (confirmed, approved):
        runner.run_store.append_event(run_id, event)
        yield event

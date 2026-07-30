from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from novel_workflow.orchestration.cover_assets import generate_cover_assets
from novel_workflow.orchestration.helpers import node_with_mode_policy
from novel_workflow.orchestration.variants import (
    drain_deferred_provider_events,
    execute_with_variants,
)
from novel_workflow.output_contracts import validate_stage_artifact


@dataclass(slots=True)
class ParallelDeliveryHandle:
    queue: asyncio.Queue[dict[str, Any]]
    task: asyncio.Task[None]


def start_parallel_cover_delivery(
    runner: Any,
    workflow: Any,
    state: Any,
    run_id: str,
    ordered_nodes: list[Any],
) -> ParallelDeliveryHandle | None:
    cover_node = next((item for item in ordered_nodes if item.type == "cover_image"), None)
    text_node = next((item for item in ordered_nodes if item.type == "chapter_text"), None)
    if cover_node is None or text_node is None:
        return None
    current = state.parallel_delivery_state if isinstance(state.parallel_delivery_state, dict) else {}
    artifact = state.artifacts.get(cover_node.output_key or cover_node.id)
    generation = artifact.get("asset_generation") if isinstance(artifact, dict) else None
    if current.get("status") in {"running", "ready"} or (
        isinstance(generation, dict) and generation.get("status") == "ready"
    ):
        return None
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    node = node_with_mode_policy(cover_node, workflow, state)
    task = asyncio.create_task(
        _run_parallel_cover_delivery(runner, workflow, state, run_id, node, queue),
        name=f"parallel-cover-{run_id}",
    )
    return ParallelDeliveryHandle(queue=queue, task=task)


async def merge_with_parallel_delivery(
    primary: AsyncIterator[dict[str, Any]],
    handle: ParallelDeliveryHandle,
) -> AsyncIterator[dict[str, Any]]:
    primary_task = asyncio.create_task(_pump_primary(primary, handle.queue))
    primary_done = False
    parallel_done = False
    try:
        while not (primary_done and parallel_done and handle.queue.empty()):
            get_task = asyncio.create_task(handle.queue.get())
            waiters: set[asyncio.Task[Any]] = {get_task}
            if not primary_done:
                waiters.add(primary_task)
            if not parallel_done:
                waiters.add(handle.task)
            completed, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
            if get_task in completed:
                yield get_task.result()
            else:
                get_task.cancel()
                with suppress(asyncio.CancelledError):
                    await get_task
            if primary_task in completed:
                await primary_task
                primary_done = True
            if handle.task in completed:
                await handle.task
                parallel_done = True
    finally:
        for task in (primary_task, handle.task):
            if not task.done():
                task.cancel()
        for task in (primary_task, handle.task):
            with suppress(asyncio.CancelledError):
                await task


async def finish_parallel_delivery(
    handle: ParallelDeliveryHandle,
) -> AsyncIterator[dict[str, Any]]:
    await handle.task
    while not handle.queue.empty():
        yield handle.queue.get_nowait()


async def _pump_primary(
    primary: AsyncIterator[dict[str, Any]],
    queue: asyncio.Queue[dict[str, Any]],
) -> None:
    async for event in primary:
        await queue.put(event)


async def _run_parallel_cover_delivery(
    runner: Any,
    workflow: Any,
    state: Any,
    run_id: str,
    node: Any,
    queue: asyncio.Queue[dict[str, Any]],
) -> None:
    state.parallel_delivery_state = {
        "status": "running",
        "unlocked_after": "detail",
        "tracks": ["cover", "export_preview"],
    }
    await _commit_and_queue(runner, state, queue, {
        "type": "parallel_delivery_started",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "source_stage_id": "detail",
        "tracks": ["cover", "export_preview"],
        "message": "章节细纲已定稿，封面资产与导出准备开始并行推进。",
    })
    try:
        output_key = node.output_key or node.id
        existing = state.artifacts.get(output_key)
        plan = None
        if not isinstance(existing, dict) or not existing.get("candidates"):
            plan, variant_events = await execute_with_variants(runner, node, state, workflow)
            for event in variant_events:
                await _commit_and_queue(runner, state, queue, {"run_id": run_id, **event})
            validation = validate_stage_artifact(node.type, plan)
            if not validation.valid:
                raise ValueError("; ".join(validation.errors))
            plan = validation.artifact
        async for event in generate_cover_assets(
            runner,
            node,
            state,
            workflow,
            run_id,
            plan=plan,
        ):
            await queue.put(event)
        for event in drain_deferred_provider_events(state):
            await _commit_and_queue(runner, state, queue, event)
        generation = (state.artifacts.get(output_key) or {}).get("asset_generation") or {}
        state.parallel_delivery_state = {
            "status": "ready",
            "unlocked_after": "detail",
            "tracks": ["cover", "export_preview"],
            "ready_count": int(generation.get("ready_count") or 0),
            "total": int(generation.get("total") or 0),
        }
        state.progress[node.id] = {"status": "parallel_ready", **state.parallel_delivery_state}
        await _commit_and_queue(runner, state, queue, {
            "type": "parallel_delivery_ready",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "tracks": ["cover", "export_preview"],
            "parallel_delivery": dict(state.parallel_delivery_state),
            "message": "封面候选已准备，可在正文创作期间完成选择与交付设置。",
        })
    except asyncio.CancelledError:
        state.parallel_delivery_state = {
            "status": "cancelled",
            "unlocked_after": "detail",
            "tracks": ["cover", "export_preview"],
        }
        runner.run_store.update_state(run_id, state)
        raise
    except Exception as exc:
        for event in drain_deferred_provider_events(state):
            await _commit_and_queue(runner, state, queue, event)
        state.parallel_delivery_state = {
            "status": "degraded",
            "unlocked_after": "detail",
            "tracks": ["cover", "export_preview"],
            "message": str(exc),
        }
        state.progress[node.id] = {"status": "parallel_degraded", "message": str(exc)}
        await _commit_and_queue(runner, state, queue, {
            "type": "parallel_delivery_degraded",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "tracks": ["cover", "export_preview"],
            "parallel_delivery": dict(state.parallel_delivery_state),
            "message": "封面并行任务暂未完成，正文继续推进；进入封面工作台后可重试。",
        })


async def _commit_and_queue(
    runner: Any,
    state: Any,
    queue: asyncio.Queue[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    runner.run_store.commit_state_event(state.run_id, state, event)
    await queue.put(event)

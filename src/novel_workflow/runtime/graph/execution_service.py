from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from novel_workflow.runtime.graph.provider_gateway import NarrativeProviderGateway
from novel_workflow.runtime.graph.checkpoint_branch import CheckpointBranchMode
from novel_workflow.runtime.graph.runtime import (
    filesystem_stores,
    has_active_graph_interrupt,
    open_sqlite_runtime,
)


class RunExecutionConflict(RuntimeError):
    pass


class NarrativeExecutionService:
    """Owns graph tasks independently from HTTP/SSE observer lifetimes."""

    def __init__(
        self,
        root: Path,
        provider_factory: Callable[[], NarrativeProviderGateway],
    ) -> None:
        self.root = root
        self.provider_factory = provider_factory
        self.stores = filesystem_stores(root)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._collaboration_tasks: dict[str, asyncio.Task[None]] = {}

    def dispatch_start(self, run_id: str) -> None:
        self._dispatch(run_id, self._start(run_id))

    def dispatch_resume(self, run_id: str, decision: dict[str, Any]) -> None:
        self._dispatch(run_id, self._resume(run_id, decision))

    def dispatch_recover(self, run_id: str) -> None:
        self._dispatch(run_id, self._recover(run_id))

    def dispatch_collaboration_turn(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
    ) -> None:
        key = self._collaboration_key(thread_id, turn_id)
        task = self._collaboration_tasks.get(key)
        if task is not None and not task.done():
            raise RunExecutionConflict(key)
        created = asyncio.create_task(
            self._execute_collaboration(run_id, thread_id, turn_id),
            name=f"author-collaboration:{thread_id}:{turn_id}",
        )
        self._collaboration_tasks[key] = created
        created.add_done_callback(
            lambda completed, task_key=key: self._release_collaboration_task(
                task_key,
                completed,
            )
        )

    def cancel_collaboration_turn(self, thread_id: str, turn_id: str) -> bool:
        task = self._collaboration_tasks.get(self._collaboration_key(thread_id, turn_id))
        if task is None or task.done():
            return False
        task.cancel()
        return True

    def is_collaboration_running(self, thread_id: str, turn_id: str) -> bool:
        task = self._collaboration_tasks.get(self._collaboration_key(thread_id, turn_id))
        return task is not None and not task.done()

    async def recover_incomplete(self) -> None:
        projections = self.stores.runs.list()
        for projection in projections:
            self._recover_collaboration_turns(projection.run_id)
        for projection in projections:
            if projection.status in {"completed", "cancelled", "failed"}:
                continue
            async with open_sqlite_runtime(self.root, self.provider_factory()) as runtime:
                snapshot = await runtime.graph.aget_state(
                    {"configurable": {"thread_id": projection.run_id}},
                    subgraphs=True,
                )
            if snapshot.values and snapshot.next and not has_active_graph_interrupt(snapshot):
                self.dispatch_recover(projection.run_id)

    def _recover_collaboration_turns(self, run_id: str) -> None:
        for thread in self.stores.collaboration.list_threads(run_id):
            for turn in self.stores.collaboration.list_turns(run_id, thread.thread_id):
                if turn.status == "queued":
                    self.dispatch_collaboration_turn(run_id, thread.thread_id, turn.turn_id)
                    continue
                if turn.status != "streaming":
                    continue
                receipt = self.stores.operations.find(
                    run_id,
                    turn.provider_operation_ref,
                ) if turn.provider_operation_ref else None
                if receipt is not None and receipt.status in {"provider_returned", "succeeded"}:
                    self.dispatch_collaboration_turn(run_id, thread.thread_id, turn.turn_id)
                    continue
                if receipt is not None and receipt.status == "contract_rejected":
                    self._finish_interrupted_collaboration(
                        run_id,
                        thread.thread_id,
                        turn.turn_id,
                        status="contract_rejected",
                        code="collaboration_contract_invalid",
                        message="Provider returned content that did not satisfy the collaboration contract",
                    )
                    continue
                if receipt is not None and receipt.status == "cancelled":
                    self._finish_interrupted_collaboration(
                        run_id,
                        thread.thread_id,
                        turn.turn_id,
                        status="cancelled",
                        code="cancelled",
                        message="Collaboration turn was cancelled before the service restarted",
                    )
                    continue
                if receipt is not None and receipt.status == "failed":
                    error = receipt.error or {}
                    self._finish_interrupted_collaboration(
                        run_id,
                        thread.thread_id,
                        turn.turn_id,
                        status="failed",
                        code=str(error.get("code") or "provider_failed"),
                        message=str(error.get("message") or "Collaboration Provider failed before restart"),
                    )
                    continue
                error = {
                    "code": "provider_outcome_unknown",
                    "message": "The service restarted before the Provider outcome was durably recorded",
                }
                if receipt is not None and receipt.status == "pending":
                    self.stores.operations.fail(run_id, receipt.operation_key, error)
                self._finish_interrupted_collaboration(
                    run_id,
                    thread.thread_id,
                    turn.turn_id,
                    status="failed",
                    **error,
                )

    async def wait(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task is not None:
            await task

    def is_running(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    async def create_branch(
        self,
        *,
        source_run_id: str,
        target_run_id: str,
        checkpoint_id: str,
        provider_binding_overrides=None,
        cover_asset_binding_override=None,
        binding_override=None,
        branch_mode: CheckpointBranchMode = "active_decision",
    ):
        if self.is_running(source_run_id) or self.is_running(target_run_id):
            raise RunExecutionConflict(source_run_id)
        from novel_workflow.runtime.graph.branch_service import NarrativeBranchService

        async with open_sqlite_runtime(self.root, self.provider_factory()) as runtime:
            projection = await NarrativeBranchService(runtime).create(
                source_run_id=source_run_id,
                target_run_id=target_run_id,
                checkpoint_id=checkpoint_id,
                provider_binding_overrides=provider_binding_overrides,
                cover_asset_binding_override=cover_asset_binding_override,
                binding_override=binding_override,
                branch_mode=branch_mode,
            )
        if branch_mode == "stage_boundary":
            self.dispatch_recover(target_run_id)
        return projection

    def _dispatch(self, run_id: str, coroutine: Any) -> None:
        if self.is_running(run_id):
            coroutine.close()
            raise RunExecutionConflict(run_id)
        self._tasks[run_id] = asyncio.create_task(coroutine, name=f"narrative-run:{run_id}")

    async def _start(self, run_id: str) -> None:
        await self._execute(run_id, mode="start")

    async def _resume(self, run_id: str, decision: dict[str, Any]) -> None:
        await self._execute(run_id, mode="resume", decision=decision)

    async def _recover(self, run_id: str) -> None:
        await self._execute(run_id, mode="recover")

    async def _execute(
        self,
        run_id: str,
        *,
        mode: str,
        decision: dict[str, Any] | None = None,
    ) -> None:
        try:
            async with open_sqlite_runtime(self.root, self.provider_factory()) as runtime:
                if mode == "start":
                    await runtime.start(run_id)
                elif mode == "recover":
                    await runtime.recover(run_id)
                else:
                    await runtime.resume(run_id, decision or {})
        except Exception as exc:
            self.stores.events.append(
                run_id,
                event_id=f"{run_id}:execution-failed:{type(exc).__name__}",
                type="run.failed",
                node_id="execution_service",
                status="failed",
                payload={"code": type(exc).__name__, "message": str(exc)},
            )
            current = self.stores.runs.read(run_id)
            self.stores.runs.project(
                run_id,
                current.model_copy(
                    update={
                        "status": "failed",
                        "failure": {
                            "node_id": "execution_service",
                            "code": type(exc).__name__,
                            "retryable": False,
                        },
                    }
                ),
            )

    async def _execute_collaboration(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
    ) -> None:
        try:
            async with open_sqlite_runtime(self.root, self.provider_factory()) as runtime:
                await runtime.collaborate(run_id, thread_id, turn_id)
        except asyncio.CancelledError:
            turn = self.stores.collaboration.read_turn(run_id, thread_id, turn_id)
            operation_key = turn.provider_operation_ref
            if operation_key:
                receipt = self.stores.operations.find(run_id, operation_key)
                if receipt is not None and receipt.status == "pending":
                    self.stores.operations.cancel(run_id, operation_key)
            if turn.status in {"queued", "streaming"}:
                self.stores.collaboration.transition_turn(
                    run_id,
                    thread_id,
                    turn_id,
                    "cancelled",
                    error={"code": "cancelled", "message": "Cancelled by the author"},
                )
                self.stores.collaboration.append_event(
                    run_id,
                    thread_id,
                    "turn.cancelled",
                    turn_id=turn_id,
                    payload={"code": "cancelled"},
                )
                thread = self.stores.collaboration.read_thread(run_id, thread_id)
                self.stores.events.append(
                    run_id,
                    event_id=f"{turn_id}:cancelled",
                    type="collaboration.turn_cancelled",
                    stage_id=thread.stage_id,
                    node_id="author_collaboration",
                    status="cancelled",
                    payload={"thread_id": thread_id, "turn_id": turn_id},
                )
            raise
        except Exception as exc:
            turn = self.stores.collaboration.read_turn(run_id, thread_id, turn_id)
            if turn.status in {"queued", "streaming"}:
                self._finish_interrupted_collaboration(
                    run_id,
                    thread_id,
                    turn_id,
                    status="failed",
                    code=type(exc).__name__,
                    message=str(exc),
                )

    def _finish_interrupted_collaboration(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
        *,
        status: str,
        code: str,
        message: str,
    ) -> None:
        turn = self.stores.collaboration.transition_turn(
            run_id,
            thread_id,
            turn_id,
            status,
            error={"code": code, "message": message},
        )
        stream_type = "turn.cancelled" if status == "cancelled" else "turn.failed"
        run_type = "collaboration.turn_cancelled" if status == "cancelled" else "collaboration.turn_failed"
        self.stores.collaboration.append_event(
            run_id,
            thread_id,
            stream_type,
            turn_id=turn_id,
            payload={"code": code},
        )
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        self.stores.events.append(
            run_id,
            event_id=f"{turn_id}:{turn.status}",
            type=run_type,
            stage_id=thread.stage_id,
            node_id="author_collaboration",
            status=turn.status,
            payload={"thread_id": thread_id, "turn_id": turn_id, "code": code},
        )

    def _release_collaboration_task(
        self,
        key: str,
        task: asyncio.Task[None],
    ) -> None:
        if self._collaboration_tasks.get(key) is task:
            self._collaboration_tasks.pop(key, None)
        if task.cancelled():
            return
        task.exception()

    @staticmethod
    def _collaboration_key(thread_id: str, turn_id: str) -> str:
        return f"{thread_id}:{turn_id}"


__all__ = ["NarrativeExecutionService", "RunExecutionConflict"]

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

    def dispatch_start(self, run_id: str) -> None:
        self._dispatch(run_id, self._start(run_id))

    def dispatch_resume(self, run_id: str, decision: dict[str, Any]) -> None:
        self._dispatch(run_id, self._resume(run_id, decision))

    def dispatch_recover(self, run_id: str) -> None:
        self._dispatch(run_id, self._recover(run_id))

    async def recover_incomplete(self) -> None:
        for projection in self.stores.runs.list():
            if projection.status in {"completed", "cancelled", "failed"}:
                continue
            async with open_sqlite_runtime(self.root, self.provider_factory()) as runtime:
                snapshot = await runtime.graph.aget_state(
                    {"configurable": {"thread_id": projection.run_id}},
                    subgraphs=True,
                )
            if snapshot.values and snapshot.next and not has_active_graph_interrupt(snapshot):
                self.dispatch_recover(projection.run_id)

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


__all__ = ["NarrativeExecutionService", "RunExecutionConflict"]

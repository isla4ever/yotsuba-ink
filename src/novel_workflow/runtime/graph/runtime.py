from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from novel_workflow.runtime.graph.narrative_graph import build_narrative_graph
from novel_workflow.runtime.graph.provider_gateway import NarrativeProviderGateway
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.artifact_store import ArtifactStore
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.cover_asset_store import CoverAssetStore
from novel_workflow.storage.event_projection import EventProjection
from novel_workflow.storage.evidence_store import EvidenceStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.memory.canon_store import CanonStore
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.storage.domain_outbox import DomainOutbox
from novel_workflow.storage.narrative_run_repository import (
    NarrativeRunRepository,
    RunReadModel,
)
from novel_workflow.storage.operation_store import OperationStore


class DecisionReplayConflict(ValueError):
    """A decision command conflicts with the graph's persisted authority."""


@dataclass(frozen=True, slots=True)
class NarrativeRuntimeStores:
    runs: NarrativeRunRepository
    artifacts: ArtifactStore
    chapters: ChapterStore
    evidence: EvidenceStore
    exports: ExportStore
    cover_assets: CoverAssetStore
    canon: CanonStore
    wiki: WikiProjectionStore
    outbox: DomainOutbox
    operations: OperationStore
    events: EventProjection


@dataclass(slots=True)
class NarrativeRuntime:
    """The only production execution entry point for a narrative Run."""

    stores: NarrativeRuntimeStores
    provider: NarrativeProviderGateway
    checkpointer: Any
    graph: Any

    @classmethod
    def create(
        cls,
        stores: NarrativeRuntimeStores,
        provider: NarrativeProviderGateway,
        *,
        checkpointer: Any,
    ) -> "NarrativeRuntime":
        executor = StageExecutor(
            runs=stores.runs,
            artifacts=stores.artifacts,
            chapters=stores.chapters,
            operations=stores.operations,
            events=stores.events,
            evidence=stores.evidence,
            exports=stores.exports,
            cover_assets=stores.cover_assets,
            outbox=stores.outbox,
            provider=provider,
        )
        return cls(
            stores=stores,
            provider=provider,
            checkpointer=checkpointer,
            graph=build_narrative_graph(executor, checkpointer=checkpointer),
        )

    async def start(self, run_id: str) -> RunReadModel:
        await self._execute(run_id, {"run_id": run_id})
        return self.stores.runs.read(run_id)

    async def resume(self, run_id: str, decision: dict[str, Any]) -> RunReadModel:
        command = dict(decision)
        receipt_signature = str(command.pop("_receipt_signature", "")) or decision_signature(command)
        decision_id = str(command.get("decision_id") or "")
        action = str(command.get("action") or "")
        if not decision_id or not action:
            raise DecisionReplayConflict("Decision id and action are required")
        operation_key = decision_operation_key(decision_id)
        try:
            receipt = self.stores.operations.begin(
                run_id=run_id,
                operation_key=operation_key,
                kind="graph_decision",
                request_signature=receipt_signature,
            )
        except ValueError as exc:
            raise DecisionReplayConflict(
                "Decision was already submitted with different command data"
            ) from exc

        if receipt.status == "succeeded":
            await self._project(run_id)
            return self.stores.runs.read(run_id)

        snapshot = await self.graph.aget_state(self._config(run_id), subgraphs=True)
        pending = [item.value for item in snapshot.interrupts]
        active = next(
            (
                item
                for item in pending
                if isinstance(item, dict) and item.get("decision_id") == decision_id
            ),
            None,
        )
        if active is None:
            if receipt.status == "pending":
                self.stores.operations.succeed(
                    run_id,
                    operation_key,
                    {"decision_id": decision_id, "action": action},
                )
                await self._project(run_id)
                return self.stores.runs.read(run_id)
            raise DecisionReplayConflict("Decision is not pending on this Run")
        if int(command.get("domain_revision", -1)) != int(
            active.get("domain_revision", -2)
        ):
            raise DecisionReplayConflict("Decision domain revision is stale")
        if action not in (active.get("allowed_actions") or []):
            raise DecisionReplayConflict("Decision action is not allowed")

        await self._execute(run_id, Command(resume=command))
        next_snapshot = await self.graph.aget_state(self._config(run_id), subgraphs=True)
        if _decision_is_pending(next_snapshot, decision_id):
            raise DecisionReplayConflict("Decision did not reach a resolved graph state")
        self.stores.operations.succeed(
            run_id,
            operation_key,
            {"decision_id": decision_id, "action": action},
        )
        return self.stores.runs.read(run_id)

    async def recover(self, run_id: str) -> RunReadModel:
        """Continue the latest failed super-step from its durable checkpoint."""
        snapshot = await self.graph.aget_state(self._config(run_id))
        if snapshot.interrupts:
            await self._project(run_id)
            return self.stores.runs.read(run_id)
        await self._execute(run_id, None)
        return self.stores.runs.read(run_id)

    async def state(self, run_id: str) -> NarrativeRunState:
        snapshot = await self.graph.aget_state(self._config(run_id))
        return dict(snapshot.values)

    async def refresh_projection(self, run_id: str) -> RunReadModel:
        await self._project(run_id)
        return self.stores.runs.read(run_id)

    async def _execute(self, run_id: str, input_value: Any) -> None:
        try:
            async for mode, chunk in self.graph.astream(
                input_value,
                config=self._config(run_id),
                stream_mode=["updates", "checkpoints"],
            ):
                if mode == "checkpoints":
                    self._record_checkpoint(run_id, chunk)
        except Exception as exc:
            # The graph owns execution. Persist a terminal domain projection
            # here so an HTTP/SSE observer can reconnect without owning task
            # lifetime or guessing whether an exception was recoverable.
            current = self.stores.runs.read(run_id)
            failure = {
                "node_id": "graph",
                "code": type(exc).__name__,
                "retryable": False,
                "message": str(exc),
            }
            self.stores.events.append(
                run_id,
                event_id=f"{run_id}:graph-failed:{type(exc).__name__}",
                type="run.failed",
                stage_id=current.active_stage_id,
                node_id="graph",
                status="failed",
                payload=failure,
            )
            self.stores.runs.project(
                run_id,
                current.model_copy(update={"status": "failed", "failure": failure}),
            )
            return
        await self._project(run_id)

    def _record_checkpoint(self, run_id: str, chunk: Any) -> None:
        if not isinstance(chunk, dict):
            return
        configurable = chunk.get("config", {}).get("configurable", {})
        checkpoint_id = str(configurable.get("checkpoint_id") or "")
        if not checkpoint_id:
            return
        values = chunk.get("values") if isinstance(chunk.get("values"), dict) else {}
        stage_id = str(values.get("active_stage_id") or "info")
        self.stores.events.append(
            run_id,
            event_id=f"checkpoint:{checkpoint_id}",
            type="checkpoint.saved",
            stage_id=stage_id,
            node_id="graph.checkpoint",
            status="saved",
            payload={"next": list(chunk.get("next") or [])},
            checkpoint_id=checkpoint_id,
        )

    async def _project(self, run_id: str) -> None:
        snapshot = await self.graph.aget_state(self._config(run_id))
        values = dict(snapshot.values or {})
        stage_status = dict(values.get("stage_status") or {})
        pending = [item.value for item in snapshot.interrupts]
        active_stage = str(values.get("active_stage_id") or "info")
        status = str(values.get("status") or "running")
        if pending:
            status = "awaiting_decision"
            node_id = str(pending[0].get("node_id") or "") if isinstance(pending[0], dict) else ""
            interrupted_stage = node_id.partition(".")[0]
            if interrupted_stage in stage_status:
                active_stage = interrupted_stage
            if active_stage in stage_status:
                stage_status[active_stage] = "awaiting_decision"
        definition = self.stores.runs.definition(run_id)
        projection = RunReadModel(
            run_id=run_id,
            project_id=str(values.get("project_id") or definition.project_id),
            thread_id=run_id,
            status=status,  # type: ignore[arg-type]
            active_stage_id=active_stage,  # type: ignore[arg-type]
            active_chapter_number=int(values.get("active_chapter_number") or 0),
            stage_status=stage_status,
            artifact_refs=dict(values.get("artifact_refs") or {}),
            pending_decisions=pending,
            provider_usage=self.stores.operations.usage_summary(run_id),
            failure=values.get("failure"),
            checkpoint_id=str(snapshot.config.get("configurable", {}).get("checkpoint_id") or ""),
            updated_at="",
        )
        self.stores.runs.project(run_id, projection)

    @staticmethod
    def _config(run_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": run_id}}


def filesystem_stores(root: Path) -> NarrativeRuntimeStores:
    canon = CanonStore(root / "canon")
    wiki = WikiProjectionStore(root / "wiki")
    return NarrativeRuntimeStores(
        runs=NarrativeRunRepository(root / "runs"),
        artifacts=ArtifactStore(root / "artifacts"),
        chapters=ChapterStore(root / "chapters"),
        evidence=EvidenceStore(root / "evidence"),
        exports=ExportStore(root / "exports"),
        cover_assets=CoverAssetStore(root / "cover_assets"),
        canon=canon,
        wiki=wiki,
        outbox=DomainOutbox(root / "outbox", canon=canon, wiki=wiki),
        operations=OperationStore(root / "operations"),
        events=EventProjection(root / "events"),
    )


@asynccontextmanager
async def open_sqlite_runtime(
    root: Path,
    provider: NarrativeProviderGateway,
) -> AsyncIterator[NarrativeRuntime]:
    stores = filesystem_stores(root)
    checkpoint_path = root / "checkpoints.sqlite"
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        await checkpointer.setup()
        yield NarrativeRuntime.create(stores, provider, checkpointer=checkpointer)


__all__ = [
    "DecisionReplayConflict",
    "NarrativeRuntime",
    "NarrativeRuntimeStores",
    "filesystem_stores",
    "open_sqlite_runtime",
    "decision_operation_key",
    "decision_signature",
]


def decision_operation_key(decision_id: str) -> str:
    return f"decision:{decision_id}"


def decision_signature(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _decision_is_pending(snapshot: Any, decision_id: str) -> bool:
    return any(
        isinstance(item.value, dict) and item.value.get("decision_id") == decision_id
        for item in snapshot.interrupts
    )

from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from novel_workflow.output_contracts.artifacts_vnext import DetailArtifact, StageId
from novel_workflow.quality.decision_contract import QualityDecision
from novel_workflow.runtime.graph.narrative_graph import build_narrative_graph
from novel_workflow.runtime.graph.planning_authority import HierarchicalPlanningAuthority
from novel_workflow.runtime.graph.provider_gateway import NarrativeProviderGateway
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.artifact_store import ArtifactStore
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.cover_asset_store import CoverAssetStore
from novel_workflow.storage.context_manifest_store import ContextManifestStore
from novel_workflow.storage.event_projection import EventProjection
from novel_workflow.storage.evidence_store import EvidenceStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.memory.canon_store import CanonStore
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.memory.story_bible_read_model import StoryBibleReadModelStore
from novel_workflow.storage.domain_outbox import DomainOutbox
from novel_workflow.storage.narrative_run_repository import (
    NarrativeRunRepository,
    RunReadModel,
)
from novel_workflow.storage.operation_store import OperationStore
from novel_workflow.storage.planning_aggregate_store import PlanningAggregateStore
from novel_workflow.storage.stage_artifact_draft_store import StageArtifactDraftStore
from novel_workflow.storage.collaboration_store import CollaborationStore
from novel_workflow.storage.collaboration_context_store import (
    CollaborationContextReceiptStore,
)
from novel_workflow.runtime.graph.author_collaboration_graph import (
    AuthorCollaborationExecutor,
    build_author_collaboration_graph,
)


class DecisionReplayConflict(ValueError):
    """A decision command conflicts with the graph's persisted authority."""


def has_active_graph_interrupt(snapshot: Any) -> bool:
    """Ignore stale parent interrupts when a nested graph can still resume."""
    return bool(_active_interrupts(snapshot))


@dataclass(frozen=True, slots=True)
class NarrativeRuntimeStores:
    runs: NarrativeRunRepository
    artifacts: ArtifactStore
    planning_aggregates: PlanningAggregateStore
    stage_drafts: StageArtifactDraftStore
    chapters: ChapterStore
    evidence: EvidenceStore
    exports: ExportStore
    cover_assets: CoverAssetStore
    context_manifests: ContextManifestStore
    canon: CanonStore
    wiki: WikiProjectionStore
    story_bible: StoryBibleReadModelStore
    outbox: DomainOutbox
    operations: OperationStore
    events: EventProjection
    collaboration: CollaborationStore
    collaboration_contexts: CollaborationContextReceiptStore


@dataclass(slots=True)
class NarrativeRuntime:
    """The only production execution entry point for a narrative Run."""

    stores: NarrativeRuntimeStores
    provider: NarrativeProviderGateway
    checkpointer: Any
    graph: Any
    planning: HierarchicalPlanningAuthority
    collaboration_graph: Any

    @classmethod
    def create(
        cls,
        stores: NarrativeRuntimeStores,
        provider: NarrativeProviderGateway,
        *,
        checkpointer: Any,
    ) -> "NarrativeRuntime":
        planning = HierarchicalPlanningAuthority(
            runs=stores.runs,
            store=stores.planning_aggregates,
        )
        executor = StageExecutor(
            runs=stores.runs,
            artifacts=stores.artifacts,
            planning=planning,
            chapters=stores.chapters,
            operations=stores.operations,
            events=stores.events,
            evidence=stores.evidence,
            exports=stores.exports,
            cover_assets=stores.cover_assets,
            context_manifests=stores.context_manifests,
            outbox=stores.outbox,
            provider=provider,
        )
        return cls(
            stores=stores,
            provider=provider,
            checkpointer=checkpointer,
            graph=build_narrative_graph(executor, checkpointer=checkpointer),
            planning=planning,
            collaboration_graph=build_author_collaboration_graph(
                AuthorCollaborationExecutor(stores, provider),
                checkpointer=checkpointer,
            ),
        )

    async def collaborate(
        self,
        run_id: str,
        collaboration_thread_id: str,
        turn_id: str,
    ) -> dict[str, Any]:
        self.stores.runs.executable_definition(run_id)
        value = await self.collaboration_graph.ainvoke(
            {
                "run_id": run_id,
                "collaboration_thread_id": collaboration_thread_id,
                "active_turn_id": turn_id,
                "status_revision": 0,
            },
            config={
                "configurable": {
                    "thread_id": f"{run_id}:collab:{collaboration_thread_id}",
                }
            },
        )
        return dict(value or {})

    async def start(self, run_id: str) -> RunReadModel:
        self.stores.runs.executable_definition(run_id)
        await self._execute(run_id, {"run_id": run_id})
        return self.stores.runs.read(run_id)

    async def resume(self, run_id: str, decision: dict[str, Any]) -> RunReadModel:
        self.stores.runs.executable_definition(run_id)
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
        interrupts = _active_interrupts(snapshot)
        active_interrupt = next(
            (
                item
                for item in interrupts
                if isinstance(item.value, dict)
                and item.value.get("decision_id") == decision_id
            ),
            None,
        )
        if active_interrupt is None:
            if receipt.status == "pending":
                self.stores.operations.succeed(
                    run_id,
                    operation_key,
                    {"decision_id": decision_id, "action": action},
                )
                await self._project(run_id)
                return self.stores.runs.read(run_id)
            raise DecisionReplayConflict("Decision is not pending on this Run")
        active = active_interrupt.value
        if int(command.get("domain_revision", -1)) != int(
            active.get("domain_revision", -2)
        ):
            raise DecisionReplayConflict("Decision domain revision is stale")
        if action not in (active.get("allowed_actions") or []):
            raise DecisionReplayConflict("Decision action is not allowed")

        await self._execute(
            run_id,
            Command(resume={active_interrupt.id: command}),
        )
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
        snapshot = await self.graph.aget_state(
            self._config(run_id),
            subgraphs=True,
        )
        if has_active_graph_interrupt(snapshot):
            await self._project(run_id)
            return self.stores.runs.read(run_id)
        await self._execute(run_id, None)
        return self.stores.runs.read(run_id)

    async def replay_from_checkpoint(
        self,
        run_id: str,
        checkpoint_id: str,
        *,
        stage_id: StageId,
        attempt: int,
        direction: str = "",
    ) -> RunReadModel:
        """Replay an explicit pre-failure checkpoint with fresh operation keys.

        A terminal graph failure can leave no active interrupt to resume. An
        explicit checkpoint replay is the only safe recovery path in that
        case: it preserves the Run/thread and committed artifacts while
        discarding the failed stage frontier and issuing a new attempt.
        """
        if attempt < 1:
            raise ValueError("Checkpoint replay attempt must be positive")
        config = {
            "configurable": {
                "thread_id": run_id,
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id,
            }
        }
        snapshot = await self.graph.aget_state(config, subgraphs=True)
        if not snapshot.next:
            raise ValueError("Checkpoint replay requires a resumable graph frontier")
        values = dict(snapshot.values or {})
        attempts = dict(values.get("stage_attempts") or {})
        attempts[stage_id] = attempt
        directions = dict(values.get("stage_revision_directions") or {})
        if direction.strip():
            directions[stage_id] = direction.strip()
        candidates = dict(values.get("candidate_artifact_refs") or {})
        candidates.pop(stage_id, None)
        decisions = dict(values.get("decision_actions") or {})
        decisions.pop(stage_id, None)
        decision_ids = dict(values.get("decision_ids") or {})
        decision_ids.pop(stage_id, None)
        statuses = dict(values.get("stage_status") or {})
        statuses[stage_id] = "running"
        replay_config = await self.graph.aupdate_state(
            config,
            {
                "active_stage_id": stage_id,
                "active_chapter_number": 0,
                "status": "running",
                "failure": None,
                "candidate_artifact_refs": candidates,
                "decision_actions": decisions,
                "decision_ids": decision_ids,
                "stage_attempts": attempts,
                "stage_revision_directions": directions,
                "stage_status": statuses,
            },
        )
        await self._execute(run_id, None, config=replay_config)
        return self.stores.runs.read(run_id)

    async def state(self, run_id: str) -> NarrativeRunState:
        snapshot = await self.graph.aget_state(
            self._config(run_id),
            subgraphs=True,
        )
        return _projection_values(snapshot)

    async def refresh_projection(self, run_id: str) -> RunReadModel:
        await self._project(run_id)
        return self.stores.runs.read(run_id)

    async def _execute(
        self,
        run_id: str,
        input_value: Any,
        *,
        config: dict[str, Any] | None = None,
    ) -> None:
        try:
            async for mode, chunk in self.graph.astream(
                input_value,
                config=config or self._config(run_id),
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
        stage_id = str(values.get("active_stage_id") or "brief")
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
        self._project_progress(run_id, values, checkpoint_id)

    def _project_progress(
        self, run_id: str, values: dict[str, Any], checkpoint_id: str
    ) -> None:
        """Project a live read model from super-step checkpoint values.

        Without this, a run that never interrupts (fast mode auto-accepts every
        decision) stays `created` in the read model until the whole graph
        finishes, so state polling and the monitor console see nothing move.
        Interrupt/terminal projection still happens in `_project`, which runs
        after the stream ends and takes precedence over this mid-stream view.
        """
        if not values:
            return
        definition = self.stores.runs.definition(run_id)
        projection = RunReadModel(
            run_id=run_id,
            project_id=str(values.get("project_id") or definition.project_id),
            thread_id=run_id,
            status=str(values.get("status") or "running"),  # type: ignore[arg-type]
            active_stage_id=str(values.get("active_stage_id") or "brief"),  # type: ignore[arg-type]
            active_chapter_number=int(values.get("active_chapter_number") or 0),
            context_manifest_ref=str(values.get("context_manifest_ref") or ""),
            stage_status=dict(values.get("stage_status") or {}),
            artifact_refs=dict(values.get("artifact_refs") or {}),
            pending_decisions=[],
            provider_usage=self.stores.operations.usage_summary(run_id),
            failure=values.get("failure"),
            checkpoint_id=checkpoint_id,
            updated_at="",
        )
        self.stores.runs.project(run_id, projection)

    async def _project(self, run_id: str) -> None:
        snapshot = await self.graph.aget_state(
            self._config(run_id),
            subgraphs=True,
        )
        values = _projection_values(snapshot)
        stage_status = dict(values.get("stage_status") or {})
        pending = [item.value for item in _active_interrupts(snapshot)]
        active_stage = str(values.get("active_stage_id") or "brief")
        active_chapter_number = int(values.get("active_chapter_number") or 0)
        status = str(values.get("status") or "running")
        if pending:
            status = "awaiting_decision"
            node_id = str(pending[0].get("node_id") or "") if isinstance(pending[0], dict) else ""
            interrupted_stage = node_id.partition(".")[0]
            if interrupted_stage in stage_status:
                active_stage = interrupted_stage
            if active_stage in stage_status:
                stage_status[active_stage] = "awaiting_decision"
            chapter_id = (
                str(pending[0].get("chapter_id") or "")
                if isinstance(pending[0], dict)
                else ""
            )
            if chapter_id:
                active_chapter_number = self._chapter_number(
                    run_id,
                    values,
                    chapter_id,
                )
        definition = self.stores.runs.definition(run_id)
        quality_decision = _latest_quality_decision(
            self.stores.events,
            run_id,
            chapter_id=(
                str(pending[0].get("chapter_id") or "")
                if pending and isinstance(pending[0], dict)
                else str(values.get("active_chapter_id") or "")
            ),
        )
        projection = RunReadModel(
            run_id=run_id,
            project_id=str(values.get("project_id") or definition.project_id),
            thread_id=run_id,
            status=status,  # type: ignore[arg-type]
            active_stage_id=active_stage,  # type: ignore[arg-type]
            active_chapter_number=active_chapter_number,
            context_manifest_ref=str(values.get("context_manifest_ref") or ""),
            stage_status=stage_status,
            artifact_refs=dict(values.get("artifact_refs") or {}),
            pending_decisions=pending,
            quality_decision=quality_decision,
            provider_usage=self.stores.operations.usage_summary(run_id),
            failure=values.get("failure"),
            checkpoint_id=str(snapshot.config.get("configurable", {}).get("checkpoint_id") or ""),
            updated_at="",
        )
        self.stores.runs.project(run_id, projection)

    def _chapter_number(
        self,
        run_id: str,
        values: dict[str, Any],
        chapter_id: str,
    ) -> int:
        detail_ref = str((values.get("artifact_refs") or {}).get("detail") or "")
        if not detail_ref:
            raise ValueError("A chapter decision requires a committed Detail artifact")
        detail = DetailArtifact.model_validate(
            self.stores.artifacts.read(run_id, detail_ref).payload
        )
        for chapter in detail.chapters:
            if chapter.ref == chapter_id:
                return int(chapter.ref.removeprefix("chapter-"))
        raise ValueError("Chapter decision does not reference the frozen Detail artifact")

    @staticmethod
    def _config(run_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": run_id}}


def filesystem_stores(root: Path) -> NarrativeRuntimeStores:
    evidence = EvidenceStore(root / "evidence")
    canon = CanonStore(root / "canon")
    wiki = WikiProjectionStore(root / "wiki")
    story_bible = StoryBibleReadModelStore(
        root / "story_bible",
        evidence=evidence,
        canon=canon,
        wiki=wiki,
    )
    return NarrativeRuntimeStores(
        runs=NarrativeRunRepository(root / "runs"),
        artifacts=ArtifactStore(root / "artifacts"),
        planning_aggregates=PlanningAggregateStore(root / "planning_aggregates"),
        stage_drafts=StageArtifactDraftStore(root / "stage_drafts"),
        chapters=ChapterStore(root / "chapters"),
        evidence=evidence,
        exports=ExportStore(root / "exports"),
        cover_assets=CoverAssetStore(root / "cover_assets"),
        context_manifests=ContextManifestStore(root / "context_manifests"),
        canon=canon,
        wiki=wiki,
        story_bible=story_bible,
        outbox=DomainOutbox(root / "outbox", canon=canon, wiki=wiki),
        operations=OperationStore(root / "operations"),
        events=EventProjection(root / "events"),
        collaboration=CollaborationStore(root / "collaboration"),
        collaboration_contexts=CollaborationContextReceiptStore(
            root / "collaboration_contexts"
        ),
    )


def _projection_values(snapshot: Any) -> NarrativeRunState:
    """Overlay the one active interrupt frontier onto its parent routing state."""

    values = dict(snapshot.values or {})
    frontiers = _interrupted_frontiers(snapshot)
    if len(frontiers) > 1:
        raise ValueError("A narrative Run cannot expose multiple decision frontiers")
    if frontiers:
        values.update(dict(frontiers[0].values or {}))
    return values


def _latest_quality_decision(
    events: EventProjection,
    run_id: str,
    *,
    chapter_id: str,
) -> QualityDecision | None:
    for event in reversed(events.read(run_id)):
        if chapter_id and event.chapter_id and event.chapter_id != chapter_id:
            continue
        if not isinstance(event.payload, dict):
            continue
        payload = event.payload.get("quality_decision")
        if isinstance(payload, dict):
            return QualityDecision.model_validate(payload)
    return None


def _interrupted_frontiers(snapshot: Any) -> list[Any]:
    frontiers: list[Any] = []
    for task in getattr(snapshot, "tasks", ()):
        child = getattr(task, "state", None)
        if child is None or not hasattr(child, "values"):
            continue
        nested = _interrupted_frontiers(child)
        if nested:
            frontiers.extend(nested)
        elif getattr(child, "interrupts", ()) or getattr(task, "interrupts", ()):
            frontiers.append(child)
    return frontiers


def _active_interrupts(snapshot: Any) -> tuple[Any, ...]:
    """Return the deepest durable interrupt set, excluding stale parents."""

    nested_interrupts: list[Any] = []
    for task in getattr(snapshot, "tasks", ()):
        child = getattr(task, "state", None)
        if child is not None and hasattr(child, "values"):
            active = _active_interrupts(child)
            if active:
                nested_interrupts.extend(active)
                continue
        nested_interrupts.extend(getattr(task, "interrupts", ()) or ())
    if nested_interrupts:
        return tuple(nested_interrupts)
    return tuple(getattr(snapshot, "interrupts", ()) or ())


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
        for item in _active_interrupts(snapshot)
    )

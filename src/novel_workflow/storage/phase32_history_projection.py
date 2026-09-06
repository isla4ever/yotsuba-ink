"""Route-aware history projection for the dormant Phase 32 Run repository."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_read_model import RouteRunReadModel
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


_ROUTE_LABELS = {
    "screenplay_sample": "剧本样片",
    "short_novel": "短中篇小说",
    "long_novel": "长篇小说",
}


@dataclass(frozen=True, slots=True)
class Phase32HistoryProjection:
    """Project one dynamic Run manifest for history/workbench readers.

    This reader intentionally does not load literary Artifacts or Provider
    bindings.  The manifest and read model are the only sources for route
    identity, progress, status, and pending decisions.
    """

    runs: Phase32RunRepository

    def list(
        self,
        *,
        project_id: str = "",
        status: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for projection in self.runs.list_read_models():
            if project_id and projection.project_id != project_id:
                continue
            if status and projection.status != status:
                continue
            definition = self.runs.definition(projection.run_id)
            items.append(self.item(projection, definition=definition))
            if limit is not None and len(items) >= limit:
                break
        return items

    def latest(self, project_id: str) -> dict[str, Any] | None:
        items = self.list(project_id=project_id, limit=1)
        return items[0] if items else None

    def item(
        self,
        projection: RouteRunReadModel,
        *,
        definition: GraphRunDefinition | None = None,
    ) -> dict[str, Any]:
        definition = definition or self.runs.definition(projection.run_id)
        stages = projection.stage_manifest
        completed = [
            stage.stage_id
            for stage in stages
            if projection.stage_status.get(stage.stage_id) == "completed"
        ]
        active_stage = next(
            stage for stage in stages if stage.stage_id == projection.active_stage_id
        )
        return {
            "run_id": projection.run_id,
            "project_id": projection.project_id,
            "creation_route_id": projection.creation_route_id,
            "route_revision": projection.route_revision,
            "route_label": _ROUTE_LABELS[definition.creation_route_id],
            "deliverable_kind": definition.route_contract.route_manifest.deliverable_kind,
            "status": projection.status,
            "active_stage": {
                "stage_id": active_stage.stage_id,
                "label": active_stage.label,
                "ordinal": active_stage.ordinal,
                "total": len(stages),
            },
            "completed_stage_ids": completed,
            "progress": {
                "completed": len(completed),
                "total": len(stages),
                "ratio": len(completed) / len(stages),
            },
            "active_unit_ref": projection.active_unit_ref,
            "pending_decisions": [
                decision.model_dump(mode="json")
                for decision in projection.pending_decisions
            ],
            "provider_usage": projection.provider_usage.model_dump(mode="json"),
            "failure": projection.failure.model_dump(mode="json")
            if projection.failure
            else None,
            "checkpoint_id": projection.checkpoint_id,
            "can_branch": bool(
                projection.status == "awaiting_decision"
                and projection.checkpoint_id
                and projection.pending_decisions
            ),
            "export_ready": projection.status != "image_deferred" and "export" in completed,
            "created_at": definition.created_at,
            "updated_at": projection.updated_at,
        }


__all__ = ["Phase32HistoryProjection"]

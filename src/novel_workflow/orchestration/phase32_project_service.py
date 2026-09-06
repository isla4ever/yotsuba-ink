"""Authoritative Project creation and read projection for Phase 32."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
    Phase32CreationService,
    PreparedPhase32Run,
)
from novel_workflow.storage.phase32_history_projection import Phase32HistoryProjection
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactStore,
    Phase32ArtifactStoreError,
)
from novel_workflow.storage.phase32_project_catalog_store import (
    Phase32ProjectCatalogRecord,
    Phase32ProjectCatalogStore,
)
from novel_workflow.storage.phase32_run_repository import Phase32RunRecord
from novel_workflow.storage.project_schemas import ACCENT_HUE_SEQUENCE


_PENDING_TITLE = "待定标题"


@dataclass(frozen=True, slots=True)
class Phase32ProjectService:
    """Create Project membership and project one canonical latest Run."""

    creation: Phase32CreationService
    catalog: Phase32ProjectCatalogStore
    history: Phase32HistoryProjection
    artifacts: Phase32ArtifactStore

    def create(self, request: CreationPreparationRequest) -> dict[str, Any]:
        prepared = self.creation.prepare(request)
        self._register(prepared)
        return self._project(prepared.record, self.catalog.get(prepared.definition.project_id))

    def list(self) -> list[dict[str, Any]]:
        return [self.get(record.project_id) for record in self.catalog.list()]

    def get(self, project_id: str) -> dict[str, Any]:
        catalog_record = self.catalog.get(project_id)
        run_id = catalog_record.run_ids[-1]
        record = self.creation.repository.read(run_id)
        return self._project(record, catalog_record)

    def reorder(self, project_ids: list[str]) -> list[dict[str, Any]]:
        records = self.catalog.reorder(project_ids)
        return [self.get(record.project_id) for record in records]

    def _register(self, prepared: PreparedPhase32Run) -> None:
        definition = prepared.definition
        self.catalog.register(
            Phase32ProjectCatalogRecord(
                project_id=definition.project_id,
                run_ids=(definition.run_id,),
                accent_hue=_accent_hue(definition.project_id),
                created_at=definition.created_at,
            )
        )

    def _project(
        self,
        record: Phase32RunRecord,
        catalog_record: Phase32ProjectCatalogRecord,
    ) -> dict[str, Any]:
        definition = record.definition
        read_model = record.read_model
        if definition.project_id != catalog_record.project_id:
            raise ValueError("Phase 32 Project and Run identities do not match")
        if definition.run_id != catalog_record.run_ids[-1]:
            raise ValueError("Phase 32 Project latest Run identity is inconsistent")
        summary = self.history.item(read_model, definition=definition)
        inputs = definition.inputs.payload
        creative_intent = inputs.get("creative_intent")
        scale = definition.scale_profile.payload
        brief_binding = read_model.artifact_refs.get("brief")
        title = _PENDING_TITLE
        if brief_binding:
            title = self._brief_title(definition.run_id, brief_binding.artifact_ref)
        return {
            "architecture_version": definition.architecture_version,
            "id": definition.project_id,
            "title": title,
            "summary": creative_intent if isinstance(creative_intent, str) else "",
            "accent_hue": catalog_record.accent_hue,
            "workflow_id": definition.workflow_id,
            "status": catalog_record.status,
            "created_at": catalog_record.created_at,
            "updated_at": read_model.updated_at,
            "latest_run_id": definition.run_id,
            "creation_route_id": definition.creation_route_id,
            "route_revision": definition.route_revision,
            "route_label": summary["route_label"],
            "deliverable_kind": summary["deliverable_kind"],
            "run_status": read_model.status,
            "active_stage": summary["active_stage"],
            "stage_manifest": [
                stage.model_dump(mode="json") for stage in read_model.stage_manifest
            ],
            "stage_status": dict(read_model.stage_status),
            "completed_stage_ids": summary["completed_stage_ids"],
            "progress": summary["progress"],
            "target": scale.get("target", 0),
            "target_unit": scale.get("unit", "characters"),
            "words": 0,
            "provider_usage": summary["provider_usage"],
            "pending_decisions": summary["pending_decisions"],
            "failure": summary["failure"],
        }

    def _brief_title(self, run_id: str, artifact_ref: str) -> str:
        """Keep the bookshelf readable when an older local brief is quarantined."""

        try:
            brief = self.artifacts.read(run_id, artifact_ref)
        except (FileNotFoundError, Phase32ArtifactStoreError):
            return _PENDING_TITLE
        title = brief.payload.get("title")
        return title if isinstance(title, str) and title.strip() else _PENDING_TITLE


def _accent_hue(project_id: str) -> int:
    digest = hashlib.sha256(project_id.encode("utf-8")).digest()
    return ACCENT_HUE_SEQUENCE[int.from_bytes(digest[:2], "big") % len(ACCENT_HUE_SEQUENCE)]


__all__ = ["Phase32ProjectService"]

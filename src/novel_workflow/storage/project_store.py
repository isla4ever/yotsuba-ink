from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

from novel_workflow.storage.json_store import JsonStore
from novel_workflow.storage.project_schemas import ProjectRecord, next_accent_hue
from novel_workflow.storage.run_history_projection import RunHistoryProjection
from novel_workflow.workflows.seed_policy import scrub_narrative_seeds


class ProjectStoreError(ValueError):
    """Domain-rule violation (delete protection etc.); routes map it to 409."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    """Domain wrapper around JsonStore(root/'projects').

    Owns project lifecycle: id/accent allocation, per-project workflow copy,
    delete protection against existing runs, and latest-run aggregation.
    """

    def __init__(self, root: Path, *, workflow_store: JsonStore, run_history: RunHistoryProjection) -> None:
        self.store = JsonStore(root)
        self.workflow_store = workflow_store
        self.run_history = run_history

    def list(self) -> list[ProjectRecord]:
        records = [ProjectRecord.model_validate(item) for item in self.store.list()]
        records.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return records

    def get(self, project_id: str) -> ProjectRecord:
        return ProjectRecord.model_validate(self.store.read(project_id))

    def create(self, *, title: str, summary: str = "", template_workflow_id: str = "default-novel-workflow") -> ProjectRecord:
        # Phase 12 M1: the per-project copy starts from genuinely blank story
        # fields — demo narrative seeds are cleared; the template itself keeps them.
        template = scrub_narrative_seeds(self.workflow_store.read(template_workflow_id))
        project_id = f"proj-{uuid4().hex[:10]}"
        workflow_id = f"wf-{project_id}"
        self.workflow_store.write(workflow_id, {**template, "id": workflow_id, "name": title, "is_template": False})
        timestamp = now()
        record = ProjectRecord(
            id=project_id,
            title=title,
            summary=summary,
            accent_hue=next_accent_hue([item.accent_hue for item in self.list()]),
            workflow_id=workflow_id,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.store.write(project_id, record.model_dump())
        return record

    def patch(self, project_id: str, changes: dict[str, Any]) -> ProjectRecord:
        record = self.get(project_id)
        allowed = {key: value for key, value in changes.items() if key in {"title", "summary", "status", "accent_hue"}}
        updated = record.model_copy(update={**allowed, "updated_at": now()})
        self.store.write(project_id, updated.model_dump())
        return updated

    def delete(self, project_id: str) -> None:
        record = self.get(project_id)
        if self.run_history.has_project_run(project_id):
            raise ProjectStoreError(
                f"作品「{record.title}」已有创作运行记录，禁止直接删除；如需收起请改用归档（PATCH status=archived）。"
            )
        self.store.delete(project_id)
        self._delete_owned_workflow(record)

    def touch_run(self, project_id: str, run_id: str) -> None:
        """Best-effort backfill of latest_run_id/updated_at; silent when the project is absent."""
        if not project_id:
            return
        try:
            record = self.get(project_id)
        except (FileNotFoundError, ValueError):
            return
        updated = record.model_copy(update={"latest_run_id": run_id or record.latest_run_id, "updated_at": now()})
        self.store.write(project_id, updated.model_dump())

    def summary(self, project_id: str) -> dict[str, Any]:
        record = self.get(project_id)
        latest = self.run_history.latest(project_id)
        return {
            "project": record.model_dump(),
            "latest_run": latest,
            "title": str((latest or {}).get("title") or record.title),
            "status": str((latest or {}).get("status") or ""),
            "current_stage": dict((latest or {}).get("current_stage") or {}),
            "completed_stage_ids": list((latest or {}).get("completed_stage_ids") or []),
            "words": int((latest or {}).get("words") or 0),
            "updated_at": str((latest or {}).get("updated_at") or record.updated_at),
        }

    def projects_referencing_workflow(self, workflow_id: str) -> list[ProjectRecord]:
        return [record for record in self.list() if record.workflow_id == workflow_id]

    def _delete_owned_workflow(self, record: ProjectRecord) -> None:
        if record.workflow_id != f"wf-{record.id}":
            return
        if self.projects_referencing_workflow(record.workflow_id):
            return
        self.workflow_store.delete(record.workflow_id)

"""Project membership and bookshelf order for the Phase 32 runtime."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32ProjectCatalogRecord(BaseModel):
    """Bind one product Project to its immutable Phase 32 Run lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    run_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    status: Literal["active", "archived"] = "active"
    accent_hue: int = Field(ge=0, le=360)
    created_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def require_unique_runs(self) -> "Phase32ProjectCatalogRecord":
        if len(set(self.run_ids)) != len(self.run_ids):
            raise ValueError("Phase 32 Project Run ids must be unique")
        return self


class Phase32ProjectCatalogError(ValueError):
    code = "phase32_project_catalog_invalid"


class Phase32ProjectCatalogStore:
    """Persist Project membership separately from executable Run authority."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.records_root = root / "records"
        self.order_path = root / "order.json"
        self.records_root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def get(self, project_id: str) -> Phase32ProjectCatalogRecord:
        safe_project_id = require_safe_id(project_id, label="project_id")
        try:
            record = Phase32ProjectCatalogRecord.model_validate(
                read_json(self.records_root / f"{safe_project_id}.json")
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ProjectCatalogError(
                f"Malformed Phase 32 Project catalog record: {safe_project_id}"
            ) from exc
        if record.project_id != safe_project_id:
            raise Phase32ProjectCatalogError(
                "Phase 32 Project storage identity does not match its record"
            )
        return record

    def list(self) -> list[Phase32ProjectCatalogRecord]:
        records = [self.get(path.stem) for path in self.records_root.glob("*.json")]
        by_id = {record.project_id: record for record in records}
        order = self._read_order()
        ordered = [by_id.pop(project_id) for project_id in order if project_id in by_id]
        ordered.extend(
            sorted(
                by_id.values(),
                key=lambda record: (record.created_at, record.project_id),
                reverse=True,
            )
        )
        return ordered

    def register(self, record: Phase32ProjectCatalogRecord) -> Phase32ProjectCatalogRecord:
        with self._lock:
            path = self.records_root / f"{record.project_id}.json"
            if path.exists():
                existing = self.get(record.project_id)
                if existing != record:
                    raise Phase32ProjectCatalogError(
                        "Phase 32 Project id is already bound to another Run lineage"
                    )
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def append_run(
        self,
        project_id: str,
        *,
        source_run_id: str,
        target_run_id: str,
    ) -> Phase32ProjectCatalogRecord:
        with self._lock:
            current = self.get(project_id)
            if target_run_id in current.run_ids:
                target_index = current.run_ids.index(target_run_id)
                if target_index == 0 or current.run_ids[target_index - 1] != source_run_id:
                    raise Phase32ProjectCatalogError(
                        "Project Run lineage does not bind the amendment source to its successor"
                    )
                return current
            if current.run_ids[-1] != source_run_id:
                raise Phase32ProjectCatalogError(
                    "Amendment branch source is not the Project's latest Run"
                )
            updated = current.model_copy(
                update={"run_ids": (*current.run_ids, target_run_id)}
            )
            atomic_write_json(
                self.records_root / f"{current.project_id}.json",
                updated.model_dump(mode="json"),
            )
            return updated

    def reorder(self, project_ids: list[str]) -> list[Phase32ProjectCatalogRecord]:
        safe_ids = [require_safe_id(item, label="project_id") for item in project_ids]
        if len(set(safe_ids)) != len(safe_ids):
            raise Phase32ProjectCatalogError("Project order contains duplicate ids")
        available = {record.project_id for record in self.list()}
        if set(safe_ids) != available:
            raise Phase32ProjectCatalogError(
                "Project order must contain the complete Phase 32 Project set"
            )
        with self._lock:
            atomic_write_json(
                self.order_path,
                {
                    "architecture_version": "phase32-routes-v1",
                    "project_ids": safe_ids,
                },
            )
        return self.list()

    def _read_order(self) -> tuple[str, ...]:
        if not self.order_path.exists():
            return ()
        try:
            payload = read_json(self.order_path)
            if payload.get("architecture_version") != "phase32-routes-v1":
                raise ValueError("Unsupported Project order architecture")
            project_ids = payload.get("project_ids")
            if not isinstance(project_ids, list) or not all(
                isinstance(item, str) for item in project_ids
            ):
                raise ValueError("Project order ids must be a list of strings")
            safe_ids = tuple(require_safe_id(item, label="project_id") for item in project_ids)
            if len(set(safe_ids)) != len(safe_ids):
                raise ValueError("Project order ids must be unique")
            return safe_ids
        except Exception as exc:
            raise Phase32ProjectCatalogError("Malformed Phase 32 Project order") from exc


__all__ = [
    "Phase32ProjectCatalogError",
    "Phase32ProjectCatalogRecord",
    "Phase32ProjectCatalogStore",
]

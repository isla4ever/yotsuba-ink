from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from novel_workflow.output_contracts.artifacts_vnext import STAGE_ORDER, StageId
from novel_workflow.providers.frozen_contract import (
    FrozenProviderConfig,
    FrozenProviderTemplate,
    FrozenStructuredTask,
    frozen_provider_config_digest,
    frozen_provider_template_digest,
    prompt_digest,
)
from novel_workflow.providers.usage import ProviderUsageSummary
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile


RunStatus = Literal[
    "created",
    "running",
    "awaiting_decision",
    "completed",
    "failed",
    "cancelled",
]
StageStatus = Literal["locked", "available", "running", "awaiting_decision", "completed", "failed"]


class ProviderBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_profile_id: str = Field(min_length=1, max_length=120)
    provider_config: FrozenProviderConfig
    template_id: str = Field(min_length=1, max_length=120)
    provider_template: FrozenProviderTemplate
    provider_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_template_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: str = Field(min_length=1, max_length=200)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1800, ge=1)
    top_p: float = Field(default=0.95, ge=0, le=1)
    timeout_seconds: int = Field(default=120, ge=1)
    prompt_template_id: str = Field(min_length=1, max_length=120)
    prompt_template: str = Field(min_length=1)
    prompt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_tasks: dict[str, FrozenStructuredTask]

    @field_validator("provider_profile_id")
    @classmethod
    def require_explicit_provider(cls, value: str) -> str:
        provider_id = value.strip()
        if not provider_id or provider_id == "inherit":
            raise ValueError("Provider binding must name an explicit profile")
        return provider_id

    @model_validator(mode="after")
    def validate_frozen_snapshot(self) -> "ProviderBinding":
        if self.provider_config.provider_profile_id != self.provider_profile_id:
            raise ValueError("Provider binding profile does not match its frozen config")
        if self.provider_config.kind != "openai-compatible":
            raise ValueError("Text Provider binding requires an openai-compatible config")
        if self.provider_config.template_id != self.template_id:
            raise ValueError("Provider binding template does not match its frozen config")
        if self.provider_template.id != self.template_id:
            raise ValueError("Provider binding template does not match its frozen snapshot")
        if self.provider_template.kind != "openai-compatible":
            raise ValueError("Text Provider binding requires a text template snapshot")
        if frozen_provider_config_digest(self.provider_config) != self.provider_config_digest:
            raise ValueError("Provider config digest does not match its frozen snapshot")
        if frozen_provider_template_digest(self.provider_template) != self.provider_template_digest:
            raise ValueError("Provider template digest does not match its frozen snapshot")
        if prompt_digest(self.prompt_template) != self.prompt_digest:
            raise ValueError("Prompt digest does not match its frozen content")
        return self


class CoverAssetBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_profile_id: str = Field(min_length=1, max_length=120)
    provider_config: FrozenProviderConfig
    template_id: str = Field(min_length=1, max_length=120)
    provider_template: FrozenProviderTemplate
    provider_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_template_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: str = Field(min_length=1, max_length=200)
    candidate_count: int = Field(ge=1, le=4)
    size: str = Field(pattern=r"^[1-9][0-9]{2,3}x[1-9][0-9]{2,3}$")
    quality: Literal["low", "medium", "high"]
    timeout_seconds: int = Field(default=180, ge=1, le=600)
    failure_policy: Literal["fail_run"] = "fail_run"

    @field_validator("provider_profile_id")
    @classmethod
    def require_explicit_provider(cls, value: str) -> str:
        provider_id = value.strip()
        if not provider_id or provider_id == "inherit":
            raise ValueError("Cover asset binding must name an explicit image profile")
        return provider_id

    @model_validator(mode="after")
    def validate_dimensions(self) -> "CoverAssetBinding":
        width, height = (int(item) for item in self.size.split("x", maxsplit=1))
        if not (256 <= width <= 8192 and 256 <= height <= 8192):
            raise ValueError("Cover image dimensions must stay between 256 and 8192 pixels")
        if self.provider_config.provider_profile_id != self.provider_profile_id:
            raise ValueError("Cover binding profile does not match its frozen config")
        if self.provider_config.kind != "openai-compatible-image":
            raise ValueError("Cover binding requires an image Provider config")
        if self.provider_config.template_id != self.template_id:
            raise ValueError("Cover binding template does not match its frozen config")
        if self.provider_template.id != self.template_id:
            raise ValueError("Cover binding template does not match its frozen snapshot")
        if self.provider_template.kind != "openai-compatible-image":
            raise ValueError("Cover binding requires an image template snapshot")
        if frozen_provider_config_digest(self.provider_config) != self.provider_config_digest:
            raise ValueError("Cover Provider config digest does not match its frozen snapshot")
        if frozen_provider_template_digest(self.provider_template) != self.provider_template_digest:
            raise ValueError("Cover Provider template digest does not match its frozen snapshot")
        return self

    def aspect_ratio(self) -> float:
        width, height = (int(item) for item in self.size.split("x", maxsplit=1))
        return width / height


class ExportPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["md", "json", "zip"] = "zip"
    author: str = Field(default="", max_length=160)
    version_note: str = Field(default="", max_length=500)


class BranchOrigin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_run_id: str = Field(min_length=1, max_length=240)
    source_checkpoint_id: str = Field(min_length=1, max_length=240)


class RunDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    architecture_version: Literal["phase27-vnext"] = "phase27-vnext"
    run_id: str
    project_id: str
    workflow_id: str
    workflow_revision: str
    workflow_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality_mode: Literal["fast", "balanced", "deep"] = "balanced"
    inputs: dict[str, Any]
    scale_profile: NarrativeScaleProfile
    provider_bindings: dict[StageId, ProviderBinding]
    cover_asset_binding: CoverAssetBinding
    export_preferences: ExportPreferences
    branch_origin: BranchOrigin | None = None
    created_at: str


class RunReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    thread_id: str
    status: RunStatus
    active_stage_id: StageId = "brief"
    active_chapter_number: int = 0
    context_manifest_ref: str = ""
    stage_status: dict[StageId, StageStatus]
    artifact_refs: dict[StageId, str] = Field(default_factory=dict)
    pending_decisions: list[dict[str, Any]] = Field(default_factory=list)
    provider_usage: ProviderUsageSummary = Field(default_factory=ProviderUsageSummary)
    failure: dict[str, Any] | None = None
    checkpoint_id: str = ""
    updated_at: str


class NarrativeRunRepository:
    """Immutable Run definitions plus a rebuildable graph read projection."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create(
        self,
        *,
        run_id: str,
        project_id: str,
        workflow_id: str,
        workflow_revision: str,
        workflow_digest: str,
        quality_mode: Literal["fast", "balanced", "deep"],
        inputs: dict[str, Any],
        scale_profile: NarrativeScaleProfile,
        provider_bindings: dict[StageId, ProviderBinding],
        cover_asset_binding: CoverAssetBinding,
        export_preferences: ExportPreferences,
        branch_origin: BranchOrigin | None = None,
    ) -> RunDefinition:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id
        definition_path = directory / "definition.json"
        with self._lock:
            if definition_path.exists():
                raise FileExistsError(run_id)
            definition = RunDefinition(
                run_id=run_id,
                project_id=project_id,
                workflow_id=workflow_id,
                workflow_revision=workflow_revision,
                workflow_digest=workflow_digest,
                quality_mode=quality_mode,
                inputs=inputs,
                scale_profile=scale_profile,
                provider_bindings=provider_bindings,
                cover_asset_binding=cover_asset_binding,
                export_preferences=export_preferences,
                branch_origin=branch_origin,
                created_at=_now(),
            )
            atomic_write_json(definition_path, definition.model_dump(mode="json"))
            initial_status: dict[StageId, StageStatus] = {stage: "locked" for stage in STAGE_ORDER}
            initial_status["brief"] = "available"
            projection = RunReadModel(
                run_id=run_id,
                project_id=project_id,
                thread_id=run_id,
                status="created",
                stage_status=initial_status,
                updated_at=_now(),
            )
            atomic_write_json(directory / "read_model.json", projection.model_dump(mode="json"))
            return definition

    def definition(self, run_id: str) -> RunDefinition:
        return RunDefinition.model_validate(read_json(self._path(run_id, "definition.json")))

    def read(self, run_id: str) -> RunReadModel:
        return RunReadModel.model_validate(read_json(self._path(run_id, "read_model.json")))

    def project(self, run_id: str, projection: RunReadModel) -> RunReadModel:
        if projection.run_id != run_id or projection.thread_id != run_id:
            raise ValueError("Run projection identity mismatch")
        with self._lock:
            next_projection = projection.model_copy(update={"updated_at": _now()})
            atomic_write_json(self._path(run_id, "read_model.json"), next_projection.model_dump(mode="json"))
            return next_projection

    def list(self) -> list[RunReadModel]:
        records: list[RunReadModel] = []
        for path in sorted(self.root.glob("*/read_model.json")):
            records.append(RunReadModel.model_validate(read_json(path)))
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def exists(self, run_id: str) -> bool:
        return self._path(run_id, "definition.json").exists()

    def _path(self, run_id: str, name: str) -> Path:
        require_safe_id(run_id, label="run_id")
        return self.root / run_id / name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

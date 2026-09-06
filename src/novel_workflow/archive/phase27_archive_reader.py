"""Strict, zero-provider reader for immutable Phase 27 Run evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from novel_workflow.storage.atomic_json import require_safe_id


PHASE27_ARCHITECTURE_VERSION = "phase27-vnext"
PHASE27_STAGE_ORDER = (
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
    "export",
)

Phase27StageId = Literal[
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
    "export",
]
Phase27RunStatus = Literal[
    "created",
    "running",
    "awaiting_decision",
    "completed",
    "failed",
    "cancelled",
]
Phase27StageStatus = Literal[
    "locked",
    "available",
    "running",
    "awaiting_decision",
    "completed",
    "failed",
]


class ArchiveRunReadOnlyError(RuntimeError):
    code = "archived_run_read_only"


class Phase27ArchiveFormatError(ValueError):
    code = "phase27_archive_invalid"


class Phase27ArchiveArchitectureError(Phase27ArchiveFormatError):
    code = "archive_architecture_unsupported"


class Phase27ArchiveCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mutate: Literal[False] = False
    execute: Literal[False] = False
    resume: Literal[False] = False
    decide: Literal[False] = False
    branch: Literal[False] = False
    amend: Literal[False] = False
    stream: Literal[False] = False
    writeback: Literal[False] = False
    provider: Literal[False] = False


class Phase27ArchiveProviderUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_operations: int = Field(default=0, ge=0)
    returned_operations: int = Field(default=0, ge=0)
    succeeded_operations: int = Field(default=0, ge=0)
    contract_rejected_operations: int = Field(default=0, ge=0)
    failed_operations: int = Field(default=0, ge=0)
    pending_operations: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)


class Phase27ArchiveFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=240)
    node_id: str = Field(default="", max_length=500)
    retryable: bool = False
    message: str = Field(default="", max_length=4_000)
    message_truncated: bool = False


class Phase27ArchivePendingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    decision_id: str = Field(min_length=1, max_length=500)
    kind: str = Field(min_length=1, max_length=160)
    node_id: str = Field(default="", max_length=500)
    artifact_available: bool = False
    allowed_actions: tuple[str, ...] = ()


class Phase27ArchiveRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase27-vnext"] = PHASE27_ARCHITECTURE_VERSION
    archive_state: Literal["archived_read_only"] = "archived_read_only"
    run_id: str
    project_id: str
    workflow_id: str
    workflow_revision: str
    legacy_quality_mode: Literal["fast", "balanced", "deep"]
    status: Phase27RunStatus
    active_stage_id: Phase27StageId
    active_chapter_number: int = Field(ge=0)
    stage_status: dict[Phase27StageId, Phase27StageStatus]
    created_at: str = Field(min_length=1, max_length=80)
    updated_at: str = Field(min_length=1, max_length=80)
    capabilities: Phase27ArchiveCapabilities = Field(
        default_factory=Phase27ArchiveCapabilities
    )


class Phase27ArchiveRunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: Phase27ArchiveRunSummary
    artifact_stages: tuple[Phase27StageId, ...]
    pending_decisions: tuple[Phase27ArchivePendingDecision, ...]
    provider_usage: Phase27ArchiveProviderUsage
    failure: Phase27ArchiveFailure | None = None
    events_available: bool


class Phase27ArchiveRunPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[Phase27ArchiveRunSummary, ...]
    next_cursor: int | None
    read_only: Literal[True] = True


class Phase27ArchiveEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_id: str = Field(min_length=1, max_length=1_000)
    sequence: int = Field(ge=1)
    occurred_at: str = Field(min_length=1, max_length=80)
    type: str = Field(min_length=1, max_length=240)
    stage_id: Phase27StageId | None = None
    node_id: str = Field(default="", max_length=500)
    chapter_id: str = Field(default="", max_length=500)
    status: str = Field(default="", max_length=160)
    has_payload: bool
    payload_ref: str = Field(default="", max_length=1_000)
    checkpoint_id: str = Field(default="", max_length=500)


class Phase27ArchiveEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    items: tuple[Phase27ArchiveEvent, ...]
    next_cursor: int | None
    read_only: Literal[True] = True


class _Phase27DefinitionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    architecture_version: Literal["phase27-vnext"]
    run_id: str
    project_id: str
    workflow_id: str
    workflow_revision: str
    workflow_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality_mode: Literal["fast", "balanced", "deep"]
    inputs: dict[str, Any]
    scale_profile: dict[str, Any]
    hierarchical_scale_plan: dict[str, Any] | None = None
    provider_bindings: dict[str, Any]
    cover_asset_binding: dict[str, Any]
    export_preferences: dict[str, Any]
    branch_origin: dict[str, Any] | None = None
    created_at: str = Field(min_length=1, max_length=80)


class _Phase27ReadModelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    project_id: str
    thread_id: str
    status: Phase27RunStatus
    active_stage_id: Phase27StageId
    active_chapter_number: int = Field(ge=0)
    context_manifest_ref: str
    stage_status: dict[Phase27StageId, Phase27StageStatus]
    artifact_refs: dict[Phase27StageId, str]
    pending_decisions: list[dict[str, Any]]
    quality_decision: dict[str, Any] | None = None
    provider_usage: Phase27ArchiveProviderUsage
    failure: dict[str, Any] | None = None
    checkpoint_id: str
    updated_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_phase27_projection(self) -> "_Phase27ReadModelRecord":
        if self.thread_id != self.run_id:
            raise ValueError("Phase 27 archive thread identity must equal Run identity")
        if set(self.stage_status) != set(PHASE27_STAGE_ORDER):
            raise ValueError("Phase 27 archive stage status must cover all eight stages")
        return self


class _Phase27EventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_id: str = Field(min_length=1, max_length=1_000)
    sequence: int = Field(ge=1)
    occurred_at: str = Field(min_length=1, max_length=80)
    run_id: str
    thread_id: str
    type: str = Field(min_length=1, max_length=240)
    stage_id: Phase27StageId | None = None
    node_id: str = Field(default="", max_length=500)
    chapter_id: str = Field(default="", max_length=500)
    status: str = Field(default="", max_length=160)
    payload: dict[str, Any] | None = None
    payload_ref: str = Field(default="", max_length=1_000)
    checkpoint_id: str = Field(default="", max_length=500)


class Phase27ArchiveRunReader:
    """Project Phase 27 files without importing any executable Run contract."""

    def __init__(self, runs_root: Path, events_root: Path) -> None:
        self.runs_root = runs_root
        self.events_root = events_root

    def list(self, *, cursor: int = 0, limit: int = 20) -> Phase27ArchiveRunPage:
        if cursor < 0 or not 1 <= limit <= 50:
            raise ValueError("Invalid archive pagination")
        if not self.runs_root.exists():
            return Phase27ArchiveRunPage(items=(), next_cursor=None)
        summaries = [
            self._load_summary(path.parent.name)
            for path in sorted(self.runs_root.glob("*/definition.json"))
        ]
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        items = tuple(summaries[cursor : cursor + limit])
        end = cursor + len(items)
        next_cursor = end if end < len(summaries) else None
        return Phase27ArchiveRunPage(items=items, next_cursor=next_cursor)

    def read(self, run_id: str) -> Phase27ArchiveRunDetail:
        definition, projection = self._load_records(run_id)
        return Phase27ArchiveRunDetail(
            summary=self._summary(definition, projection),
            artifact_stages=tuple(
                stage for stage in PHASE27_STAGE_ORDER if stage in projection.artifact_refs
            ),
            pending_decisions=tuple(
                self._pending_decision(item) for item in projection.pending_decisions
            ),
            provider_usage=projection.provider_usage,
            failure=self._failure(projection.failure),
            events_available=self._event_path(run_id).exists(),
        )

    def events(
        self,
        run_id: str,
        *,
        after: int = 0,
        limit: int = 100,
    ) -> Phase27ArchiveEventPage:
        if after < 0 or not 1 <= limit <= 500:
            raise ValueError("Invalid archive event pagination")
        self._load_records(run_id)
        path = self._event_path(run_id)
        if not path.exists():
            return Phase27ArchiveEventPage(run_id=run_id, items=(), next_cursor=None)
        records = self._load_events(path, run_id)
        candidates = [item for item in records if item.sequence > after]
        selected = candidates[:limit]
        items = tuple(self._event(item) for item in selected)
        next_cursor = selected[-1].sequence if len(candidates) > len(selected) else None
        return Phase27ArchiveEventPage(
            run_id=run_id,
            items=items,
            next_cursor=next_cursor,
        )

    def reject_mutation(self, run_id: str) -> None:
        self._load_records(run_id)
        raise ArchiveRunReadOnlyError(f"Archived Run is read-only: {run_id}")

    def _load_summary(self, run_id: str) -> Phase27ArchiveRunSummary:
        definition, projection = self._load_records(run_id)
        return self._summary(definition, projection)

    def _load_records(
        self,
        run_id: str,
    ) -> tuple[_Phase27DefinitionRecord, _Phase27ReadModelRecord]:
        run_id = require_safe_id(run_id, label="run_id")
        directory = self.runs_root / run_id
        definition_payload = self._read_object(directory / "definition.json")
        architecture = definition_payload.get("architecture_version")
        if architecture != PHASE27_ARCHITECTURE_VERSION:
            raise Phase27ArchiveArchitectureError(
                f"Unsupported archived Run architecture: {architecture!r}"
            )
        read_model_payload = self._read_object(directory / "read_model.json")
        try:
            definition = _Phase27DefinitionRecord.model_validate(definition_payload)
            projection = _Phase27ReadModelRecord.model_validate(read_model_payload)
        except ValidationError as exc:
            raise Phase27ArchiveFormatError(
                f"Malformed Phase 27 archive record: {run_id}"
            ) from exc
        if definition.run_id != run_id or projection.run_id != run_id:
            raise Phase27ArchiveFormatError("Archive folder and Run identity differ")
        if definition.project_id != projection.project_id:
            raise Phase27ArchiveFormatError("Archive definition and projection differ")
        return definition, projection

    def _load_events(self, path: Path, run_id: str) -> list[_Phase27EventRecord]:
        records: list[_Phase27EventRecord] = []
        seen_event_ids: set[str] = set()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise Phase27ArchiveFormatError(
                f"Cannot read Phase 27 archive events: {run_id}"
            ) from exc
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                record = _Phase27EventRecord.model_validate_json(line)
            except ValidationError as exc:
                raise Phase27ArchiveFormatError(
                    f"Malformed Phase 27 event at line {line_number}: {run_id}"
                ) from exc
            expected_sequence = len(records) + 1
            if record.sequence != expected_sequence:
                raise Phase27ArchiveFormatError(
                    f"Phase 27 event sequence is not contiguous: {run_id}"
                )
            if record.run_id != run_id or record.thread_id != run_id:
                raise Phase27ArchiveFormatError(
                    f"Phase 27 event identity differs from its Run: {run_id}"
                )
            if record.event_id in seen_event_ids:
                raise Phase27ArchiveFormatError(
                    f"Phase 27 archive contains duplicate event ids: {run_id}"
                )
            seen_event_ids.add(record.event_id)
            records.append(record)
        return records

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(path.name)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Phase27ArchiveFormatError(f"Malformed archive JSON: {path.name}") from exc
        if not isinstance(payload, dict):
            raise Phase27ArchiveFormatError(
                f"Archive JSON root must be an object: {path.name}"
            )
        return payload

    def _event_path(self, run_id: str) -> Path:
        run_id = require_safe_id(run_id, label="run_id")
        return self.events_root / run_id / "events.jsonl"

    @staticmethod
    def _summary(
        definition: _Phase27DefinitionRecord,
        projection: _Phase27ReadModelRecord,
    ) -> Phase27ArchiveRunSummary:
        return Phase27ArchiveRunSummary(
            run_id=definition.run_id,
            project_id=definition.project_id,
            workflow_id=definition.workflow_id,
            workflow_revision=definition.workflow_revision,
            legacy_quality_mode=definition.quality_mode,
            status=projection.status,
            active_stage_id=projection.active_stage_id,
            active_chapter_number=projection.active_chapter_number,
            stage_status=projection.stage_status,
            created_at=definition.created_at,
            updated_at=projection.updated_at,
        )

    @staticmethod
    def _pending_decision(payload: dict[str, Any]) -> Phase27ArchivePendingDecision:
        decision_id = payload.get("decision_id")
        kind = payload.get("type")
        allowed_actions = payload.get("allowed_actions", [])
        if (
            not isinstance(decision_id, str)
            or not isinstance(kind, str)
            or not isinstance(allowed_actions, list)
            or not all(isinstance(item, str) for item in allowed_actions)
        ):
            raise Phase27ArchiveFormatError("Malformed Phase 27 pending decision")
        return Phase27ArchivePendingDecision(
            decision_id=decision_id,
            kind=kind,
            node_id=str(payload.get("node_id") or ""),
            artifact_available=bool(payload.get("artifact_ref")),
            allowed_actions=tuple(allowed_actions),
        )

    @staticmethod
    def _failure(payload: dict[str, Any] | None) -> Phase27ArchiveFailure | None:
        if payload is None:
            return None
        code = payload.get("code")
        if not isinstance(code, str) or not code:
            raise Phase27ArchiveFormatError("Malformed Phase 27 failure projection")
        message = str(payload.get("message") or "")
        return Phase27ArchiveFailure(
            code=code,
            node_id=str(payload.get("node_id") or ""),
            retryable=bool(payload.get("retryable", False)),
            message=message[:4_000],
            message_truncated=len(message) > 4_000,
        )

    @staticmethod
    def _event(record: _Phase27EventRecord) -> Phase27ArchiveEvent:
        return Phase27ArchiveEvent(
            event_id=record.event_id,
            sequence=record.sequence,
            occurred_at=record.occurred_at,
            type=record.type,
            stage_id=record.stage_id,
            node_id=record.node_id,
            chapter_id=record.chapter_id,
            status=record.status,
            has_payload=record.payload is not None,
            payload_ref=record.payload_ref,
            checkpoint_id=record.checkpoint_id,
        )


__all__ = [
    "ArchiveRunReadOnlyError",
    "Phase27ArchiveArchitectureError",
    "Phase27ArchiveCapabilities",
    "Phase27ArchiveEvent",
    "Phase27ArchiveEventPage",
    "Phase27ArchiveFormatError",
    "Phase27ArchivePendingDecision",
    "Phase27ArchiveProviderUsage",
    "Phase27ArchiveRunDetail",
    "Phase27ArchiveRunPage",
    "Phase27ArchiveRunReader",
    "Phase27ArchiveRunSummary",
]

from __future__ import annotations

from pydantic import BaseModel, Field


class SnapshotRestoreRequest(BaseModel):
    snapshot_id: str = Field(min_length=8, max_length=180)
    request_id: str = Field(min_length=8, max_length=160)
    expected_revision: int | None = Field(default=None, ge=0)


class RunHistoryItem(BaseModel):
    run_id: str
    project_id: str = ""
    title: str = "未命名小说"
    quality_mode: str = "balanced"
    status: str = "created"
    current_stage: dict[str, str] = Field(default_factory=dict)
    completed_stage_ids: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    words: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    summary: str = ""
    can_resume: bool = False
    recovery_required: bool = False
    latest_snapshot_id: str = ""
    export_ready: bool = False
    export_count: int = 0
    latest_export: dict[str, object] | None = None
    state_revision: int = 0


class ExportReceipt(BaseModel):
    export_id: str
    run_id: str
    request_id: str
    schema_version: int = 1
    version: int = 0
    snapshot_id: str = ""
    artifact_signature: str = ""
    selection_digest: str = ""
    selection_snapshot: dict[str, object] = Field(default_factory=dict)
    source_state_revision: int = 0
    source_state_digest: str = ""
    request_digest: str = ""
    format: str
    chapter_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    filename: str
    size_bytes: int = 0
    sha256: str = ""
    files: list[dict[str, object]] = Field(default_factory=list)
    cover_asset: dict[str, object] = Field(default_factory=dict)
    created_at: str = ""

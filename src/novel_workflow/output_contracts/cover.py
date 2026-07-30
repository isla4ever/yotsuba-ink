from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RequiredText = Annotated[str, Field(min_length=1)]


class CoverCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: RequiredText
    image_url: str = ""
    composition: RequiredText
    palette: str = ""
    quality_summary: RequiredText
    asset_status: Literal["planned", "generating", "ready", "failed", "blocked"] = "planned"
    asset_source: Literal["production", "fixture", "legacy"] = "legacy"
    generation_key: str = ""
    asset_id: str = ""
    mime_type: str = ""
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    size_bytes: int = Field(default=0, ge=0)
    sha256: str = ""
    provider_profile_id: str = ""
    model: str = ""
    attempt: int = Field(default=0, ge=0)
    error_code: str = ""
    error_message: str = ""

    @model_validator(mode="after")
    def validate_ready_asset(self) -> "CoverCandidate":
        if self.asset_status == "ready" and not self.image_url.strip():
            raise ValueError("image_url: ready asset requires a URL")
        return self


class CoverAssetGeneration(BaseModel):
    status: Literal["planned", "generating", "partial", "ready", "failed"] = "planned"
    total: int = Field(default=0, ge=0)
    ready_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    provider_profile_id: str = ""
    model: str = ""
    size: str = "1024x1536"
    quality: str = "medium"
    updated_at: str = ""


class CoverContract(BaseModel):
    brief: RequiredText
    visual_keywords: list[str] = Field(default_factory=list)
    composition: RequiredText
    copy_suggestions: list[str] = Field(default_factory=list)
    prompt: RequiredText
    candidates: list[CoverCandidate] = Field(min_length=1)
    selected_candidate_id: RequiredText
    asset_generation: CoverAssetGeneration = Field(default_factory=CoverAssetGeneration)

    @model_validator(mode="after")
    def validate_candidate_selection(self) -> "CoverContract":
        candidate_ids = [candidate.id.strip() for candidate in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidates: ids must be unique")
        if self.selected_candidate_id.strip() not in set(candidate_ids):
            raise ValueError("selected_candidate_id: must reference a candidate")
        return self

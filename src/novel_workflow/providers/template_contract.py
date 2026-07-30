from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from novel_workflow.workflows.schemas import ProviderKind


class ProviderTemplate(BaseModel):
    id: str = Field(min_length=1)
    label: str
    kind: ProviderKind
    base_url: str
    default_model: str
    model_options: list[str] = Field(default_factory=list)
    api_key_env: str
    docs_url: str
    integration_tier: Literal["official", "compatibility", "gateway", "custom"] = "official"
    description: str = ""
    supports_response_format: bool = True
    image_size_separator: Literal["x", ":"] = "x"
    image_size_field: Literal["size", "image_size", "resolution", "aspect_ratio", "width_height"] = "size"
    image_count_field: Literal["n", "images", "batch_size", "none"] = "n"
    image_response_field: Literal["data", "images"] = "data"
    image_endpoint_path: str = "/images/generations"
    models_endpoint_path: str = "/models"
    image_static_parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    supports_image_quality: bool = True
    max_retries: int = Field(default=2, ge=0, le=3)

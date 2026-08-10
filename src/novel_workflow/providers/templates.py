from __future__ import annotations

import math
import re
from fnmatch import fnmatchcase

from novel_workflow.providers.image_templates import IMAGE_PROVIDER_TEMPLATES
from novel_workflow.providers.template_contract import ProviderTemplate
from novel_workflow.providers.text_templates import TEXT_PROVIDER_TEMPLATES
from novel_workflow.workflows.schemas import ProviderKind


_TEMPLATES = (*TEXT_PROVIDER_TEMPLATES, *IMAGE_PROVIDER_TEMPLATES)
_BY_ID = {template.id: template for template in _TEMPLATES}


def list_provider_templates() -> list[ProviderTemplate]:
    return [template.model_copy(deep=True) for template in _TEMPLATES]


def provider_template(template_id: str, kind: ProviderKind) -> ProviderTemplate:
    template = _BY_ID.get(template_id)
    if template is None:
        raise ValueError(f"Unknown provider template: {template_id}")
    if template.kind != kind:
        raise ValueError(f"Provider template {template_id} does not support kind {kind}")
    return template


def require_provider_template(template_id: str, kind: ProviderKind) -> ProviderTemplate:
    template = _BY_ID.get(template_id)
    if template is None:
        raise ValueError(f"Unknown provider template: {template_id}")
    if template.kind != kind:
        raise ValueError(f"Provider template {template_id} does not support kind {kind}")
    return template


def openai_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    for endpoint in ("/chat/completions", "/images/generations", "/images"):
        if normalized.endswith(endpoint):
            normalized = normalized[: -len(endpoint)]
    return normalized


def image_request_parameters(
    template: ProviderTemplate,
    *,
    model: str,
    prompt: str,
    size: str,
    quality: str,
) -> dict[str, object]:
    width, height = _image_dimensions(size)
    capability = next(
        (
            item
            for item in template.image_model_capabilities
            if fnmatchcase(model.casefold(), item.model_pattern.casefold())
        ),
        None,
    )
    size_field = (
        capability.image_size_field
        if capability is not None and capability.image_size_field is not None
        else template.image_size_field
    )
    request: dict[str, object] = {"model": model, "prompt": prompt}
    if size_field == "width_height":
        request.update({"width": width, "height": height})
    elif size_field == "aspect_ratio":
        divisor = math.gcd(width, height)
        request["aspect_ratio"] = f"{width // divisor}:{height // divisor}"
    else:
        request[size_field] = f"{width}{template.image_size_separator}{height}"
    if template.image_count_field != "none":
        request[template.image_count_field] = 1
    if template.supports_image_quality and quality:
        request["quality"] = quality
    request.update(template.image_static_parameters)
    if capability is not None:
        request.update(capability.image_static_parameters)
    return request


def _image_dimensions(size: str) -> tuple[int, int]:
    parts = re.split(r"[x:*]", size.strip().lower())
    if len(parts) != 2:
        raise ValueError("Image size must contain width and height")
    try:
        width, height = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError("Image width and height must be integers") from exc
    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be positive")
    return width, height

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.storage.run_store_support import now


_SAFE_CANDIDATE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


@dataclass(frozen=True, slots=True)
class CoverGenerationConfig:
    provider_profile_id: str
    model: str
    size: str
    quality: str
    candidate_count: int
    estimated_cost_usd: float | None


def cover_generation_config(node: Any, state: Any, workflow: Any) -> CoverGenerationConfig:
    profile = next(
        (item for item in workflow.provider_profiles if item.id == node.image_provider_profile_id and item.kind == "openai-compatible-image"),
        None,
    )
    if profile is None:
        raise ValueError(f"Cover image provider is not configured: {node.image_provider_profile_id}")
    stage = ((state.inputs.get("stage_configs") or {}).get(node.id) or {}) if isinstance(state.inputs, dict) else {}
    aspect_ratio = str(stage.get("aspect_ratio") or "2:3")
    size = {"2:3": "1024x1536", "3:4": "1024x1365", "1:1": "1024x1024"}.get(aspect_ratio, "1024x1536")
    return CoverGenerationConfig(
        provider_profile_id=profile.id,
        model=str(stage.get("image_model") or profile.default_model),
        size=str(stage.get("image_size") or size),
        quality=str(stage.get("image_quality") or "medium"),
        candidate_count=max(1, min(4, _integer(stage.get("candidate_count"), 3))),
        estimated_cost_usd=profile.estimated_cost_per_output_usd,
    )


def prepare_cover_artifact(raw: Any, config: CoverGenerationConfig) -> dict[str, Any]:
    validation = validate_stage_artifact("cover_image", raw)
    if not validation.valid or not isinstance(validation.artifact, dict):
        raise ValueError("; ".join(validation.errors) or "封面规划 Artifact 无效")
    artifact = copy.deepcopy(validation.artifact)
    original_candidates = list(artifact.get("candidates") or [])
    selected_original = str(artifact.get("selected_candidate_id") or "")
    candidates: list[dict[str, Any]] = []
    id_map: dict[str, str] = {}
    for index in range(config.candidate_count):
        source = copy.deepcopy(original_candidates[index % len(original_candidates)])
        source_id = str(source.get("id") or "")
        candidate_id = source_id if index < len(original_candidates) and _SAFE_CANDIDATE_ID.fullmatch(source_id) else f"cover-{index + 1:02d}"
        while any(item["id"] == candidate_id for item in candidates):
            candidate_id = f"cover-{index + 1:02d}"
        if index < len(original_candidates):
            id_map[source_id] = candidate_id
        source.update({
            "id": candidate_id,
            "image_url": "",
            "asset_status": "planned",
            "asset_source": "production",
            "generation_key": "",
            "asset_id": "",
            "mime_type": "",
            "width": 0,
            "height": 0,
            "size_bytes": 0,
            "sha256": "",
            "provider_profile_id": config.provider_profile_id,
            "model": config.model,
            "attempt": 0,
            "error_code": "",
            "error_message": "",
        })
        candidates.append(source)
    artifact["candidates"] = candidates
    artifact["selected_candidate_id"] = id_map.get(selected_original, candidates[0]["id"])
    artifact["asset_generation"] = {
        "status": "planned",
        "total": len(candidates),
        "ready_count": 0,
        "failed_count": 0,
        "provider_profile_id": config.provider_profile_id,
        "model": config.model,
        "size": config.size,
        "quality": config.quality,
        "updated_at": now(),
    }
    return artifact


def candidate_generation_key(
    run_id: str,
    node_id: str,
    artifact: dict[str, Any],
    candidate: dict[str, Any],
    config: CoverGenerationConfig,
    attempt: int,
) -> str:
    payload = {
        "run_id": run_id,
        "node_id": node_id,
        "candidate_id": candidate["id"],
        "prompt": artifact.get("prompt"),
        "composition": candidate.get("composition"),
        "palette": candidate.get("palette"),
        "provider_profile_id": config.provider_profile_id,
        "model": config.model,
        "size": config.size,
        "quality": config.quality,
        "attempt": attempt,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def candidate_image_prompt(artifact: dict[str, Any], candidate: dict[str, Any]) -> str:
    keywords = ", ".join(str(item) for item in artifact.get("visual_keywords") or [] if str(item).strip())
    return "\n".join(filter(None, [
        str(artifact.get("prompt") or "").strip(),
        f"Candidate composition: {str(candidate.get('composition') or artifact.get('composition') or '').strip()}",
        f"Palette: {str(candidate.get('palette') or '').strip()}",
        f"Visual keywords: {keywords}" if keywords else "",
        "Create a complete portrait novel-cover image. Keep a calm title-safe area, but do not render readable title text, logos, watermarks, UI, or mockup frames.",
    ]))


def apply_asset_metadata(candidate: dict[str, Any], metadata: dict[str, Any]) -> None:
    candidate.update({
        "image_url": metadata["image_url"],
        "asset_status": "ready",
        "asset_source": "production",
        "asset_id": metadata["asset_id"],
        "mime_type": metadata["mime_type"],
        "width": metadata["width"],
        "height": metadata["height"],
        "size_bytes": metadata["size_bytes"],
        "sha256": metadata["sha256"],
        "error_code": "",
        "error_message": "",
    })


def refresh_cover_generation(artifact: dict[str, Any], config: CoverGenerationConfig) -> dict[str, int]:
    candidates = artifact.get("candidates") or []
    ready = [item for item in candidates if item.get("asset_status") == "ready" and str(item.get("image_url") or "").strip()]
    failed = [item for item in candidates if item.get("asset_status") in {"failed", "blocked"}]
    if len(ready) == len(candidates):
        status = "ready"
    elif ready:
        status = "partial"
    elif len(failed) == len(candidates):
        status = "failed"
    elif any(item.get("asset_status") == "generating" for item in candidates):
        status = "generating"
    else:
        status = "planned"
    ready_provider_ids = {str(item.get("provider_profile_id") or "") for item in ready if item.get("provider_profile_id")}
    ready_models = {str(item.get("model") or "") for item in ready if item.get("model")}
    artifact["asset_generation"] = {
        "status": status,
        "total": len(candidates),
        "ready_count": len(ready),
        "failed_count": len(failed),
        "provider_profile_id": next(iter(ready_provider_ids)) if len(ready_provider_ids) == 1 else "mixed" if ready_provider_ids else config.provider_profile_id,
        "model": next(iter(ready_models)) if len(ready_models) == 1 else "mixed" if ready_models else config.model,
        "size": config.size,
        "quality": config.quality,
        "updated_at": now(),
    }
    if ready and not any(item.get("id") == artifact.get("selected_candidate_id") for item in ready):
        artifact["selected_candidate_id"] = ready[0]["id"]
    return {"ready_count": len(ready), "failed_count": len(failed), "total": len(candidates)}


def _integer(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback

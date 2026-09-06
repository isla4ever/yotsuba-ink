from __future__ import annotations

from copy import deepcopy
from typing import Any

from novel_workflow.providers.frozen_contract import prompt_digest, schema_digest
from novel_workflow.providers.structured_tasks import contract_for_task
from novel_workflow.quality.narrative_contracts import dramatic_endpoints_for_text
from novel_workflow.quality.custody_contracts import (
    project_superseded_custody_history_text,
    text_assumes_custody,
)
from novel_workflow.runtime.graph.evidence_candidates import build_chapter_evidence_candidates
from novel_workflow.runtime.graph.provider_contract_compiler import (
    schema_for_proposal,
    schema_for_review_role,
    schema_for_stage,
    schema_with_frozen_context_bounds,
    validate_frozen_structured_task,
)
from novel_workflow.runtime.graph.provider_prompt_compiler import (
    render_structured_prompt,
    render_text_prompt,
)
from novel_workflow.runtime.graph.provider_requests import (
    ChapterEvidenceRequest,
    ChapterSceneGenerationRequest,
    ChapterReviewRequest,
    ProposalGenerationRequest,
    ProviderRequest,
    StageGenerationRequest,
)
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.storage.provider_input_store import (
    ProviderInputPayload,
    ProviderOutputContract,
)


def compile_provider_input(request: ProviderRequest) -> ProviderInputPayload:
    """Compile the deterministic, secret-free input that the Provider will see."""

    if isinstance(request, StageGenerationRequest):
        return _structured_provider_input(
            request,
            stage_id=request.stage_id,
            task_name=request.stage_id,
            frozen_task_name=request.stage_id,
            schema=schema_for_stage(request.stage_id),
            context=request.context,
        )
    if isinstance(request, ProposalGenerationRequest):
        schema, _ = schema_for_proposal(request.proposal_type)
        task_name = f"{request.proposal_type}.proposal"
        return _structured_provider_input(
            request,
            stage_id=request.stage_id,
            task_name=task_name,
            frozen_task_name=task_name,
            schema=schema,
            context=request.context,
        )
    if isinstance(request, ChapterReviewRequest):
        return _structured_provider_input(
            request,
            stage_id="text",
            task_name="text.review",
            frozen_task_name=f"text.review.{request.role}",
            schema=schema_for_review_role(request.role),
            context=request.context,
        )
    if isinstance(request, ChapterEvidenceRequest):
        context = {
            "chapter_id": request.chapter_id,
            "chapter_version_id": request.chapter_version_id,
            "frozen_state": request.context,
            "evidence_candidates": [
                candidate.prompt_payload()
                for candidate in build_chapter_evidence_candidates(request.content)
            ],
        }
        return _structured_provider_input(
            request,
            stage_id="text",
            task_name="text.evidence",
            frozen_task_name="text.evidence",
            schema=contract_for_task("text.evidence").schema,
            context=context,
        )
    if isinstance(request, ChapterSceneGenerationRequest):
        plain_text_contract = (
            "One bounded replacement passage for the masked rejected scene segment; "
            "no full-scene rewrite, heading, JSON, Markdown, metadata, analysis, or commentary."
            if request.mode == "fact_repair"
            else (
                "One complete scene segment as plain prose only; no scene heading, JSON, "
                "Markdown fences, metadata, analysis, commentary, or truncation."
            )
        )
        return ProviderInputPayload(
            stage_id="text",
            task_name="text.scene",
            attempt=request.scene_attempt,
            chapter_id=request.chapter_id,
            provider_binding=_secret_free_binding(request.binding),
            prompt_template_id=request.binding.prompt_template_id,
            prompt_digest=request.binding.prompt_digest,
            rendered_prompt=render_text_prompt(request.binding, request.context),
            structured_context=request.context,
            output_contract=ProviderOutputContract(
                kind="plain_text",
                plain_text_contract=plain_text_contract,
            ),
        )
    binding = request.binding
    return ProviderInputPayload(
        stage_id="cover",
        task_name="cover.image",
        attempt=request.generation_attempt,
        provider_binding=_secret_free_binding(binding),
        prompt_template_id="cover-image-prompt",
        prompt_digest=prompt_digest(request.prompt),
        rendered_prompt=request.prompt,
        structured_context={
            "candidate_index": request.candidate_index,
            "generation_attempt": request.generation_attempt,
        },
        output_contract=ProviderOutputContract(
            kind="image",
            image_contract={
                "model": binding.model,
                "size": binding.size,
                "quality": binding.quality,
                "timeout_seconds": binding.timeout_seconds,
            },
        ),
    )


def _structured_provider_input(
    request: StageGenerationRequest | ProposalGenerationRequest | ChapterReviewRequest | ChapterEvidenceRequest,
    *,
    stage_id: str,
    task_name: str,
    frozen_task_name: str,
    schema: dict[str, Any],
    context: dict[str, Any],
) -> ProviderInputPayload:
    binding = request.binding
    validate_frozen_structured_task(
        binding,
        frozen_task_name=frozen_task_name,
        provider_task_name=task_name,
        schema=schema,
    )
    provider_context = _provider_visible_structured_context(
        frozen_task_name,
        context,
    )
    effective_schema = schema_with_frozen_context_bounds(
        frozen_task_name,
        schema,
        provider_context,
    )
    frozen = binding.structured_tasks[frozen_task_name]
    return ProviderInputPayload(
        stage_id=stage_id,
        task_name=task_name,
        attempt=request.attempt,
        chapter_id=str(getattr(request, "chapter_id", "")),
        chapter_version_id=str(getattr(request, "chapter_version_id", "")),
        provider_binding=_secret_free_binding(binding),
        prompt_template_id=binding.prompt_template_id,
        prompt_digest=binding.prompt_digest,
        rendered_prompt=render_structured_prompt(
            binding,
            task_name,
            provider_context,
            effective_schema,
        ),
        structured_context=provider_context,
        output_contract=ProviderOutputContract(
            kind="structured_json",
            json_schema_contract=effective_schema,
            schema_digest=schema_digest(effective_schema),
            structured_mode=frozen.effective_mode,
        ),
    )


def _provider_visible_structured_context(
    task_name: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    if task_name != "detail":
        return context
    material = context.get("material")
    recovery = material.get("recovery_source") if isinstance(material, dict) else None
    feedback = material.get("preflight_feedback") if isinstance(material, dict) else None
    if not isinstance(recovery, dict) or not isinstance(feedback, dict):
        return context

    projected = deepcopy(context)
    projected_material = projected["material"]
    projected_recovery = projected_material["recovery_source"]
    projected_material.pop("volume_spine_turns", None)
    projected_feedback = projected_material["preflight_feedback"]
    if isinstance(projected_feedback.get("blockers"), list):
        projected_feedback["blockers"] = [
            {
                key: value
                for key, value in item.items()
                if key in {"code", "chapter_refs", "required_fix"}
            }
            for item in projected_feedback["blockers"]
            if isinstance(item, dict)
        ]
    source_segment = recovery.get("source_segment")
    source_chapters = (
        source_segment.get("chapters") if isinstance(source_segment, dict) else None
    )
    chapter_refs = recovery.get("chapter_refs")
    editable_refs = recovery.get("editable_chapter_refs")
    if not isinstance(source_chapters, list) or not isinstance(chapter_refs, list):
        raise ValueError("Detail recovery Provider projection requires a source segment")
    if not isinstance(editable_refs, list) or not editable_refs:
        raise ValueError("Detail recovery Provider projection requires editable chapter refs")
    if len(source_chapters) != len(chapter_refs):
        raise ValueError("Detail recovery Provider projection source refs do not align")

    scale_projection = projected_material.get("scale_projection")
    if isinstance(scale_projection, dict) and isinstance(
        scale_projection.get("chapter_beats"),
        list,
    ):
        segment_start = int(scale_projection.get("chapter_number_start") or 0)
        editable_numbers = {
            int(str(chapter_ref).removeprefix("chapter-"))
            for chapter_ref in editable_refs
        }
        custody_contracts = projected_recovery.get("custody_repair_contracts") or {}
        visible_beats = [
            deepcopy(beat)
            for beat in scale_projection["chapter_beats"]
            if isinstance(beat, dict)
            and segment_start + int(beat.get("chapter_offset") or 0) - 1
            in editable_numbers
        ]
        for beat in visible_beats:
            chapter_number = segment_start + int(beat.get("chapter_offset") or 0) - 1
            custody_contract = custody_contracts.get(f"chapter-{chapter_number}")
            if isinstance(custody_contract, dict):
                beat["dramatic_job"] = str(
                    custody_contract.get("preserved_dramatic_task") or ""
                )
        scale_projection["chapter_beats"] = visible_beats

    source_by_ref = dict(zip(chapter_refs, source_chapters, strict=True))
    dossiers = [
        item
        for item in projected_material.get("selected_dossiers") or []
        if isinstance(item, dict)
    ]
    dossier_names = {
        str(item.get("id") or ""): str(item.get("name") or "").strip()
        for item in dossiers
    }
    visible_chapters = []
    for chapter_ref in editable_refs:
        chapter = source_by_ref.get(chapter_ref)
        if not isinstance(chapter, dict):
            raise ValueError(
                f"Detail recovery Provider projection is missing {chapter_ref}"
            )
        forbidden = set(
            (recovery.get("required_removed_endpoints") or {}).get(chapter_ref) or []
        )
        custody_repair = (recovery.get("custody_repair_contracts") or {}).get(
            chapter_ref
        )
        source_patch: dict[str, Any] = {}
        omitted_fields: list[str] = []
        for field in ("purpose", "handoff"):
            value = str(chapter.get(field) or "")
            if forbidden & dramatic_endpoints_for_text(value) or (
                isinstance(custody_repair, dict) and text_assumes_custody(value)
            ):
                omitted_fields.append(field)
            else:
                source_patch[field] = value
        visible_scenes = []
        omitted_scene_indexes = []
        for index, scene in enumerate(chapter.get("scenes") or [], start=1):
            if not isinstance(scene, dict):
                raise ValueError("Detail recovery source scene must be structured")
            scene_text = " ".join(str(scene.get(key) or "") for key in scene)
            if forbidden & dramatic_endpoints_for_text(scene_text) or (
                isinstance(custody_repair, dict) and text_assumes_custody(scene_text)
            ):
                omitted_scene_indexes.append(index)
            else:
                visible_scenes.append(scene)
        source_patch["scenes"] = visible_scenes
        cast_ids = [str(item) for item in chapter.get("cast_ids") or []]
        visible_chapter = {
            "chapter_ref": chapter_ref,
            "frozen_pov": str(chapter.get("pov") or ""),
            "frozen_cast_ids": cast_ids,
            "frozen_cast_names": [
                dossier_names[subject_id]
                for subject_id in cast_ids
                if dossier_names.get(subject_id)
            ],
            "source_patch": source_patch,
            "omitted_source_fields": omitted_fields,
            "omitted_source_scene_indexes": omitted_scene_indexes,
        }
        frozen_title = str(chapter.get("title") or "")
        if not (
            isinstance(custody_repair, dict) and text_assumes_custody(frozen_title)
        ):
            visible_chapter["frozen_title"] = frozen_title
        visible_chapters.append(visible_chapter)

    projected_recovery.pop("source_segment", None)
    projected_recovery["editable_source_chapters"] = visible_chapters
    actionable_cast_ids = {
        subject_id
        for chapter in visible_chapters
        for subject_id in chapter["frozen_cast_ids"]
    }
    visible_source_patches = [
        chapter["source_patch"] for chapter in visible_chapters
    ]
    reference_only_ids = {
        str(item.get("id") or "")
        for item in dossiers
        if item.get("kind") == "historical_record"
        and _structured_value_contains(
            visible_source_patches,
            str(item.get("name") or "").strip(),
        )
    }
    visible_dossiers = []
    has_custody_repair = bool(
        projected_recovery.get("custody_repair_contracts")
    )
    for dossier in dossiers:
        subject_id = str(dossier.get("id") or "")
        if subject_id not in actionable_cast_ids | reference_only_ids:
            continue
        visible_dossier = deepcopy(dossier)
        if has_custody_repair:
            visible_dossier = {
                key: value
                for key, value in visible_dossier.items()
                if key in {"id", "name", "kind", "debut"}
                or not _structured_value_assumes_custody(value)
            }
        if subject_id in reference_only_ids:
            visible_dossier["reference_only"] = True
        visible_dossiers.append(visible_dossier)
    projected_material["selected_dossiers"] = visible_dossiers
    projected_material["present_actor_ids"] = [
        str(item.get("id") or "")
        for item in visible_dossiers
        if item.get("kind") != "historical_record"
        and str(item.get("id") or "") in actionable_cast_ids
    ]
    projected_material["historical_record_ids"] = [
        str(item.get("id") or "")
        for item in visible_dossiers
        if item.get("kind") == "historical_record"
    ]
    if isinstance(projected_material.get("debut_requirements"), list):
        projected_material["debut_requirements"] = [
            item
            for item in projected_material["debut_requirements"]
            if isinstance(item, dict)
            and str(item.get("subject_id") or "") in actionable_cast_ids
        ]
    if has_custody_repair:
        _remove_superseded_custody_history(
            projected_material,
            projected_recovery["custody_repair_contracts"],
        )
    return projected


def _structured_value_assumes_custody(value: Any) -> bool:
    if isinstance(value, str):
        return text_assumes_custody(value)
    if isinstance(value, dict):
        return any(_structured_value_assumes_custody(item) for item in value.values())
    if isinstance(value, list):
        return any(_structured_value_assumes_custody(item) for item in value)
    return False


def _remove_superseded_custody_history(
    material: dict[str, Any],
    custody_contracts: dict[str, Any],
) -> None:
    """Keep the adjacent state authority and hide older contradictory custody prose."""

    handoff = material.get("previous_segment_handoff")
    if not isinstance(handoff, dict):
        return
    previous_refs = {
        str(contract.get("previous_chapter_ref") or "")
        for contract in custody_contracts.values()
        if isinstance(contract, dict)
    }
    established = handoff.get("established_chapters")
    if not isinstance(established, list):
        return
    projected_chapters = []
    for chapter in established:
        if (
            not isinstance(chapter, dict)
            or str(chapter.get("chapter_ref") or "") in previous_refs
        ):
            projected_chapters.append(chapter)
            continue
        projected = deepcopy(chapter)
        for field in ("purpose", "final_result"):
            value = projected.get(field)
            if not isinstance(value, str):
                continue
            sanitized = project_superseded_custody_history_text(value)
            if sanitized != value:
                if sanitized:
                    projected[field] = sanitized
                else:
                    projected.pop(field, None)
        projected_chapters.append(projected)
    handoff["established_chapters"] = projected_chapters


def _structured_value_contains(value: Any, needle: str) -> bool:
    if not needle:
        return False
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(_structured_value_contains(item, needle) for item in value.values())
    if isinstance(value, list):
        return any(_structured_value_contains(item, needle) for item in value)
    return False


def _secret_free_binding(binding: ProviderBinding | CoverAssetBinding) -> dict[str, Any]:
    return _without_secret_or_header_config(binding.model_dump(mode="json"))


def secret_free_provider_binding(
    binding: ProviderBinding | CoverAssetBinding,
) -> dict[str, Any]:
    """Public compiler boundary for secret-free sidecar Provider snapshots."""

    return _secret_free_binding(binding)


def _without_secret_or_header_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_secret_or_header_config(item)
            for key, item in value.items()
            if not _is_secret_or_header_key(key)
        }
    if isinstance(value, list):
        return [_without_secret_or_header_config(item) for item in value]
    return value


def _is_secret_or_header_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized
        in {
            "api_key",
            "authorization",
            "header",
            "headers",
            "secret",
            "secret_ref",
        }
        or normalized.endswith("_header")
        or normalized.endswith("_headers")
    )


__all__ = ["compile_provider_input", "secret_free_provider_binding"]

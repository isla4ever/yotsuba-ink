from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterRelationBatch,
    DetailLayoutProposalBatch,
    RoleDemandProposalBatch,
    VolumeBoundaryProposalBatch,
)
from novel_workflow.providers.frozen_contract import schema_digest
from novel_workflow.output_contracts.provider_tasks import (
    CastDossierSemanticReviewResult,
    DetailRecoveryPatch,
    RoleDemandSemanticReviewResult,
    SpineSemanticReviewResult,
)
from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.providers.structured_schema import structured_format_decision
from novel_workflow.providers.structured_tasks import contract_for_task
from novel_workflow.runtime.graph.provider_requests import ProviderOperationError
from novel_workflow.storage.narrative_run_repository import ProviderBinding


def validate_frozen_structured_task(
    binding: ProviderBinding,
    *,
    frozen_task_name: str,
    provider_task_name: str,
    schema: dict[str, Any],
) -> None:
    frozen = binding.structured_tasks.get(frozen_task_name)
    if frozen is None:
        raise ProviderOperationError(
            f"Frozen structured task is missing: {frozen_task_name}",
            diagnostic={"code": "structured_task_missing"},
        )
    if frozen.schema_digest != schema_digest(schema):
        raise ProviderOperationError(
            f"Structured schema changed after Run creation: {frozen_task_name}",
            diagnostic={"code": "schema_digest_mismatch"},
        )
    policy = resolve_request_policy(
        binding.provider_template,
        model=binding.model,
        task_name=provider_task_name,
    )
    decision = (
        structured_format_decision(
            policy,
            task_name=provider_task_name,
            schema=schema,
        )
        if binding.provider_template.supports_response_format
        else None
    )
    effective_mode = decision.effective_mode if decision is not None else "prompt_only"
    if effective_mode != frozen.effective_mode:
        raise ProviderOperationError(
            f"Structured output mode changed after Run creation: {frozen_task_name}",
            diagnostic={"code": "structured_mode_mismatch"},
        )


def schema_for_stage(stage_id: str) -> dict[str, Any]:
    return contract_for_task(stage_id).schema


def schema_for_proposal(
    proposal_type: Literal[
        "role_demand",
        "role_demand_review",
        "spine_review",
        "cast_review",
        "cast_relation",
        "volume_boundary",
        "detail_layout",
    ],
) -> tuple[dict[str, Any], type[BaseModel]]:
    if proposal_type == "role_demand":
        return contract_for_task("role_demand.proposal").schema, RoleDemandProposalBatch
    if proposal_type == "role_demand_review":
        return (
            contract_for_task("role_demand_review.proposal").schema,
            RoleDemandSemanticReviewResult,
        )
    if proposal_type == "spine_review":
        return contract_for_task("spine_review.proposal").schema, SpineSemanticReviewResult
    if proposal_type == "cast_review":
        return (
            contract_for_task("cast_review.proposal").schema,
            CastDossierSemanticReviewResult,
        )
    if proposal_type == "cast_relation":
        return contract_for_task("cast_relation.proposal").schema, CharacterRelationBatch
    if proposal_type == "volume_boundary":
        return contract_for_task("volume_boundary.proposal").schema, VolumeBoundaryProposalBatch
    return contract_for_task("detail_layout.proposal").schema, DetailLayoutProposalBatch


def schema_for_review_role(role: str) -> dict[str, Any]:
    return contract_for_task(f"text.review.{role}").schema


def schema_with_frozen_context_bounds(
    task_name: str,
    schema: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Bind code-owned per-operation array sizes into the Provider schema.

    Provider bindings freeze the base task shape. Exact Run scale and unit sizes
    become known later from immutable stage context, so their derived bounds are
    signed with the operation input instead of mutating the frozen binding.
    """

    effective = deepcopy(schema)
    material = context.get("material")
    if not isinstance(material, dict):
        return effective

    if task_name == "spine":
        scale_plan = _required_dict(material, "scale_plan", task_name)
        turn_target = _required_positive_int(scale_plan, "turn_target", task_name)
        _set_array_bounds(
            effective,
            ("properties", "turns"),
            turn_target,
            turn_target,
        )
    elif task_name == "role_demand.proposal":
        scale_plan = _required_dict(material, "scale_plan", task_name)
        recommended_min, _ = _required_range(
            scale_plan,
            "cast_recommended_range",
            task_name,
        )
        hard_max = _required_positive_int(scale_plan, "cast_hard_max", task_name)
        if recommended_min > hard_max:
            raise ValueError("Role demand Provider schema cast range exceeds its hard maximum")
        _set_array_bounds(
            effective,
            ("properties", "proposals"),
            recommended_min,
            hard_max,
        )
    elif task_name == "cast":
        subject_count = len(_required_list(material, "subject_refs", task_name))
        if subject_count < 1:
            raise ValueError("Cast Provider schema requires at least one frozen subject ref")
        _set_array_bounds(
            effective,
            ("properties", "subjects"),
            subject_count,
            subject_count,
        )
    elif task_name == "volume_boundary.proposal":
        scale_plan = _required_dict(material, "scale_plan", task_name)
        volume_target = _required_positive_int(scale_plan, "volume_target", task_name)
        _set_array_bounds(
            effective,
            ("properties", "proposals"),
            volume_target,
            volume_target,
        )
    elif task_name == "detail_layout.proposal":
        slot_count = len(_required_list(material, "chapter_slots", task_name))
        if slot_count < 1:
            raise ValueError("Detail layout Provider schema requires frozen chapter slots")
        _set_array_bounds(
            effective,
            ("$defs", "DetailLayoutVolumeProposal", "properties", "chapters"),
            slot_count,
            slot_count,
        )
    elif task_name == "detail":
        scale_projection = _required_dict(material, "scale_projection", task_name)
        chapter_target = _required_positive_int(
            scale_projection,
            "chapter_target",
            task_name,
        )
        recovery_source = material.get("recovery_source")
        chapter_definition = "DetailSegmentChapter"
        if recovery_source is not None:
            if not isinstance(recovery_source, dict):
                raise ValueError("Detail recovery source must be structured")
            editable_refs = _required_list(
                recovery_source,
                "editable_chapter_refs",
                "detail recovery",
            )
            if not editable_refs or len(editable_refs) != len(set(editable_refs)):
                raise ValueError(
                    "Detail recovery requires distinct editable chapter refs"
                )
            chapter_target = len(editable_refs)
            effective = DetailRecoveryPatch.model_json_schema()
            chapter_definition = "DetailRecoveryChapterPatch"
        scene_min = _required_positive_int(
            scale_projection,
            "scenes_per_chapter_min",
            task_name,
        )
        scene_max = _required_positive_int(
            scale_projection,
            "scenes_per_chapter_max",
            task_name,
        )
        if scene_min > scene_max:
            raise ValueError("Detail Provider schema scene range is inverted")
        _set_array_bounds(
            effective,
            ("properties", "chapters"),
            chapter_target,
            chapter_target,
        )
        _set_array_bounds(
            effective,
            ("$defs", chapter_definition, "properties", "scenes"),
            scene_min,
            scene_max,
        )
    return effective


def _required_dict(container: dict[str, Any], key: str, task_name: str) -> dict[str, Any]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{task_name} Provider schema requires frozen {key}")
    return value


def _required_list(container: dict[str, Any], key: str, task_name: str) -> list[Any]:
    value = container.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{task_name} Provider schema requires frozen {key}")
    return value


def _required_positive_int(container: dict[str, Any], key: str, task_name: str) -> int:
    value = container.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{task_name} Provider schema requires positive {key}")
    return value


def _required_range(
    container: dict[str, Any],
    key: str,
    task_name: str,
) -> tuple[int, int]:
    value = container.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{task_name} Provider schema requires a two-item {key}")
    minimum, maximum = value
    if (
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or minimum < 1
        or minimum > maximum
    ):
        raise ValueError(f"{task_name} Provider schema has an invalid {key}")
    return minimum, maximum


def _set_array_bounds(
    schema: dict[str, Any],
    path: tuple[str, ...],
    minimum: int,
    maximum: int,
) -> None:
    node: Any = schema
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise ValueError(f"Structured Provider schema is missing {'/'.join(path)}")
        node = node[key]
    if not isinstance(node, dict) or node.get("type") != "array":
        raise ValueError(f"Structured Provider schema path is not an array: {'/'.join(path)}")
    node["minItems"] = minimum
    node["maxItems"] = maximum


__all__ = [
    "schema_for_proposal",
    "schema_for_review_role",
    "schema_for_stage",
    "schema_with_frozen_context_bounds",
    "validate_frozen_structured_task",
]

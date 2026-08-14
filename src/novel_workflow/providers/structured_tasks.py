from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from novel_workflow.output_contracts.artifacts_vnext import (
    ARTIFACT_MODELS,
    CharacterDossierBatch,
    CharacterRelationBatch,
    CoverBrief,
    DetailSegmentArtifact,
    RoleDemandProposalBatch,
    StorySpineDraftArtifact,
    VolumeArchitectureDraftArtifact,
    VolumeBoundaryProposalBatch,
)
from novel_workflow.providers.frozen_contract import schema_digest
from novel_workflow.output_contracts.provider_tasks import (
    ChapterEvidenceResult,
    ChapterReviewResult,
)


@dataclass(frozen=True, slots=True)
class StructuredTaskContract:
    name: str
    provider_task_name: str
    schema: dict[str, Any]


def structured_task_contracts_for_stage(stage_id: str) -> tuple[StructuredTaskContract, ...]:
    """Return every strict JSON task executed under one Phase 27 stage binding."""

    if stage_id == "brief":
        return (_contract("brief", ARTIFACT_MODELS["brief"]),)
    if stage_id == "spine":
        return (
            _contract("spine", StorySpineDraftArtifact),
            _contract("role_demand.proposal", RoleDemandProposalBatch),
        )
    if stage_id == "cast":
        return (
            _contract("cast", CharacterDossierBatch),
            _contract("cast_relation.proposal", CharacterRelationBatch),
        )
    if stage_id == "volumes":
        return (
            _contract("volumes", VolumeArchitectureDraftArtifact),
            _contract("volume_boundary.proposal", VolumeBoundaryProposalBatch),
        )
    if stage_id == "detail":
        return (_contract("detail", DetailSegmentArtifact),)
    if stage_id == "text":
        return (
            _review_contract("continuity"),
            _review_contract("character"),
            _review_contract("prose"),
            _contract("text.evidence", ChapterEvidenceResult),
        )
    if stage_id == "cover":
        return (_contract("cover", CoverBrief),)
    raise ValueError(f"No structured task contracts for stage {stage_id}")


def contract_for_task(task_name: str) -> StructuredTaskContract:
    for contract in _all_contracts():
        if contract.name == task_name:
            return contract
    raise ValueError(f"Unknown structured Provider task: {task_name}")


def task_schema_digest(task_name: str) -> str:
    return schema_digest(contract_for_task(task_name).schema)


def _all_contracts() -> Iterable[StructuredTaskContract]:
    for stage_id in ("brief", "spine", "cast", "volumes", "detail", "text", "cover"):
        yield from structured_task_contracts_for_stage(stage_id)


def _contract(name: str, model: type[BaseModel]) -> StructuredTaskContract:
    return StructuredTaskContract(
        name=name,
        provider_task_name=name,
        schema=model.model_json_schema(),
    )


def _review_contract(role: str) -> StructuredTaskContract:
    return StructuredTaskContract(
        name=f"text.review.{role}",
        provider_task_name="text.review",
        schema=_review_schema_for_role(role),
    )


def _review_schema_for_role(role: str) -> dict[str, Any]:
    schema = ChapterReviewResult.model_json_schema()
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not isinstance(properties.get("role"), dict):
        raise RuntimeError("Chapter review schema is missing its role property")
    properties["role"] = {**properties["role"], "const": role}
    return schema


__all__ = [
    "StructuredTaskContract",
    "contract_for_task",
    "structured_task_contracts_for_stage",
    "task_schema_digest",
]

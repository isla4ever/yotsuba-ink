from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile


BudgetKind = Literal[
    "brief",
    "spine",
    "cast_dossier",
    "volumes",
    "detail",
    "cover",
    "role_demand",
    "cast_relation",
    "volume_boundary",
    "text",
    "review",
    "evidence",
]


class OutputBudgetExceeded(ValueError):
    """The frozen Provider ceiling cannot hold the predicted response unit."""


class OutputBudgetPlan(BaseModel):
    """Request sidecar describing one response envelope, never an Artifact field."""

    model_config = ConfigDict(extra="forbid")

    kind: BudgetKind
    expected_items: int = Field(ge=1)
    item_cap: int = Field(ge=1)
    field_char_cap: int = Field(ge=1)
    estimated_chars: int = Field(ge=1)
    max_tokens: int = Field(ge=1)
    scene_cap: int | None = Field(default=None, ge=1)

    def bind(self, binding: ProviderBinding) -> ProviderBinding:
        return binding.model_copy(update={"max_tokens": self.max_tokens})

    def sidecar(self) -> dict[str, int | str]:
        values: dict[str, int | str] = {
            "kind": self.kind,
            "expected_items": self.expected_items,
            "item_cap": self.item_cap,
            "field_char_cap": self.field_char_cap,
            "max_tokens": self.max_tokens,
        }
        if self.scene_cap is not None:
            values["scene_cap"] = self.scene_cap
        return values


@dataclass(frozen=True, slots=True)
class _Shape:
    fixed_chars: int
    item_chars: int
    minimum_tokens: int


_SHAPES: dict[BudgetKind, _Shape] = {
    "brief": _Shape(fixed_chars=1_800, item_chars=1, minimum_tokens=2_400),
    "spine": _Shape(fixed_chars=900, item_chars=300, minimum_tokens=2_400),
    "cast_dossier": _Shape(fixed_chars=320, item_chars=760, minimum_tokens=1_800),
    "volumes": _Shape(fixed_chars=300, item_chars=980, minimum_tokens=1_800),
    "detail": _Shape(fixed_chars=320, item_chars=1_620, minimum_tokens=2_400),
    "cover": _Shape(fixed_chars=1_500, item_chars=1, minimum_tokens=1_800),
    "role_demand": _Shape(fixed_chars=260, item_chars=300, minimum_tokens=1_600),
    "cast_relation": _Shape(fixed_chars=220, item_chars=230, minimum_tokens=1_400),
    "volume_boundary": _Shape(fixed_chars=220, item_chars=240, minimum_tokens=1_400),
    "text": _Shape(fixed_chars=1, item_chars=1, minimum_tokens=1),
    "review": _Shape(fixed_chars=340, item_chars=520, minimum_tokens=1_400),
    "evidence": _Shape(fixed_chars=300, item_chars=360, minimum_tokens=1_400),
}

_DEFAULT_ITEM_CAPS: dict[str, int] = {
    "spine_turns": 8,
    "role_demands": 12,
    "cast_dossiers": 5,
    "cast_relations": 24,
    "volume_boundaries": 6,
    "volume_contracts": 4,
    "review_findings": 6,
    "evidence_claims": 8,
}


@dataclass(frozen=True, slots=True)
class OutputBudgetPlanner:
    profile: NarrativeScaleProfile

    def for_stage(
        self,
        stage_id: StageId,
        binding: ProviderBinding,
        context: dict[str, Any],
    ) -> OutputBudgetPlan:
        if stage_id == "brief":
            return self._structured("brief", binding, expected_items=1, item_cap=1)
        if stage_id == "spine":
            cap = self.item_cap("spine_turns")
            return self._structured("spine", binding, expected_items=cap, item_cap=cap)
        if stage_id == "cast":
            refs = _material_list(context, "subject_refs")
            cap = self.item_cap("cast_dossiers")
            return self._structured(
                "cast_dossier",
                binding,
                expected_items=max(1, len(refs)),
                item_cap=cap,
            )
        if stage_id == "volumes":
            boundaries = _material_dict(context, "volume_boundaries").get("proposals")
            expected = len(boundaries) if isinstance(boundaries, list) else 1
            cap = self.item_cap("volume_contracts")
            return self._structured("volumes", binding, expected_items=max(1, expected), item_cap=cap)
        if stage_id == "detail":
            basis = context.get("budget_basis")
            expected = int(basis.get("expected_chapters") or 1) if isinstance(basis, dict) else 1
            capacity = self.detail_chapter_capacity(binding)
            return self._structured(
                "detail",
                binding,
                expected_items=expected,
                item_cap=capacity,
                scene_cap=self.profile.chapter_scene_cap,
            )
        if stage_id == "cover":
            return self._structured("cover", binding, expected_items=1, item_cap=1)
        raise ValueError(f"Stage {stage_id} does not use a Provider output budget")

    def for_proposal(
        self,
        proposal_type: str,
        binding: ProviderBinding,
        context: dict[str, Any],
    ) -> OutputBudgetPlan:
        if proposal_type == "role_demand":
            cap = self.item_cap("role_demands")
            spine = _material_dict(context, "story_spine")
            turns = spine.get("turns")
            expected = min(cap, max(1, len(turns) if isinstance(turns, list) else cap))
            return self._structured("role_demand", binding, expected_items=expected, item_cap=cap)
        if proposal_type == "cast_relation":
            cap = self.item_cap("cast_relations")
            subjects = _material_list(context, "subjects")
            expected = min(cap, max(1, len(subjects) * 2))
            return self._structured("cast_relation", binding, expected_items=expected, item_cap=cap)
        if proposal_type == "volume_boundary":
            cap = self.item_cap("volume_boundaries")
            spine = _material_dict(context, "story_spine")
            turns = spine.get("turns")
            expected = min(cap, max(1, len(turns) if isinstance(turns, list) else cap))
            return self._structured("volume_boundary", binding, expected_items=expected, item_cap=cap)
        raise ValueError(f"Unknown proposal output budget: {proposal_type}")

    def for_chapter(self, binding: ProviderBinding) -> OutputBudgetPlan:
        return OutputBudgetPlan(
            kind="text",
            expected_items=1,
            item_cap=1,
            field_char_cap=max(1, binding.max_tokens),
            estimated_chars=max(1, binding.max_tokens),
            max_tokens=binding.max_tokens,
        )

    def for_review(self, binding: ProviderBinding) -> OutputBudgetPlan:
        cap = self.item_cap("review_findings")
        return self._structured("review", binding, expected_items=cap, item_cap=cap)

    def for_evidence(self, binding: ProviderBinding) -> OutputBudgetPlan:
        cap = self.item_cap("evidence_claims")
        return self._structured("evidence", binding, expected_items=cap, item_cap=cap)

    def detail_chapter_capacity(self, binding: ProviderBinding) -> int:
        shape = _SHAPES["detail"]
        available_chars = math.floor(max(0, binding.max_tokens - 384) / 1.15)
        return max(1, (available_chars - shape.fixed_chars) // shape.item_chars)

    def attach(
        self,
        context: dict[str, Any],
        plan: OutputBudgetPlan,
    ) -> dict[str, Any]:
        return {**context, "output_budget": plan.sidecar()}

    def item_cap(self, key: str) -> int:
        value = self.profile.json_item_caps.get(key, _DEFAULT_ITEM_CAPS[key])
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"Narrative scale output cap {key} must be a positive integer")
        return value

    def _structured(
        self,
        kind: BudgetKind,
        binding: ProviderBinding,
        *,
        expected_items: int,
        item_cap: int,
        scene_cap: int | None = None,
    ) -> OutputBudgetPlan:
        if expected_items > item_cap:
            raise OutputBudgetExceeded(
                f"{kind} unit expects {expected_items} items but its frozen item cap is {item_cap}; split the unit before calling the Provider"
            )
        shape = _SHAPES[kind]
        estimated_chars = shape.fixed_chars + expected_items * shape.item_chars
        required_tokens = max(
            shape.minimum_tokens,
            math.ceil(estimated_chars * 1.15) + 384,
        )
        if required_tokens > binding.max_tokens:
            raise OutputBudgetExceeded(
                f"{kind} unit requires {required_tokens} output tokens but the frozen Provider ceiling is {binding.max_tokens}; split the unit or create a new Run with a larger ceiling"
            )
        return OutputBudgetPlan(
            kind=kind,
            expected_items=expected_items,
            item_cap=item_cap,
            field_char_cap=shape.item_chars,
            estimated_chars=estimated_chars,
            max_tokens=required_tokens,
            scene_cap=scene_cap,
        )


def _material_list(context: dict[str, Any], key: str) -> list[Any]:
    material = context.get("material")
    value = material.get(key) if isinstance(material, dict) else None
    return value if isinstance(value, list) else []


def _material_dict(context: dict[str, Any], key: str) -> dict[str, Any]:
    material = context.get("material")
    value = material.get(key) if isinstance(material, dict) else None
    return value if isinstance(value, dict) else {}


__all__ = [
    "OutputBudgetExceeded",
    "OutputBudgetPlan",
    "OutputBudgetPlanner",
]

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from novel_workflow.workflows.narrative_scale import (
    NarrativeScaleProfile,
    detail_scene_count_range,
)


BudgetKind = Literal[
    "brief",
    "spine",
    "cast_dossier",
    "volumes",
    "detail",
    "cover",
    "role_demand",
    "role_demand_review",
    "spine_review",
    "cast_review",
    "cast_relation",
    "volume_boundary",
    "detail_layout",
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
    "spine": _Shape(fixed_chars=900, item_chars=125, minimum_tokens=2_400),
    "cast_dossier": _Shape(fixed_chars=320, item_chars=1_100, minimum_tokens=1_800),
    "volumes": _Shape(fixed_chars=300, item_chars=980, minimum_tokens=1_800),
    # Detail chapters contain compact scene instructions, not prose. The old
    # 1,620-char estimate split a 14-chapter volume into one turn per call and
    # forced the model to stretch each small turn across two chapters. The
    # strict schema plus live DeepSeek receipts put the bounded item envelope
    # below 900 chars, which keeps adjacent turns together without risking the
    # frozen output ceiling.
    "detail": _Shape(fixed_chars=320, item_chars=900, minimum_tokens=2_400),
    "cover": _Shape(fixed_chars=1_500, item_chars=1, minimum_tokens=1_800),
    "role_demand": _Shape(fixed_chars=260, item_chars=450, minimum_tokens=1_600),
    "role_demand_review": _Shape(fixed_chars=240, item_chars=460, minimum_tokens=1_400),
    "spine_review": _Shape(fixed_chars=240, item_chars=420, minimum_tokens=1_400),
    "cast_review": _Shape(fixed_chars=240, item_chars=460, minimum_tokens=1_400),
    "cast_relation": _Shape(fixed_chars=220, item_chars=230, minimum_tokens=1_400),
    "volume_boundary": _Shape(fixed_chars=220, item_chars=240, minimum_tokens=1_400),
    "detail_layout": _Shape(fixed_chars=300, item_chars=85, minimum_tokens=1_800),
    "text": _Shape(fixed_chars=1, item_chars=1, minimum_tokens=1),
    "review": _Shape(fixed_chars=340, item_chars=520, minimum_tokens=1_400),
    "evidence": _Shape(fixed_chars=300, item_chars=360, minimum_tokens=1_400),
}

_DEFAULT_ITEM_CAPS: dict[str, int] = {
    "spine_turns": 120,
    # Role Demand is one global call so it can enforce one protagonist and
    # deduplicate duties across the whole cast. Keep its serialization ceiling
    # aligned with RoleDemandProposalBatch instead of introducing a second,
    # smaller character-count authority.
    "role_demands": 24,
    "role_demand_review_findings": 8,
    "spine_review_findings": 5,
    "cast_dossiers": 5,
    "cast_review_findings": 8,
    "cast_relations": 24,
    "detail_layout_chapters": 200,
    "review_findings": 6,
    "evidence_claims": 8,
}

_TASK_NAMES_BY_BUDGET: dict[BudgetKind, str] = {
    "brief": "brief",
    "spine": "spine",
    "cast_dossier": "cast",
    "volumes": "volumes",
    "detail": "detail",
    "cover": "cover",
    "role_demand": "role_demand.proposal",
    "role_demand_review": "role_demand_review.proposal",
    "spine_review": "spine_review.proposal",
    "cast_review": "cast_review.proposal",
    "cast_relation": "cast_relation.proposal",
    "volume_boundary": "volume_boundary.proposal",
    "detail_layout": "detail_layout.proposal",
    "text": "text",
    "review": "text.review",
    "evidence": "text.evidence",
}

_DETAIL_CHAPTER_BASE_CHARS = 360
_DETAIL_SCENE_CHARS = 170


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
            turn_target, _, _ = spine_turn_plan(context)
            frozen_cap = self.item_cap("spine_turns")
            if turn_target > frozen_cap:
                raise OutputBudgetExceeded(
                    f"spine scale requires {turn_target} turns but its frozen item cap is "
                    f"{frozen_cap}; raise the cap before calling the Provider"
                )
            return self._structured(
                "spine",
                binding,
                expected_items=turn_target,
                item_cap=turn_target,
            )
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
            return self._structured(
                "volumes",
                binding,
                expected_items=1,
                item_cap=1,
            )
        if stage_id == "detail":
            basis = context.get("budget_basis")
            expected = int(basis.get("expected_chapters") or 1) if isinstance(basis, dict) else 1
            material = context.get("material")
            recovery = material.get("recovery_source") if isinstance(material, dict) else None
            if recovery is not None:
                if not isinstance(recovery, dict):
                    raise ValueError("Detail recovery output budget requires structured source")
                editable_refs = recovery.get("editable_chapter_refs")
                if not isinstance(editable_refs, list) or not editable_refs:
                    raise ValueError(
                        "Detail recovery output budget requires editable chapter refs"
                    )
                expected = len(editable_refs)
            scale = material.get("scale_projection") if isinstance(material, dict) else None
            scene_cap = (
                int(scale.get("scenes_per_chapter_max") or 0)
                if isinstance(scale, dict)
                else 0
            )
            if scene_cap < 1:
                raise ValueError("Detail output budget requires a dynamic scene-count range")
            item_chars = _detail_chapter_chars(scene_cap)
            capacity = self.detail_chapter_capacity(binding, scene_cap=scene_cap)
            return self._structured(
                "detail",
                binding,
                expected_items=expected,
                item_cap=capacity,
                scene_cap=scene_cap,
                item_chars=item_chars,
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
            scale_plan = _material_dict(context, "scale_plan")
            scale_cap = scale_plan.get("cast_hard_max")
            if (
                not isinstance(scale_cap, int)
                or isinstance(scale_cap, bool)
                or scale_cap < 1
            ):
                raise ValueError("Role demand proposal requires a frozen cast capacity")
            serialization_cap = self.item_cap("role_demands")
            if scale_cap > serialization_cap:
                raise OutputBudgetExceeded(
                    f"role demand scale allows {scale_cap} subjects but its frozen item cap is "
                    f"{serialization_cap}; raise the cap before calling the Provider"
                )
            # The effective Provider schema permits any irreducible ensemble up
            # to cast_hard_max. Budget for that legal maximum, not the editorial
            # center, or a valid larger first draft can be truncated mid-JSON.
            return self._structured(
                "role_demand",
                binding,
                expected_items=scale_cap,
                item_cap=scale_cap,
            )
        if proposal_type == "spine_review":
            cap = self.item_cap("spine_review_findings")
            return self._structured(
                "spine_review",
                binding,
                expected_items=cap,
                item_cap=cap,
            )
        if proposal_type == "role_demand_review":
            cap = self.item_cap("role_demand_review_findings")
            return self._structured(
                "role_demand_review",
                binding,
                expected_items=cap,
                item_cap=cap,
            )
        if proposal_type == "cast_review":
            cap = self.item_cap("cast_review_findings")
            return self._structured(
                "cast_review",
                binding,
                expected_items=cap,
                item_cap=cap,
            )
        if proposal_type == "cast_relation":
            cap = self.item_cap("cast_relations")
            subjects = _material_list(context, "subjects")
            expected = min(cap, max(1, len(subjects) * 2))
            return self._structured("cast_relation", binding, expected_items=expected, item_cap=cap)
        if proposal_type == "volume_boundary":
            cap = self.item_cap("volume_boundaries")
            scale_plan = _material_dict(context, "scale_plan")
            volume_target = scale_plan.get("volume_target")
            if (
                not isinstance(volume_target, int)
                or isinstance(volume_target, bool)
                or volume_target < 1
            ):
                raise ValueError("Volume boundary proposal requires a frozen volume target")
            expected = min(cap, volume_target)
            return self._structured("volume_boundary", binding, expected_items=expected, item_cap=cap)
        if proposal_type == "detail_layout":
            cap = self.item_cap("detail_layout_chapters")
            scale_plan = _material_dict(context, "scale_plan")
            chapter_target = scale_plan.get("chapter_target")
            chapter_range = scale_plan.get("chapter_range")
            expected = (
                chapter_target
                if isinstance(chapter_target, int)
                and not isinstance(chapter_target, bool)
                and chapter_target >= 1
                else chapter_range[1]
                if isinstance(chapter_range, list)
                and len(chapter_range) == 2
                and isinstance(chapter_range[1], int)
                else cap
            )
            return self._structured(
                "detail_layout",
                binding,
                expected_items=expected,
                item_cap=cap,
            )
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

    def detail_chapter_capacity(
        self,
        binding: ProviderBinding,
        *,
        scene_cap: int | None = None,
    ) -> int:
        shape = _SHAPES["detail"]
        resolved_scene_cap = scene_cap or detail_scene_count_range(self.profile)[1]
        item_chars = _detail_chapter_chars(resolved_scene_cap)
        available_chars = math.floor(max(0, binding.max_tokens - 384) / 1.15)
        return max(1, (available_chars - shape.fixed_chars) // item_chars)

    def attach(
        self,
        context: dict[str, Any],
        plan: OutputBudgetPlan,
    ) -> dict[str, Any]:
        return {**context, "output_budget": plan.sidecar()}

    def item_cap(self, key: str) -> int:
        default = (
            self.profile.volume_candidate_cap
            if key == "volume_boundaries"
            else _DEFAULT_ITEM_CAPS[key]
        )
        value = self.profile.json_item_caps.get(key, default)
        if key == "volume_boundaries":
            value = min(value, self.profile.volume_candidate_cap)
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
        item_chars: int | None = None,
    ) -> OutputBudgetPlan:
        if expected_items > item_cap:
            raise OutputBudgetExceeded(
                f"{kind} unit expects {expected_items} items but its frozen item cap is {item_cap}; split the unit before calling the Provider"
            )
        shape = _SHAPES[kind]
        resolved_item_chars = item_chars or shape.item_chars
        estimated_chars = shape.fixed_chars + expected_items * resolved_item_chars
        required_tokens = max(
            shape.minimum_tokens,
            math.ceil(estimated_chars * 1.15) + 384,
        )
        if required_tokens > binding.max_tokens:
            raise OutputBudgetExceeded(
                f"{kind} unit requires {required_tokens} output tokens but the frozen Provider ceiling is {binding.max_tokens}; split the unit or create a new Run with a larger ceiling"
            )
        max_tokens = (
            binding.max_tokens
            if _thinking_enabled(binding, _TASK_NAMES_BY_BUDGET[kind])
            else required_tokens
        )
        return OutputBudgetPlan(
            kind=kind,
            expected_items=expected_items,
            item_cap=item_cap,
            # A singleton artifact spends most of its response on fixed fields,
            # so its visible character guidance must describe the whole object.
            # Using the array item cap here produced instructions such as
            # "keep the Brief within about 1 character".
            field_char_cap=(
                shape.fixed_chars + resolved_item_chars
                if expected_items == 1 and item_cap == 1
                else resolved_item_chars
            ),
            estimated_chars=estimated_chars,
            max_tokens=max_tokens,
            scene_cap=scene_cap,
        )


def _detail_chapter_chars(scene_cap: int) -> int:
    if scene_cap < 1:
        raise ValueError("Detail scene capacity must be positive")
    return _DETAIL_CHAPTER_BASE_CHARS + scene_cap * _DETAIL_SCENE_CHARS


def _thinking_enabled(binding: ProviderBinding, task_name: str) -> bool:
    policy = resolve_request_policy(
        binding.provider_template,
        model=binding.model,
        task_name=task_name,
    )
    effort = policy.request_parameters.get("reasoning_effort")
    if isinstance(effort, str) and effort.casefold() not in {
        "",
        "disabled",
        "none",
        "off",
    }:
        return True
    thinking = policy.extra_body_parameters.get("thinking")
    if isinstance(thinking, dict) and thinking.get("type") == "enabled":
        return True
    return policy.extra_body_parameters.get("enable_thinking") is True


def _material_list(context: dict[str, Any], key: str) -> list[Any]:
    material = context.get("material")
    value = material.get(key) if isinstance(material, dict) else None
    return value if isinstance(value, list) else []


def _material_dict(context: dict[str, Any], key: str) -> dict[str, Any]:
    material = context.get("material")
    value = material.get(key) if isinstance(material, dict) else None
    return value if isinstance(value, dict) else {}


def spine_turn_plan(context: dict[str, Any]) -> tuple[int, int, int]:
    scale = _material_dict(context, "scale_plan")
    target = scale.get("turn_target")
    turn_range = scale.get("turn_capacity_range")
    if (
        not isinstance(target, int)
        or isinstance(target, bool)
        or not isinstance(turn_range, list)
        or len(turn_range) != 2
        or any(not isinstance(value, int) or isinstance(value, bool) for value in turn_range)
    ):
        raise ValueError("Spine Provider context requires a complete frozen scale_plan")
    turn_min, turn_max = turn_range
    if turn_min < 1 or not turn_min <= target <= turn_max:
        raise ValueError("Spine scale_plan turn target must fit its positive range")
    return target, turn_min, turn_max


__all__ = [
    "OutputBudgetExceeded",
    "OutputBudgetPlan",
    "OutputBudgetPlanner",
    "spine_turn_plan",
]

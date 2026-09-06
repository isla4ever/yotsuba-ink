"""Traceable epistemic custody for Phase 32 Cast Provider context."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_specs import CreationRouteId


EpistemicStatus = Literal[
    "author_constraint",
    "scale_constraint",
    "accepted_plan",
    "audience_target",
    "projected_risk",
    "planned_outcome",
    "open_question",
    "style_constraint",
]


class EpistemicSourceEntry(BaseModel):
    """One exact source value and the strongest use downstream may make of it."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_path: str = Field(min_length=1, max_length=500)
    source_ref: str = Field(min_length=1, max_length=500)
    value_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: EpistemicStatus
    canon_authority: Literal[False] = False
    allowed_use: str = Field(min_length=1, max_length=800)
    prohibited_promotion: str = Field(min_length=1, max_length=800)


class Phase32EpistemicContext(BaseModel):
    """Content-addressed claim custody injected into a future Cast request."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    contract_id: str = Field(pattern=r"^epistemic\.phase32\.[a-z0-9_.-]+$")
    contract_revision: Literal["r1"] = "r1"
    creation_route_id: CreationRouteId
    stage_id: Literal["cast"] = "cast"
    context_policy_ref: str = Field(pattern=r"^context\.[a-z0-9_.-]+\.cast\.v2$")
    sources: tuple[EpistemicSourceEntry, ...] = Field(min_length=1, max_length=160)
    global_rules: tuple[str, ...] = Field(min_length=1, max_length=16)
    contract_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_contract_digest(self) -> "Phase32EpistemicContext":
        payload = self.model_dump(mode="json", exclude={"contract_digest"})
        if self.contract_digest != canonical_digest(payload):
            raise ValueError("Epistemic context digest does not match its payload")
        paths = tuple(source.source_path for source in self.sources)
        if len(paths) != len(set(paths)):
            raise ValueError("Epistemic context source paths must be unique")
        return self


_FIELD_POLICIES: dict[str, dict[str, tuple[EpistemicStatus, str, str]]] = {
    "screenplay_brief": {
        "sample_type": (
            "accepted_plan",
            "Constrain the Cast to the accepted sample form.",
            "Do not present a format choice as a story-world fact.",
        ),
        "target_minutes": (
            "scale_constraint",
            "Limit Cast size and dramatic load to the accepted duration.",
            "Do not turn duration into character history or motivation.",
        ),
        "premise": (
            "accepted_plan",
            "Use the accepted opening setup to define necessary story functions.",
            "Do not claim that planned allegations or identities have been proven in-story.",
        ),
        "audience_promise": (
            "audience_target",
            "Use it to differentiate character functions and audience access to information.",
            "Do not convert a promised audience experience into character knowledge.",
        ),
        "visible_conflict": (
            "projected_risk",
            "Model observable pressure, perceived stakes, and operational constraints.",
            "Do not state projected death, guilt, legal liability, or motive as certain fact.",
        ),
        "ending_effect": (
            "planned_outcome",
            "Keep character arcs capable of reaching the accepted visible ending target.",
            "Do not treat future outcomes or embedded open questions as present facts or motives.",
        ),
        "tone": (
            "style_constraint",
            "Differentiate voices while preserving the accepted audiovisual tone.",
            "Do not invent biography or culpability from a style instruction.",
        ),
    },
    "novel_brief": {
        "premise": (
            "accepted_plan",
            "Use the accepted setup to define only necessary character functions.",
            "Do not present planned revelations or allegations as proven story facts.",
        ),
        "audience_promise": (
            "audience_target",
            "Use it to distinguish reader access and character dramatic functions.",
            "Do not convert reader knowledge into character knowledge.",
        ),
        "theme_question": (
            "open_question",
            "Let characters embody different pressures around the question.",
            "Do not answer the theme question inside the Character Bible.",
        ),
        "world_rules": (
            "author_constraint",
            "Respect the accepted planning rules when defining constraints.",
            "Do not invent exceptions or claim that a planned event has already occurred.",
        ),
        "ending_direction": (
            "planned_outcome",
            "Keep arc scopes compatible with the accepted ending direction.",
            "Do not write the future ending as completed character history.",
        ),
        "narrative_voice": (
            "style_constraint",
            "Differentiate character voices within the accepted narrative register.",
            "Do not infer facts or motives from style.",
        ),
        "target_characters": (
            "scale_constraint",
            "Limit Cast breadth to the accepted work size.",
            "Do not turn length into character content.",
        ),
    },
    "story_map": {
        "opening_state": (
            "accepted_plan",
            "Use it as the planned entry condition for character functions.",
            "Do not promote unverified interpretations of that state to facts.",
        ),
        "story_question": (
            "open_question",
            "Assign characters different pressures around the unresolved story question.",
            "Do not answer the story question or assign hidden guilt as fact.",
        ),
        "anchors": (
            "accepted_plan",
            "Keep desires and arc scopes capable of executing accepted anchors.",
            "Do not write future revelations or consequences as completed history.",
        ),
        "ending_state": (
            "planned_outcome",
            "Keep arc scopes compatible with the accepted ending state.",
            "Do not present the ending state as already true.",
        ),
        "open_questions": (
            "open_question",
            "Preserve these as explicit unknowns that later stages may dramatize.",
            "Never answer these unresolved questions through desire, stakes, constraints, relationships, or biography.",
        ),
    },
    "book_architecture": {
        "book_promise": (
            "audience_target",
            "Use it to assign long-range character functions without overbuilding the Cast.",
            "Do not convert a reader promise into character knowledge.",
        ),
        "ending_conditions": (
            "planned_outcome",
            "Keep arc scopes compatible with accepted terminal conditions.",
            "Do not write terminal conditions as completed history.",
        ),
        "parts": (
            "accepted_plan",
            "Use Part entry, turn, and exit plans to scope character participation.",
            "Dramatic questions and unresolved obligations inside Parts remain unresolved.",
        ),
    },
}


_GLOBAL_RULES = (
    "Accepted planning Artifacts are binding plans, not Canon or proof that an allegation is true.",
    "Open questions, suspected motives, projected risks, and future outcomes must remain explicitly unresolved.",
    "Cast may define observable goals, perceived stakes, constraints, voice, and arc scope; it may not establish hidden guilt or guaranteed consequences without an author constraint.",
    "If a source supports multiple interpretations, preserve the ambiguity instead of selecting one as fact.",
)


def compile_phase32_cast_epistemic_context(
    *,
    creation_route_id: CreationRouteId,
    context_policy_ref: str,
    inputs: dict[str, Any],
    inputs_digest: str,
    upstream_artifacts: dict[str, Any],
) -> Phase32EpistemicContext | None:
    """Compile the v2 Cast claim boundary; v1 frozen Runs remain byte-stable."""

    if not context_policy_ref.endswith(".cast.v2"):
        return None
    entries: list[EpistemicSourceEntry] = []
    creative_intent = inputs.get("creative_intent")
    if creative_intent not in (None, ""):
        entries.append(
            _entry(
                source_path="inputs.creative_intent",
                source_ref=f"inputs:{inputs_digest}",
                value=creative_intent,
                status="author_constraint",
                allowed_use=(
                    "Treat explicit author requirements as binding planning constraints."
                ),
                prohibited_promotion=(
                    "Do not treat a requested setup, suspicion, risk, or ending as already proven Canon."
                ),
            )
        )
    for stage_id, source in upstream_artifacts.items():
        artifact_kind = str(source.get("artifact_kind") or "")
        payload = source.get("payload")
        if not isinstance(payload, dict):
            continue
        policies = _FIELD_POLICIES.get(artifact_kind, {})
        for field, (status, allowed_use, prohibited_promotion) in policies.items():
            if field not in payload:
                continue
            entries.append(
                _entry(
                    source_path=f"upstream_artifacts.{stage_id}.payload.{field}",
                    source_ref=str(source.get("artifact_ref") or stage_id),
                    value=payload[field],
                    status=status,
                    allowed_use=allowed_use,
                    prohibited_promotion=prohibited_promotion,
                )
            )
    if not entries:
        raise ValueError("Cast epistemic context requires traceable source entries")
    payload = {
        "contract_id": f"epistemic.phase32.{creation_route_id}.cast.v1",
        "contract_revision": "r1",
        "creation_route_id": creation_route_id,
        "stage_id": "cast",
        "context_policy_ref": context_policy_ref,
        "sources": [entry.model_dump(mode="json") for entry in entries],
        "global_rules": list(_GLOBAL_RULES),
    }
    return Phase32EpistemicContext.model_validate(
        {**payload, "contract_digest": canonical_digest(payload)}
    )


def _entry(
    *,
    source_path: str,
    source_ref: str,
    value: Any,
    status: EpistemicStatus,
    allowed_use: str,
    prohibited_promotion: str,
) -> EpistemicSourceEntry:
    return EpistemicSourceEntry(
        source_path=source_path,
        source_ref=source_ref,
        value_digest=canonical_digest(value),
        status=status,
        allowed_use=allowed_use,
        prohibited_promotion=prohibited_promotion,
    )


__all__ = [
    "EpistemicSourceEntry",
    "EpistemicStatus",
    "Phase32EpistemicContext",
    "compile_phase32_cast_epistemic_context",
]

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    DetailArtifact,
    StoryBriefArtifact,
    StorySpineArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.quality.narrative_contracts import (
    NarrativeContractReport,
    build_narrative_contract_report,
)
from novel_workflow.quality.planning_contracts import (
    MysteryPromiseLedger,
    WorldRuleSet,
    build_mystery_promise_ledger,
    project_world_rules,
)


ProgressDimension = Literal["action", "knowledge", "relationship", "risk"]


class DetailHandoffProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1, max_length=300)
    resulting_state: str = Field(min_length=1, max_length=700)
    next_step: str = Field(min_length=1, max_length=800)


class DetailChapterContractProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    title: str = Field(min_length=2, max_length=12)
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    progress_vector: list[ProgressDimension] = Field(min_length=1, max_length=4)
    state_delta_refs: list[str] = Field(min_length=1, max_length=32)
    authorized_repetition_refs: list[str] = Field(default_factory=list, max_length=24)
    handoff: DetailHandoffProjection
    promise_refs: list[str] = Field(default_factory=list, max_length=48)
    reveal_refs: list[str] = Field(default_factory=list, max_length=48)


class PlanningBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    chapter_refs: list[str] = Field(default_factory=list, max_length=24)
    evidence: str = Field(min_length=1, max_length=2000)
    required_fix: str = Field(min_length=1, max_length=2000)


class DetailPreflightReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    world_rules: WorldRuleSet
    promise_ledger: MysteryPromiseLedger
    narrative_contracts: NarrativeContractReport
    chapters: list[DetailChapterContractProjection] = Field(min_length=1)
    blockers: list[PlanningBlocker] = Field(default_factory=list)


class DetailPreflightError(ValueError):
    def __init__(self, report: DetailPreflightReport) -> None:
        self.report = report
        codes = ", ".join(blocker.code for blocker in report.blockers)
        super().__init__(f"Detail preflight blocked the candidate: {codes}")


_PROGRESS_DIMENSIONS: dict[str, tuple[ProgressDimension, ...]] = {
    "information": ("knowledge",),
    "relationship": ("relationship",),
    "external": ("action", "risk"),
    "internal": ("risk",),
}
_TERMINAL_OUTCOME_MARKERS = (
    "正式结案",
    "案件结案",
    "主案终结",
    "最终裁决",
    "真相全部公开",
    "最终真相公开",
    "核心谜题彻底解决",
)


def build_detail_preflight(
    *,
    brief: StoryBriefArtifact,
    spine: StorySpineArtifact,
    cast: CharacterBibleArtifact,
    detail: DetailArtifact,
    volumes: VolumeArchitectureArtifact | None = None,
) -> DetailPreflightReport:
    """Build the deterministic planning gate consumed before Detail commit."""

    world_rules = project_world_rules(brief)
    ledger = build_mystery_promise_ledger(brief, spine, detail)
    narrative_contracts = build_narrative_contract_report(
        brief=brief,
        spine=spine,
        cast=cast,
        volumes=volumes,
        detail=detail,
    )
    turn_by_id = {turn.id: turn for turn in spine.turns}
    authorized_rule_ids = [
        rule.rule_id for rule in world_rules.rules if rule.authorizes_repetition
    ]
    chapters: list[DetailChapterContractProjection] = []
    blockers: list[PlanningBlocker] = []
    blockers.extend(
        PlanningBlocker(
            code=finding.code,
            chapter_refs=finding.source_refs,
            evidence=finding.evidence,
            required_fix=finding.required_fix,
        )
        for finding in narrative_contracts.findings
    )
    signatures: list[str] = []
    previous = None

    known_subjects = {subject.id for subject in cast.subjects}
    historical_subjects = {
        subject.id for subject in cast.subjects if subject.kind == "historical_record"
    }
    climax_ref = next(
        turn.id for turn in spine.turns if "climax" in turn.milestones
    )
    climax_chapter_number = next(
        (
            index
            for index, chapter in enumerate(detail.chapters, start=1)
            if climax_ref in chapter.turn_refs
        ),
        len(detail.chapters),
    )

    for index, chapter in enumerate(detail.chapters, start=1):
        unknown_subjects = set(chapter.cast_ids) - known_subjects
        if unknown_subjects:
            blockers.append(
                PlanningBlocker(
                    code="unknown_detail_subject",
                    chapter_refs=[chapter.ref],
                    evidence=f"Unknown frozen subjects: {sorted(unknown_subjects)}",
                    required_fix="Use only subject ids committed by the Cast artifact.",
                )
            )
        present_historical = set(chapter.cast_ids) & historical_subjects
        if present_historical:
            blockers.append(
                PlanningBlocker(
                    code="historical_subject_acts_in_present",
                    chapter_refs=[chapter.ref],
                    evidence=f"Historical subjects in present cast: {sorted(present_historical)}",
                    required_fix="Reference the record or legacy without making it a present actor.",
                )
            )

        turn_progress = [
            turn_by_id[turn_ref].progress_type
            for turn_ref in chapter.turn_refs
            if turn_ref in turn_by_id
        ]
        progress_vector = _ordered_unique_dimensions(
            dimension
            for progress_type in turn_progress
            for dimension in _PROGRESS_DIMENSIONS[progress_type]
        )
        last_scene = chapter.scenes[-1]
        signature = _state_signature(
            chapter.turn_refs,
            last_scene.result,
            chapter.handoff,
        )
        signatures.append(signature)
        repeated_form = previous is not None and (
            chapter.title.strip().casefold() == previous.title.strip().casefold()
            or chapter.purpose.strip().casefold() == previous.purpose.strip().casefold()
        )
        authorized_repetition_refs = (
            authorized_rule_ids if repeated_form else []
        )
        promise_refs, reveal_refs = _chapter_promise_refs(
            chapter.turn_refs,
            ledger,
        )
        chapters.append(
            DetailChapterContractProjection(
                chapter_id=chapter.ref,
                title=chapter.title,
                cast_ids=list(chapter.cast_ids),
                progress_vector=progress_vector,
                state_delta_refs=[
                    *[
                        f"spine:{turn_ref}:{turn_by_id[turn_ref].progress_type}"
                        for turn_ref in chapter.turn_refs
                        if turn_ref in turn_by_id
                    ],
                    f"detail:state:{signature[:16]}",
                ],
                authorized_repetition_refs=authorized_repetition_refs,
                handoff=DetailHandoffProjection(
                    location=last_scene.place,
                    resulting_state=last_scene.result,
                    next_step=chapter.handoff,
                ),
                promise_refs=promise_refs,
                reveal_refs=reveal_refs,
            )
        )

        if index > 1 and signature == signatures[-2]:
            blockers.append(
                PlanningBlocker(
                    code="missing_state_delta",
                    chapter_refs=[detail.chapters[index - 2].ref, chapter.ref],
                    evidence=(
                        "Adjacent chapters repeat the same turn refs, final result, "
                        "and handoff without a new state."
                    ),
                    required_fix=(
                        "Change action, knowledge, relationship, or risk before the handoff."
                    ),
                )
            )
            previous_chapter = detail.chapters[index - 2]
            same_title_and_purpose = (
                previous_chapter.title.strip().casefold()
                == chapter.title.strip().casefold()
                and previous_chapter.purpose.strip().casefold()
                == chapter.purpose.strip().casefold()
            )
            if same_title_and_purpose and not authorized_repetition_refs:
                blockers.append(
                    PlanningBlocker(
                        code="unauthorized_repetition",
                        chapter_refs=[previous_chapter.ref, chapter.ref],
                        evidence="Adjacent chapters repeat title, purpose, and resulting state.",
                        required_fix=(
                            "Remove the duplicate chapter or bind the repeated form to an "
                            "explicit world-rule loop with a new state consequence."
                        ),
                    )
                )

        terminal_marker = _terminal_marker(chapter)
        if terminal_marker and index < climax_chapter_number:
            blockers.append(
                PlanningBlocker(
                    code="premature_main_resolution",
                    chapter_refs=[chapter.ref, f"chapter-{climax_chapter_number}"],
                    evidence=(
                        f"{chapter.ref} states terminal outcome '{terminal_marker}' "
                        f"before the climax chapter."
                    ),
                    required_fix=(
                        "Keep this chapter as pressure, failed attempt, partial reveal, or "
                        "relationship consequence; reserve final resolution for the climax."
                    ),
                )
            )
        previous = chapter

    for entry in ledger.entries:
        if entry.status != "missing":
            continue
        blockers.append(
            PlanningBlocker(
                code=(
                    "central_mystery_missing"
                    if entry.kind == "central_mystery"
                    else "reader_promise_missing"
                ),
                chapter_refs=[],
                evidence=(
                    f"{entry.promise_id} lacks: {', '.join(entry.missing_components)}"
                ),
                required_fix=(
                    "Bind setup, evidence progression, reveal, and consequence to frozen "
                    "Spine turns and Detail chapters before prose generation."
                ),
            )
        )

    return DetailPreflightReport(
        world_rules=world_rules,
        promise_ledger=ledger,
        narrative_contracts=narrative_contracts,
        chapters=chapters,
        blockers=blockers,
    )


def require_detail_preflight(report: DetailPreflightReport) -> None:
    if report.blockers:
        raise DetailPreflightError(report)


def _state_signature(
    turn_refs: list[str],
    final_result: str,
    handoff: str,
) -> str:
    payload = {
        "turn_refs": turn_refs,
        "final_result": final_result.strip().casefold(),
        "handoff": handoff.strip().casefold(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _chapter_promise_refs(
    turn_refs: list[str],
    ledger: MysteryPromiseLedger,
) -> tuple[list[str], list[str]]:
    owned = set(turn_refs)
    promise_refs: list[str] = []
    reveal_refs: list[str] = []
    for entry in ledger.entries:
        related = set(entry.setup_refs) | set(entry.misdirection_refs)
        related.update({entry.reveal_ref, entry.consequence_ref} - {""})
        if owned & related:
            promise_refs.append(entry.promise_id)
        if entry.reveal_ref in owned:
            reveal_refs.append(entry.promise_id)
    return promise_refs, reveal_refs


def _terminal_marker(chapter: object) -> str:
    text = " ".join(
        [
            str(getattr(chapter, "purpose", "")),
            *[
                f"{scene.turn} {scene.result}"
                for scene in getattr(chapter, "scenes", [])
            ],
            str(getattr(chapter, "handoff", "")),
        ]
    )
    # A chapter may legitimately prepare for the climax by waiting for or
    # anticipating a ruling. Only treat a terminal phrase as completed when it
    # is not negated or future-facing in the local sentence.
    for marker in _TERMINAL_OUTCOME_MARKERS:
        start = 0
        while True:
            index = text.find(marker, start)
            if index < 0:
                break
            prefix = text[max(0, index - 14) : index]
            if not re.search(
                r"(?:等待|即将|将要|准备|尚未|未曾|未能|未作出|未宣布|可能|面临|考虑)\s*$",
                prefix,
            ):
                return marker
            start = index + len(marker)
    return ""


def _ordered_unique_dimensions(
    values: Iterable[ProgressDimension],
) -> list[ProgressDimension]:
    result: list[ProgressDimension] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


__all__ = [
    "DetailChapterContractProjection",
    "DetailPreflightError",
    "DetailPreflightReport",
    "PlanningBlocker",
    "build_detail_preflight",
    "require_detail_preflight",
]

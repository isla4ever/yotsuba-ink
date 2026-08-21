from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EpistemicStatus = Literal["fact", "rumour", "belief", "reveal", "refutation"]
Lifecycle = Literal["active", "supersedes", "resolves", "contradicted"]


class StoryStateEvent(BaseModel):
    """One immutable, evidence-backed state event derived from a Canon fact."""

    model_config = ConfigDict(extra="forbid")

    source_fact_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    property_key: str = Field(min_length=1)
    value: str = Field(min_length=1, max_length=2000)
    epistemic_status: EpistemicStatus = "fact"
    lifecycle: Lifecycle = "active"
    effective_from_chapter: int = Field(ge=1)
    effective_to_chapter: int | None = Field(default=None, ge=1)
    supersedes_fact_ids: list[str] = Field(default_factory=list, max_length=16)
    resolves_fact_ids: list[str] = Field(default_factory=list, max_length=16)

    @classmethod
    def from_fact(cls, fact: object) -> "StoryStateEvent":
        """Project a CanonFact without guessing an unbound claim's entity.

        Older accepted facts have no subject/property metadata. They remain
        durable story-scoped claims until a future Evidence contract supplies
        a more precise state binding; they are never silently assigned to a
        character or location.
        """

        fact_id = str(getattr(fact, "fact_id", "")).strip()
        claim = str(getattr(fact, "claim", "")).strip()
        if not fact_id or not claim:
            raise ValueError("A Canon fact needs fact_id and claim for state projection")
        chapter = getattr(fact, "effective_from_chapter", None)
        if chapter is None:
            chapter = _chapter_number(str(getattr(fact, "chapter_version_id", ""))) or 1
        subject_id = str(getattr(fact, "subject_id", "") or "").strip() or "story"
        property_key = str(getattr(fact, "property_key", "") or "").strip()
        property_key = property_key or f"claim:{fact_id}"
        value = str(getattr(fact, "value", "") or "").strip() or claim
        return cls(
            source_fact_id=fact_id,
            subject_id=subject_id,
            property_key=property_key,
            value=value,
            epistemic_status=getattr(fact, "epistemic_status", "fact"),
            lifecycle=getattr(fact, "lifecycle", "active"),
            effective_from_chapter=int(chapter),
            effective_to_chapter=getattr(fact, "effective_to_chapter", None),
            supersedes_fact_ids=list(getattr(fact, "supersedes_fact_ids", []) or []),
            resolves_fact_ids=list(getattr(fact, "resolves_fact_ids", []) or []),
        )


class StoryStateEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    property_key: str
    value: str
    epistemic_status: EpistemicStatus
    source_fact_id: str
    source_chapter: int
    source_chain: list[str] = Field(default_factory=list)


class StoryStateConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    property_key: str
    fact_ids: list[str] = Field(min_length=2)
    values: list[str] = Field(min_length=2)


class ResolvedStoryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_chapter: int | None = Field(default=None, ge=0)
    entries: list[StoryStateEntry] = Field(default_factory=list)
    conflicts: list[StoryStateConflict] = Field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


def resolve_story_state(
    facts: Iterable[object],
    *,
    as_of_chapter: int | None = None,
    subject_ids: Iterable[str] | None = None,
) -> ResolvedStoryState:
    """Resolve current state without rewriting or dropping source facts.

    Resolution is deterministic: effective time filters the input, explicit
    supersession/resolution links retire old events, and the latest remaining
    event is the current projection. Different active values remain visible as
    conflicts so a later quality gate can decide whether they are physical,
    epistemic, or an author-approved turn.
    """

    events = [StoryStateEvent.from_fact(fact) for fact in facts]
    events = [
        event
        for event in events
        if _effective_at(event, as_of_chapter)
    ]
    events.sort(key=lambda event: (event.effective_from_chapter, event.source_fact_id))
    retired: set[str] = set()
    for event in events:
        retired.update(event.supersedes_fact_ids)
        retired.update(event.resolves_fact_ids)
        if event.lifecycle == "contradicted":
            retired.add(event.source_fact_id)

    current = [
        event
        for event in events
        if event.source_fact_id not in retired and event.lifecycle != "contradicted"
    ]
    requested_subjects = {
        str(subject_id).strip()
        for subject_id in (subject_ids or ())
        if str(subject_id).strip()
    }
    if requested_subjects:
        requested_subjects.add("story")
        current = [event for event in current if event.subject_id in requested_subjects]

    event_by_id = {event.source_fact_id: event for event in events}
    grouped: dict[tuple[str, str], list[StoryStateEvent]] = {}
    for event in current:
        grouped.setdefault((event.subject_id, event.property_key), []).append(event)

    entries: list[StoryStateEntry] = []
    conflicts: list[StoryStateConflict] = []
    for (subject_id, property_key), group in sorted(grouped.items()):
        certain_events = [
            event
            for event in group
            if event.epistemic_status in {"fact", "reveal", "refutation"}
        ]
        certain_values = list(dict.fromkeys(event.value for event in certain_events))
        if len(certain_values) > 1:
            conflicts.append(
                StoryStateConflict(
                    subject_id=subject_id,
                    property_key=property_key,
                    fact_ids=[event.source_fact_id for event in certain_events],
                    values=certain_values,
                )
            )
        for event in group:
            entries.append(
                StoryStateEntry(
                    subject_id=event.subject_id,
                    property_key=event.property_key,
                    value=event.value,
                    epistemic_status=event.epistemic_status,
                    source_fact_id=event.source_fact_id,
                    source_chapter=event.effective_from_chapter,
                    source_chain=_source_chain(event, event_by_id),
                )
            )
    entries.sort(
        key=lambda entry: (
            entry.source_chapter,
            entry.subject_id,
            entry.property_key,
            entry.source_fact_id,
        )
    )
    return ResolvedStoryState(
        as_of_chapter=as_of_chapter,
        entries=entries,
        conflicts=conflicts,
    )


def _effective_at(event: StoryStateEvent, as_of_chapter: int | None) -> bool:
    if as_of_chapter is None:
        return True
    if event.effective_from_chapter > as_of_chapter:
        return False
    return event.effective_to_chapter is None or as_of_chapter <= event.effective_to_chapter


def _chapter_number(value: str) -> int:
    for part in value.split("-"):
        if part.isdigit():
            return int(part)
    return 0


def _source_chain(
    event: StoryStateEvent,
    event_by_id: dict[str, StoryStateEvent],
) -> list[str]:
    """Return the complete, cycle-safe provenance chain for one current event."""
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(source_fact_id: str) -> None:
        if source_fact_id in visited:
            return
        visited.add(source_fact_id)
        source = event_by_id.get(source_fact_id)
        if source is not None:
            for previous_id in [
                *source.supersedes_fact_ids,
                *source.resolves_fact_ids,
            ]:
                visit(previous_id)
        ordered.append(source_fact_id)

    visit(event.source_fact_id)
    return ordered


__all__ = [
    "EpistemicStatus",
    "Lifecycle",
    "ResolvedStoryState",
    "StoryStateConflict",
    "StoryStateEntry",
    "StoryStateEvent",
    "resolve_story_state",
]

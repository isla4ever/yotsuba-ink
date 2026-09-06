"""Route-aware Story Bible read model over committed Phase 32 Artifacts."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_evidence_store import Phase32EvidenceStore
from novel_workflow.storage.phase32_writeback_outbox import Phase32WritebackOutbox
from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.memory.phase32_wiki_projection import Phase32WikiProjectionStore
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_specs import CreationRouteId


StoryBibleSection = Literal[
    "overview",
    "cast",
    "structure",
    "units",
    "continuity",
]
StoryBibleEntryKind = Literal[
    "brief_field",
    "world_rule",
    "character",
    "relationship",
    "beat",
    "scene",
    "story_anchor",
    "section_unit",
    "part",
    "volume",
    "detail_window",
    "chapter_plan",
    "accepted_unit",
    "promise",
    "open_question",
    "handoff",
    "ending_condition",
    "formal_fact",
]
StoryBibleEntryStatus = Literal[
    "committed",
    "accepted",
    "tracked",
    "open",
    "planned",
    "verified",
]

SECTIONS: tuple[StoryBibleSection, ...] = (
    "overview",
    "cast",
    "structure",
    "units",
    "continuity",
)
ROUTE_LABELS: dict[CreationRouteId, str] = {
    "screenplay_sample": "剧本样片",
    "short_novel": "短中篇小说",
    "long_novel": "长篇小说",
}


class Phase32StoryBibleProjectionError(ValueError):
    code = "phase32_story_bible_projection_invalid"


class Phase32StoryBibleCursorInvalid(Phase32StoryBibleProjectionError):
    code = "phase32_story_bible_cursor_invalid"


class Phase32StoryBibleCursorStale(Phase32StoryBibleProjectionError):
    code = "phase32_story_bible_cursor_stale"


class Phase32StoryBibleSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    stage_id: str
    artifact_kind: str
    artifact_ref: str
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_path: str
    committed_at: str


class Phase32StoryBibleEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    entry_ref: str = Field(min_length=1, max_length=500)
    kind: StoryBibleEntryKind
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(default="", max_length=4_000)
    detail: str = Field(default="", max_length=1_000)
    status: StoryBibleEntryStatus
    ordinal: int | None = Field(default=None, ge=1)
    parent_ref: str = Field(default="", max_length=500)
    unit_ref: str = Field(default="", max_length=500)
    subject_refs: tuple[str, ...] = Field(default=(), max_length=120)
    promise_refs: tuple[str, ...] = Field(default=(), max_length=120)
    tags: tuple[str, ...] = Field(default=(), max_length=24)
    authority: Literal["committed_artifact", "accepted_unit", "canon"]
    confidence: Literal["direct"] = "direct"
    source: Phase32StoryBibleSource


class Phase32StoryBibleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    route_label: str
    run_status: str
    active_stage_id: str
    updated_at: str
    projection_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    available_sections: tuple[StoryBibleSection, ...] = SECTIONS
    source_artifact_count: int = Field(ge=0)
    character_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    structure_count: int = Field(ge=0)
    accepted_unit_count: int = Field(ge=0)
    continuity_count: int = Field(ge=0)
    tracked_promise_count: int = Field(ge=0)
    open_question_count: int = Field(ge=0)
    formal_fact_count: int = Field(ge=0)
    formal_writeback_status: Literal[
        "not_started", "in_progress", "recovery_required", "committed"
    ]


class Phase32StoryBiblePage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    run_id: str
    project_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    section: StoryBibleSection
    summary: Phase32StoryBibleSummary
    items: tuple[Phase32StoryBibleEntry, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class _ProjectionContent:
    title: str
    revision: str
    source_refs: frozenset[str]
    formal_fact_count: int
    formal_writeback_status: Literal[
        "not_started", "in_progress", "recovery_required", "committed"
    ]
    sections: dict[StoryBibleSection, tuple[Phase32StoryBibleEntry, ...]]


@dataclass(frozen=True, slots=True)
class Phase32StoryBibleProjection:
    runs: Phase32RunRepository
    artifacts: Phase32ArtifactStore
    evidence: Phase32EvidenceStore
    canon: Phase32CanonStore
    wiki: Phase32WikiProjectionStore
    outbox: Phase32WritebackOutbox

    def page(
        self,
        run_id: str,
        *,
        section: StoryBibleSection,
        limit: int,
        cursor: str | None = None,
    ) -> Phase32StoryBiblePage:
        if section not in SECTIONS:
            raise Phase32StoryBibleCursorInvalid("Unknown Story Bible section")
        if not 1 <= limit <= 100:
            raise Phase32StoryBibleCursorInvalid("Story Bible page limit must be 1..100")
        record = self.runs.read(run_id)
        content = self._build(record)
        offset = _decode_cursor(cursor, section=section, revision=content.revision)
        entries = content.sections[section]
        if offset > len(entries):
            raise Phase32StoryBibleCursorInvalid("Story Bible cursor is out of range")
        items = entries[offset : offset + limit]
        next_offset = offset + len(items)
        next_cursor = (
            _encode_cursor(content.revision, section, next_offset)
            if next_offset < len(entries)
            else None
        )
        return Phase32StoryBiblePage(
            run_id=record.definition.run_id,
            project_id=record.definition.project_id,
            creation_route_id=record.definition.creation_route_id,
            route_revision=record.definition.route_revision,
            definition_digest=record.definition.definition_digest,
            section=section,
            summary=_summary(record, content),
            items=items,
            total=len(entries),
            limit=limit,
            next_cursor=next_cursor,
        )

    def _build(self, record) -> _ProjectionContent:
        from novel_workflow.storage.phase32_story_bible_entries import (
            accepted_unit,
            project_brief,
            project_cast,
        )
        from novel_workflow.storage.phase32_story_bible_long_entries import (
            project_long_novel,
        )
        from novel_workflow.storage.phase32_story_bible_route_entries import (
            project_screenplay,
            project_short_novel,
        )

        definition = record.definition
        read_model = record.read_model
        sections: dict[StoryBibleSection, list[Phase32StoryBibleEntry]] = {
            section: [] for section in SECTIONS
        }
        source_refs: set[str] = set()

        def stage_record(stage_id: str) -> Phase32ArtifactRecord | None:
            projection = read_model.artifact_refs.get(stage_id)
            if projection is None:
                return None
            artifact = self._committed(definition.run_id, projection.artifact_ref)
            if artifact.stage_id != stage_id or artifact.artifact_kind != projection.artifact_kind:
                raise Phase32StoryBibleProjectionError(
                    "Story Bible source does not match the Run read model"
                )
            source_refs.add(artifact.artifact_ref)
            return artifact

        brief_record = stage_record("brief")
        title = "待定标题"
        if brief_record is not None:
            title = str(brief_record.payload["title"])
            project_brief(sections["overview"], brief_record)

        cast_record = stage_record("cast")
        if cast_record is not None:
            project_cast(sections["cast"], cast_record)

        route_id = definition.creation_route_id
        if route_id == "screenplay_sample":
            project_screenplay(
                sections,
                stage_record("beat_board"),
                stage_record("scene_deck"),
            )
        elif route_id == "short_novel":
            project_short_novel(
                sections,
                stage_record("story_map"),
                stage_record("section_plan"),
            )
        else:
            project_long_novel(
                sections,
                stage_record("book_architecture"),
                stage_record("volumes"),
                stage_record("rolling_detail"),
            )

        unit_stage = "script" if route_id == "screenplay_sample" else "text"
        progress = read_model.sequential_stage_progress.get(unit_stage)
        if progress is not None:
            for unit_ref in progress.ordered_unit_refs:
                artifact_ref = progress.committed_artifact_refs.get(unit_ref)
                if artifact_ref is None:
                    break
                unit = self._committed(definition.run_id, artifact_ref)
                if unit.stage_id != unit_stage:
                    raise Phase32StoryBibleProjectionError(
                        "Accepted Story Bible unit belongs to the wrong stage"
                    )
                source_refs.add(unit.artifact_ref)
                sections["units"].append(accepted_unit(unit, unit_ref))

        wiki_transactions = {
            transaction.transaction_ref: transaction
            for transaction in self.wiki.list(definition.run_id)
        }
        formal_fact_count = 0
        for transaction in self.canon.transactions(definition.run_id):
            projected = wiki_transactions.get(transaction.transaction_ref)
            if projected is None or projected.facts != transaction.facts:
                continue
            source = self._committed(
                definition.run_id,
                transaction.source_artifact_ref,
            )
            source_refs.add(source.artifact_ref)
            for fact in transaction.facts:
                evidence = tuple(
                    self.evidence.read(definition.run_id, evidence_ref)
                    for evidence_ref in fact.evidence_refs
                )
                if any(item.source_artifact_ref != source.artifact_ref for item in evidence):
                    raise Phase32StoryBibleProjectionError(
                        "Canon fact Evidence does not match its accepted source"
                    )
                formal_fact_count += 1
                sections["continuity"].append(
                    Phase32StoryBibleEntry(
                        entry_ref=fact.fact_ref,
                        kind="formal_fact",
                        title=fact.claim,
                        body=" / ".join(
                            span.quote for item in evidence for span in item.spans
                        ),
                        detail=(
                            f"{fact.subject_ref} · {fact.property_key} · {fact.value}"
                            if fact.subject_ref
                            else "正文直接证据"
                        ),
                        status="verified",
                        ordinal=fact.effective_ordinal,
                        unit_ref=fact.unit_ref,
                        subject_refs=(fact.subject_ref,) if fact.subject_ref else (),
                        tags=(fact.epistemic_status, fact.lifecycle),
                        authority="canon",
                        source=Phase32StoryBibleSource(
                            stage_id=source.stage_id,
                            artifact_kind=source.artifact_kind,
                            artifact_ref=source.artifact_ref,
                            payload_digest=source.payload_digest,
                            source_path=f"canon.{transaction.transaction_ref}.{fact.fact_ref}",
                            committed_at=transaction.committed_at,
                        ),
                    )
                )

        writeback_status = _writeback_status(
            tuple(item.receipt for item in self.outbox.list(definition.run_id))
        )

        frozen_sections = {
            section: tuple(items) for section, items in sections.items()
        }
        revision = canonical_digest(
            {
                "definition_digest": definition.definition_digest,
                "updated_at": read_model.updated_at,
                "artifact_refs": sorted(source_refs),
                "section_refs": {
                    section: [item.entry_ref for item in items]
                    for section, items in frozen_sections.items()
                },
                "canon_transactions": sorted(wiki_transactions),
                "writeback_status": writeback_status,
            }
        )
        return _ProjectionContent(
            title=title,
            revision=revision,
            source_refs=frozenset(source_refs),
            formal_fact_count=formal_fact_count,
            formal_writeback_status=writeback_status,
            sections=frozen_sections,
        )

    def _committed(self, run_id: str, artifact_ref: str) -> Phase32ArtifactRecord:
        artifact = self.artifacts.read(run_id, artifact_ref)
        if artifact.status != "committed":
            raise Phase32StoryBibleProjectionError(
                "Story Bible authority must be a committed Artifact"
            )
        return artifact


def _summary(record, content: _ProjectionContent) -> Phase32StoryBibleSummary:
    cast = content.sections["cast"]
    continuity = content.sections["continuity"]
    return Phase32StoryBibleSummary(
        title=content.title,
        route_label=ROUTE_LABELS[record.definition.creation_route_id],
        run_status=record.read_model.status,
        active_stage_id=record.read_model.active_stage_id,
        updated_at=record.read_model.updated_at,
        projection_revision=content.revision,
        source_artifact_count=len(content.source_refs),
        character_count=sum(item.kind == "character" for item in cast),
        relationship_count=sum(item.kind == "relationship" for item in cast),
        structure_count=len(content.sections["structure"]),
        accepted_unit_count=len(content.sections["units"]),
        continuity_count=len(continuity),
        tracked_promise_count=sum(item.kind == "promise" for item in continuity),
        open_question_count=sum(item.kind == "open_question" for item in continuity),
        formal_fact_count=content.formal_fact_count,
        formal_writeback_status=content.formal_writeback_status,
    )


def _writeback_status(receipts) -> Literal[
    "not_started", "in_progress", "recovery_required", "committed"
]:
    if not receipts:
        return "not_started"
    if any(receipt.status == "needs_action" for receipt in receipts):
        return "recovery_required"
    if all(receipt.status == "committed" for receipt in receipts):
        return "committed"
    return "in_progress"


def _encode_cursor(revision: str, section: StoryBibleSection, offset: int) -> str:
    payload = f"{revision}|{section}|{offset}"
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return base64.urlsafe_b64encode(
        f"{payload}|{checksum}".encode("utf-8")
    ).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str | None,
    *,
    section: StoryBibleSection,
    revision: str,
) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        cursor_revision, cursor_section, raw_offset, checksum = decoded.split("|", 3)
        payload = f"{cursor_revision}|{cursor_section}|{raw_offset}"
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        if checksum != expected or cursor_section != section:
            raise Phase32StoryBibleCursorInvalid(
                "Story Bible cursor does not match its section"
            )
        if cursor_revision != revision:
            raise Phase32StoryBibleCursorStale(
                "Story Bible cursor belongs to a stale projection"
            )
        offset = int(raw_offset)
        if offset < 0:
            raise Phase32StoryBibleCursorInvalid(
                "Story Bible cursor has a negative offset"
            )
        return offset
    except (UnicodeDecodeError, ValueError, base64.binascii.Error) as exc:
        if isinstance(
            exc,
            (Phase32StoryBibleCursorInvalid, Phase32StoryBibleCursorStale),
        ):
            raise
        raise Phase32StoryBibleCursorInvalid("Invalid Story Bible cursor") from exc


__all__ = [
    "Phase32StoryBibleCursorInvalid",
    "Phase32StoryBibleCursorStale",
    "Phase32StoryBibleEntry",
    "Phase32StoryBiblePage",
    "Phase32StoryBibleProjection",
    "Phase32StoryBibleProjectionError",
    "Phase32StoryBibleSource",
    "Phase32StoryBibleSummary",
    "StoryBibleSection",
]

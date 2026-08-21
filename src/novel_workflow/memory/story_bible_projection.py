from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.memory.canon_store import CanonFact, CanonStore
from novel_workflow.memory.resolved_story_state import ResolvedStoryState
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.storage.evidence_store import EvidenceRecord, EvidenceStore


class StoryBibleEvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    chapter_id: str
    chapter_version_id: str
    kind: Literal["fact", "character", "relationship", "foreshadow", "spine"]
    claim: str
    quotes: list[str] = Field(default_factory=list)
    created_at: str


class StoryBibleFactEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    claim: str
    chapter_version_id: str
    subject_id: str = ""
    property_key: str = ""
    value: str = ""
    epistemic_status: Literal["fact", "rumour", "belief", "reveal", "refutation"]
    lifecycle: Literal["active", "supersedes", "resolves", "contradicted"]
    effective_from_chapter: int | None = Field(default=None, ge=1)
    effective_to_chapter: int | None = Field(default=None, ge=1)
    supersedes_fact_ids: list[str] = Field(default_factory=list)
    resolves_fact_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(min_length=1)
    evidence_sources: list[StoryBibleEvidenceSource] = Field(default_factory=list)
    missing_evidence_refs: list[str] = Field(default_factory=list)
    wiki_transaction_ids: list[str] = Field(default_factory=list)
    is_current: bool


class StoryBibleForeshadowEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    claim: str
    chapter_id: str
    chapter_version_id: str
    quotes: list[str] = Field(default_factory=list)
    epistemic_status: Literal["fact", "rumour", "belief", "reveal", "refutation"]
    lifecycle: Literal["active", "supersedes", "resolves", "contradicted"]
    effective_from_chapter: int | None = Field(default=None, ge=1)
    effective_to_chapter: int | None = Field(default=None, ge=1)
    supersedes_fact_ids: list[str] = Field(default_factory=list)
    resolves_fact_ids: list[str] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    wiki_transaction_ids: list[str] = Field(default_factory=list)
    writeback_status: Literal["evidence_only", "canon_committed", "wiki_projected"]


class StoryBibleWikiTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    fact_ids: list[str]


class StoryBibleProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    evidence_count: int = Field(ge=0)
    canon_fact_count: int = Field(ge=0)
    facts: list[StoryBibleFactEntry] = Field(default_factory=list)
    resolved_state: ResolvedStoryState
    foreshadows: list[StoryBibleForeshadowEntry] = Field(default_factory=list)
    wiki_transactions: list[StoryBibleWikiTransaction] = Field(default_factory=list)


def build_story_bible_projection(
    *,
    run_id: str,
    evidence_store: EvidenceStore,
    canon_store: CanonStore,
    wiki_store: WikiProjectionStore,
) -> StoryBibleProjection:
    evidence = sorted(evidence_store.list(run_id), key=_evidence_sort_key)
    evidence_by_id = {item.evidence_id: item for item in evidence}
    canon_facts = sorted(canon_store.facts(run_id), key=_fact_sort_key)
    resolved_state = canon_store.resolved_state(run_id)
    current_fact_ids = {item.source_fact_id for item in resolved_state.entries}

    wiki_transactions, wiki_by_fact = _wiki_provenance(wiki_store, run_id)
    facts = [
        _project_fact(
            fact,
            evidence_by_id=evidence_by_id,
            wiki_by_fact=wiki_by_fact,
            current_fact_ids=current_fact_ids,
        )
        for fact in canon_facts
    ]

    fact_ids_by_evidence: dict[str, list[str]] = {}
    for fact in canon_facts:
        for evidence_id in fact.evidence_refs:
            fact_ids_by_evidence.setdefault(evidence_id, []).append(fact.fact_id)

    foreshadows = [
        _project_foreshadow(
            item,
            fact_ids=sorted(fact_ids_by_evidence.get(item.evidence_id, [])),
            wiki_by_fact=wiki_by_fact,
        )
        for item in evidence
        if item.kind == "foreshadow"
    ]
    return StoryBibleProjection(
        run_id=run_id,
        evidence_count=len(evidence),
        canon_fact_count=len(canon_facts),
        facts=facts,
        resolved_state=resolved_state,
        foreshadows=foreshadows,
        wiki_transactions=wiki_transactions,
    )


def _project_fact(
    fact: CanonFact,
    *,
    evidence_by_id: dict[str, EvidenceRecord],
    wiki_by_fact: dict[str, list[str]],
    current_fact_ids: set[str],
) -> StoryBibleFactEntry:
    sources = [
        _evidence_source(evidence_by_id[evidence_id])
        for evidence_id in fact.evidence_refs
        if evidence_id in evidence_by_id
    ]
    return StoryBibleFactEntry(
        **fact.model_dump(mode="json"),
        evidence_sources=sources,
        missing_evidence_refs=[
            evidence_id
            for evidence_id in fact.evidence_refs
            if evidence_id not in evidence_by_id
        ],
        wiki_transaction_ids=wiki_by_fact.get(fact.fact_id, []),
        is_current=fact.fact_id in current_fact_ids,
    )


def _project_foreshadow(
    evidence: EvidenceRecord,
    *,
    fact_ids: list[str],
    wiki_by_fact: dict[str, list[str]],
) -> StoryBibleForeshadowEntry:
    wiki_transaction_ids = sorted(
        {
            transaction_id
            for fact_id in fact_ids
            for transaction_id in wiki_by_fact.get(fact_id, [])
        }
    )
    writeback_status: Literal["evidence_only", "canon_committed", "wiki_projected"]
    if wiki_transaction_ids:
        writeback_status = "wiki_projected"
    elif fact_ids:
        writeback_status = "canon_committed"
    else:
        writeback_status = "evidence_only"
    return StoryBibleForeshadowEntry(
        evidence_id=evidence.evidence_id,
        claim=evidence.claim,
        chapter_id=evidence.chapter_id,
        chapter_version_id=evidence.chapter_version_id,
        quotes=[span.quote for span in evidence.spans],
        epistemic_status=evidence.epistemic_status,
        lifecycle=evidence.lifecycle,
        effective_from_chapter=evidence.effective_from_chapter,
        effective_to_chapter=evidence.effective_to_chapter,
        supersedes_fact_ids=evidence.supersedes_fact_ids,
        resolves_fact_ids=evidence.resolves_fact_ids,
        fact_ids=fact_ids,
        wiki_transaction_ids=wiki_transaction_ids,
        writeback_status=writeback_status,
    )


def _wiki_provenance(
    wiki_store: WikiProjectionStore,
    run_id: str,
) -> tuple[list[StoryBibleWikiTransaction], dict[str, list[str]]]:
    projected: list[StoryBibleWikiTransaction] = []
    by_fact: dict[str, list[str]] = {}
    for raw in wiki_store.list(run_id):
        transaction_id = str(raw.get("transaction_id") or "").strip()
        if not transaction_id:
            raise ValueError("Wiki projection is missing its transaction identity")
        raw_facts = raw.get("facts")
        if not isinstance(raw_facts, list):
            raise ValueError("Wiki projection facts must be a list")
        fact_ids = sorted(
            CanonFact.model_validate(raw_fact).fact_id for raw_fact in raw_facts
        )
        projected.append(
            StoryBibleWikiTransaction(
                transaction_id=transaction_id,
                fact_ids=fact_ids,
            )
        )
        for fact_id in fact_ids:
            by_fact.setdefault(fact_id, []).append(transaction_id)
    projected.sort(key=lambda item: item.transaction_id)
    for transaction_ids in by_fact.values():
        transaction_ids.sort()
    return projected, by_fact


def _evidence_source(evidence: EvidenceRecord) -> StoryBibleEvidenceSource:
    return StoryBibleEvidenceSource(
        evidence_id=evidence.evidence_id,
        chapter_id=evidence.chapter_id,
        chapter_version_id=evidence.chapter_version_id,
        kind=evidence.kind,
        claim=evidence.claim,
        quotes=[span.quote for span in evidence.spans],
        created_at=evidence.created_at,
    )


def _evidence_sort_key(evidence: EvidenceRecord) -> tuple[int, str, str]:
    chapter = evidence.effective_from_chapter or _chapter_number(evidence.chapter_id)
    return chapter, evidence.chapter_version_id, evidence.evidence_id


def _fact_sort_key(fact: CanonFact) -> tuple[int, str, str]:
    chapter = fact.effective_from_chapter or _chapter_number(fact.chapter_version_id)
    return chapter, fact.chapter_version_id, fact.fact_id


def _chapter_number(value: str) -> int:
    match = re.search(r"(?:chapter|ch)[-:]?(\d+)", value, re.IGNORECASE)
    return int(match.group(1)) if match else 0


__all__ = [
    "StoryBibleEvidenceSource",
    "StoryBibleFactEntry",
    "StoryBibleForeshadowEntry",
    "StoryBibleProjection",
    "StoryBibleWikiTransaction",
    "build_story_bible_projection",
]

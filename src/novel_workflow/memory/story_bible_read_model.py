from __future__ import annotations

import base64
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.memory.canon_store import CanonStore
from novel_workflow.memory.resolved_story_state import StoryStateConflict
from novel_workflow.memory.story_bible_projection import (
    StoryBibleFactEntry,
    StoryBibleForeshadowEntry,
    build_story_bible_projection,
)
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.storage.atomic_json import (
    atomic_write_json,
    read_json,
    require_safe_id,
)
from novel_workflow.storage.evidence_store import EvidenceStore


StoryBibleSection = Literal["facts", "foreshadow"]
StoryBibleItem = StoryBibleFactEntry | StoryBibleForeshadowEntry
ItemT = TypeVar("ItemT", bound=StoryBibleItem)


class StoryBibleCursorInvalid(ValueError):
    """The client supplied a malformed or mismatched page cursor."""


class StoryBibleCursorStale(ValueError):
    """The source ledgers changed after the cursor's snapshot was created."""


class StoryBibleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_count: int = Field(ge=0)
    canon_fact_count: int = Field(ge=0)
    current_fact_count: int = Field(ge=0)
    wiki_projected_fact_count: int = Field(ge=0)
    foreshadow_count: int = Field(ge=0)
    foreshadow_tracking_count: int = Field(ge=0)
    foreshadow_resolved_count: int = Field(ge=0)
    as_of_chapter: int | None = Field(default=None, ge=0)
    conflicts: list[StoryStateConflict] = Field(default_factory=list)


class StoryBiblePage(BaseModel, Generic[ItemT]):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    section: StoryBibleSection
    summary: StoryBibleSummary
    items: list[ItemT] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None = None


class _StoryBibleManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_revision: str
    built_at: str
    summary: StoryBibleSummary
    fact_ids: list[str] = Field(default_factory=list)
    foreshadow_ids: list[str] = Field(default_factory=list)


class StoryBibleReadModelStore:
    """Rebuildable, cursor-paged projection over immutable story ledgers.

    Source directory revisions make ordinary reads O(1) with respect to the
    Canon/Evidence/Wiki transaction count. A legacy Run is rebuilt lazily once,
    and each page then reads only its bounded item files.
    """

    def __init__(
        self,
        root: Path,
        *,
        evidence: EvidenceStore,
        canon: CanonStore,
        wiki: WikiProjectionStore,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.evidence = evidence
        self.canon = canon
        self.wiki = wiki
        self._lock = threading.RLock()

    def page(
        self,
        run_id: str,
        *,
        section: StoryBibleSection,
        limit: int,
        cursor: str | None = None,
    ) -> StoryBiblePage[StoryBibleItem]:
        require_safe_id(run_id, label="run_id")
        if section not in {"facts", "foreshadow"}:
            raise StoryBibleCursorInvalid("Unknown Story Bible section")
        if limit < 1 or limit > 100:
            raise StoryBibleCursorInvalid("Story Bible page limit must be 1..100")

        with self._lock:
            manifest = self._current_manifest(run_id)
            offset = self._decode_cursor(
                cursor,
                section=section,
                source_revision=manifest.source_revision,
            )
            item_ids = (
                manifest.fact_ids
                if section == "facts"
                else manifest.foreshadow_ids
            )
            if offset > len(item_ids):
                raise StoryBibleCursorInvalid("Story Bible cursor is out of range")
            selected_ids = item_ids[offset : offset + limit]
            items = [
                self._read_item(run_id, section=section, item_id=item_id)
                for item_id in selected_ids
            ]
            next_offset = offset + len(items)
            next_cursor = (
                self._encode_cursor(
                    source_revision=manifest.source_revision,
                    section=section,
                    offset=next_offset,
                )
                if next_offset < len(item_ids)
                else None
            )
            return StoryBiblePage[StoryBibleItem](
                run_id=run_id,
                section=section,
                summary=manifest.summary,
                items=items,
                total=len(item_ids),
                limit=limit,
                next_cursor=next_cursor,
            )

    def rebuild(self, run_id: str) -> _StoryBibleManifest:
        """Rebuild a stable snapshot, including legacy Runs with no index."""

        require_safe_id(run_id, label="run_id")
        with self._lock:
            for _ in range(3):
                before = self._source_revision(run_id)
                projection = build_story_bible_projection(
                    run_id=run_id,
                    evidence_store=self.evidence,
                    canon_store=self.canon,
                    wiki_store=self.wiki,
                )
                after = self._source_revision(run_id)
                if before != after:
                    continue

                for item in projection.facts:
                    self._write_item(
                        run_id,
                        section="facts",
                        item_id=item.fact_id,
                        item=item,
                    )
                for item in projection.foreshadows:
                    self._write_item(
                        run_id,
                        section="foreshadow",
                        item_id=item.evidence_id,
                        item=item,
                    )
                manifest = _StoryBibleManifest(
                    run_id=run_id,
                    source_revision=after,
                    built_at=datetime.now(timezone.utc).isoformat(),
                    summary=_summary(projection),
                    fact_ids=[item.fact_id for item in projection.facts],
                    foreshadow_ids=[
                        item.evidence_id for item in projection.foreshadows
                    ],
                )
                atomic_write_json(
                    self._manifest_path(run_id),
                    manifest.model_dump(mode="json"),
                )
                return manifest
        raise RuntimeError("Story Bible sources changed during projection rebuild")

    def _current_manifest(self, run_id: str) -> _StoryBibleManifest:
        revision = self._source_revision(run_id)
        try:
            manifest = _StoryBibleManifest.model_validate(
                read_json(self._manifest_path(run_id))
            )
        except FileNotFoundError:
            return self.rebuild(run_id)
        if manifest.run_id != run_id or manifest.source_revision != revision:
            return self.rebuild(run_id)
        return manifest

    def _source_revision(self, run_id: str) -> str:
        parts = []
        for store in (self.evidence, self.canon, self.wiki):
            directory = store.root / run_id
            try:
                stat = directory.stat()
                parts.append(f"{stat.st_mtime_ns}:{stat.st_size}")
            except FileNotFoundError:
                parts.append("0:0")
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def _read_item(
        self,
        run_id: str,
        *,
        section: StoryBibleSection,
        item_id: str,
    ) -> StoryBibleItem:
        raw = read_json(self._item_path(run_id, section=section, item_id=item_id))
        if section == "facts":
            return StoryBibleFactEntry.model_validate(raw)
        return StoryBibleForeshadowEntry.model_validate(raw)

    def _write_item(
        self,
        run_id: str,
        *,
        section: StoryBibleSection,
        item_id: str,
        item: StoryBibleItem,
    ) -> None:
        atomic_write_json(
            self._item_path(run_id, section=section, item_id=item_id),
            item.model_dump(mode="json"),
        )

    def _manifest_path(self, run_id: str) -> Path:
        return self.root / run_id / "manifest.json"

    def _item_path(
        self,
        run_id: str,
        *,
        section: StoryBibleSection,
        item_id: str,
    ) -> Path:
        digest = hashlib.sha256(item_id.encode("utf-8")).hexdigest()
        return self.root / run_id / section / f"{digest}.json"

    @staticmethod
    def _encode_cursor(
        *,
        source_revision: str,
        section: StoryBibleSection,
        offset: int,
    ) -> str:
        payload = f"{source_revision}|{section}|{offset}"
        checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return base64.urlsafe_b64encode(
            f"{payload}|{checksum}".encode("utf-8")
        ).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(
        cursor: str | None,
        *,
        section: StoryBibleSection,
        source_revision: str,
    ) -> int:
        if cursor is None:
            return 0
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
            revision, cursor_section, raw_offset, checksum = decoded.split("|", 3)
            payload = f"{revision}|{cursor_section}|{raw_offset}"
            expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
            if checksum != expected or cursor_section != section:
                raise StoryBibleCursorInvalid("Story Bible cursor does not match section")
            if revision != source_revision:
                raise StoryBibleCursorStale("Story Bible cursor belongs to a stale snapshot")
            offset = int(raw_offset)
            if offset < 0:
                raise StoryBibleCursorInvalid("Story Bible cursor has a negative offset")
            return offset
        except (UnicodeDecodeError, ValueError, base64.binascii.Error) as exc:
            if isinstance(exc, (StoryBibleCursorInvalid, StoryBibleCursorStale)):
                raise
            raise StoryBibleCursorInvalid("Invalid Story Bible cursor") from exc


def _summary(projection) -> StoryBibleSummary:
    return StoryBibleSummary(
        evidence_count=projection.evidence_count,
        canon_fact_count=projection.canon_fact_count,
        current_fact_count=sum(item.is_current for item in projection.facts),
        wiki_projected_fact_count=sum(
            bool(item.wiki_transaction_ids) for item in projection.facts
        ),
        foreshadow_count=len(projection.foreshadows),
        foreshadow_tracking_count=sum(
            item.lifecycle == "active" and item.writeback_status != "evidence_only"
            for item in projection.foreshadows
        ),
        foreshadow_resolved_count=sum(
            item.lifecycle == "resolves" for item in projection.foreshadows
        ),
        as_of_chapter=projection.resolved_state.as_of_chapter,
        conflicts=projection.resolved_state.conflicts,
    )


__all__ = [
    "StoryBibleCursorInvalid",
    "StoryBibleCursorStale",
    "StoryBiblePage",
    "StoryBibleReadModelStore",
    "StoryBibleSection",
    "StoryBibleSummary",
]

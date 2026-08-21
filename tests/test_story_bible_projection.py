from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.memory.canon_store import CanonFact, CanonStore
from novel_workflow.memory.story_bible_projection import build_story_bible_projection
from novel_workflow.memory.story_bible_read_model import (
    StoryBibleCursorInvalid,
    StoryBibleCursorStale,
    StoryBibleReadModelStore,
)
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.storage.evidence_store import EvidenceRecord, EvidenceSpan, EvidenceStore
from tests.phase27_api import configure_phase27_providers


def test_empty_story_bible_projection_is_explicit(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)

    projection = build_story_bible_projection(
        run_id="run-empty",
        evidence_store=evidence,
        canon_store=canon,
        wiki_store=wiki,
    )

    assert projection.evidence_count == 0
    assert projection.canon_fact_count == 0
    assert projection.facts == []
    assert projection.foreshadows == []
    assert projection.resolved_state.entries == []
    assert projection.resolved_state.conflicts == []


def test_projection_preserves_fact_evidence_and_wiki_provenance(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    source = _evidence(
        evidence,
        claim="林澈把母带交给档案馆。",
        value="母带已入馆",
    )
    fact = _canon_fact(source)
    canon.commit("run-1", "canon-chapter-1-v1", [fact])
    wiki.project("run-1", "canon-chapter-1-v1", [fact])

    projection = build_story_bible_projection(
        run_id="run-1",
        evidence_store=evidence,
        canon_store=canon,
        wiki_store=wiki,
    )

    assert projection.evidence_count == 1
    assert projection.canon_fact_count == 1
    entry = projection.facts[0]
    assert entry.fact_id == fact.fact_id
    assert entry.is_current is True
    assert entry.missing_evidence_refs == []
    assert entry.wiki_transaction_ids == ["canon-chapter-1-v1"]
    assert entry.evidence_sources[0].evidence_id == source.evidence_id
    assert entry.evidence_sources[0].chapter_id == "chapter-1"
    assert entry.evidence_sources[0].quotes == ["她把修复后的母带交给档案馆。"]


def test_projection_keeps_unresolved_canon_conflicts_visible(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    first = _evidence(evidence, claim="林澈仍在旧港。", value="旧港")
    second = _evidence(
        evidence,
        chapter=2,
        claim="林澈已经抵达北站。",
        value="北站",
    )
    first_fact = _canon_fact(first)
    second_fact = _canon_fact(second)
    canon.commit("run-1", "canon-conflict", [first_fact, second_fact])

    projection = build_story_bible_projection(
        run_id="run-1",
        evidence_store=evidence,
        canon_store=canon,
        wiki_store=wiki,
    )

    assert len(projection.resolved_state.conflicts) == 1
    conflict = projection.resolved_state.conflicts[0]
    assert conflict.subject_id == "subject-lin"
    assert conflict.property_key == "location"
    assert conflict.fact_ids == [first_fact.fact_id, second_fact.fact_id]
    assert conflict.values == ["旧港", "北站"]


def test_projection_marks_missing_evidence_without_guessing_a_source(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    missing = CanonFact(
        fact_id="fact-missing-source",
        claim="来源文件已经被移除。",
        evidence_refs=["evidence-not-present"],
        chapter_version_id="chapter-1-v1",
    )
    canon.commit("run-1", "canon-missing-source", [missing])

    projection = build_story_bible_projection(
        run_id="run-1",
        evidence_store=evidence,
        canon_store=canon,
        wiki_store=wiki,
    )

    assert projection.facts[0].missing_evidence_refs == ["evidence-not-present"]
    assert projection.facts[0].evidence_sources == []
    assert projection.facts[0].is_current is True


def test_foreshadow_projection_exposes_lifecycle_and_writeback_state(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    projected = _evidence(
        evidence,
        kind="foreshadow",
        claim="母带缺失的第七码仍未解释。",
        value="第七码缺失",
    )
    projected_fact = _canon_fact(projected)
    canon.commit("run-1", "canon-foreshadow-1", [projected_fact])
    wiki.project("run-1", "canon-foreshadow-1", [projected_fact])

    committed = _evidence(
        evidence,
        chapter=2,
        kind="foreshadow",
        claim="第七码来自应急频道。",
        value="应急频道",
        lifecycle="resolves",
        resolves_fact_ids=[projected_fact.fact_id],
    )
    committed_fact = _canon_fact(committed)
    canon.commit("run-1", "canon-foreshadow-2", [committed_fact])

    evidence_only = _evidence(
        evidence,
        chapter=3,
        kind="foreshadow",
        claim="档案柜上的新划痕尚未写回。",
        value="新划痕",
        lifecycle="active",
    )

    projection = build_story_bible_projection(
        run_id="run-1",
        evidence_store=evidence,
        canon_store=canon,
        wiki_store=wiki,
    )

    by_id = {item.evidence_id: item for item in projection.foreshadows}
    assert by_id[projected.evidence_id].writeback_status == "wiki_projected"
    assert by_id[committed.evidence_id].writeback_status == "canon_committed"
    assert by_id[committed.evidence_id].lifecycle == "resolves"
    assert by_id[committed.evidence_id].resolves_fact_ids == [projected_fact.fact_id]
    assert by_id[evidence_only.evidence_id].writeback_status == "evidence_only"
    assert by_id[evidence_only.evidence_id].fact_ids == []


def test_story_bible_api_uses_current_run_guard(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "故事圣经接口验证。"}).json()
    created = client.post(
        "/api/runs",
        json={
            "run_id": "story-bible-run",
            "project_id": project["id"],
            "workflow_id": project["workflow_id"],
            "inputs": {"length_envelope": {"word_target_soft": 12_000}},
            "export_preferences": {"format": "zip"},
        },
    )
    assert created.status_code == 200

    response = client.get("/api/runs/story-bible-run/story-bible")
    assert response.status_code == 200
    assert response.json()["run_id"] == "story-bible-run"
    assert response.json()["section"] == "facts"
    assert response.json()["items"] == []
    assert client.get("/api/runs/missing/story-bible").status_code == 404

    definition_path = (
        tmp_path
        / "runtime"
        / "novel_workflow"
        / "native_runtime"
        / "runs"
        / "story-bible-run"
        / "definition.json"
    )
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    definition["scale_profile"]["chapter_min_reasonable"] = 1
    definition_path.write_text(json.dumps(definition), encoding="utf-8")

    retired = client.get("/api/runs/story-bible-run/story-bible")
    assert retired.status_code == 409
    assert retired.json()["detail"]["code"] == "run_contract_retired"


def test_read_model_pages_in_stable_order_without_duplicates(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    facts = []
    for chapter in range(1, 6):
        source = _evidence(
            evidence,
            chapter=chapter,
            claim=f"第 {chapter} 章事实。",
            value=f"位置-{chapter}",
        )
        facts.append(_canon_fact(source))
    canon.commit("run-1", "canon-five-facts", facts)
    wiki.project("run-1", "canon-five-facts", facts)
    read_model = StoryBibleReadModelStore(
        tmp_path / "story-bible",
        evidence=evidence,
        canon=canon,
        wiki=wiki,
    )

    first = read_model.page("run-1", section="facts", limit=2)
    second = read_model.page(
        "run-1",
        section="facts",
        limit=2,
        cursor=first.next_cursor,
    )
    third = read_model.page(
        "run-1",
        section="facts",
        limit=2,
        cursor=second.next_cursor,
    )

    fact_ids = [item.fact_id for page in (first, second, third) for item in page.items]
    assert fact_ids == [item.fact_id for item in facts]
    assert len(set(fact_ids)) == 5
    assert first.total == second.total == third.total == 5
    assert first.next_cursor and second.next_cursor
    assert third.next_cursor is None
    assert len(first.items) == len(second.items) == 2
    assert len(third.items) == 1


def test_read_model_handles_empty_legacy_run_and_persists_manifest(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    read_model = StoryBibleReadModelStore(
        tmp_path / "story-bible",
        evidence=evidence,
        canon=canon,
        wiki=wiki,
    )

    page = read_model.page("run-empty", section="foreshadow", limit=50)

    assert page.items == []
    assert page.total == 0
    assert page.next_cursor is None
    assert (tmp_path / "story-bible" / "run-empty" / "manifest.json").exists()


def test_read_model_rejects_invalid_cross_section_and_stale_cursors(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    facts = []
    for chapter in range(1, 4):
        source = _evidence(
            evidence,
            chapter=chapter,
            claim=f"游标事实 {chapter}。",
            value=f"值-{chapter}",
        )
        facts.append(_canon_fact(source))
    canon.commit("run-1", "canon-cursor", facts)
    read_model = StoryBibleReadModelStore(
        tmp_path / "story-bible",
        evidence=evidence,
        canon=canon,
        wiki=wiki,
    )
    first = read_model.page("run-1", section="facts", limit=1)
    assert first.next_cursor

    with pytest.raises(StoryBibleCursorInvalid):
        read_model.page("run-1", section="facts", limit=1, cursor="broken")
    with pytest.raises(StoryBibleCursorInvalid):
        read_model.page(
            "run-1",
            section="foreshadow",
            limit=1,
            cursor=first.next_cursor,
        )

    _evidence(
        evidence,
        chapter=4,
        kind="foreshadow",
        claim="新增伏笔使快照失效。",
        value="新伏笔",
    )
    with pytest.raises(StoryBibleCursorStale):
        read_model.page(
            "run-1",
            section="facts",
            limit=1,
            cursor=first.next_cursor,
        )


def test_read_model_refreshes_wiki_summary_idempotently(tmp_path) -> None:
    evidence, canon, wiki = _stores(tmp_path)
    source = _evidence(evidence, claim="事实先进入 Canon。", value="已提交")
    fact = _canon_fact(source)
    canon.commit("run-1", "canon-late-wiki", [fact])
    read_model = StoryBibleReadModelStore(
        tmp_path / "story-bible",
        evidence=evidence,
        canon=canon,
        wiki=wiki,
    )
    before = read_model.page("run-1", section="facts", limit=50)
    assert before.summary.wiki_projected_fact_count == 0

    wiki.project("run-1", "canon-late-wiki", [fact])
    refreshed = read_model.page("run-1", section="facts", limit=50)
    replayed = read_model.page("run-1", section="facts", limit=50)

    assert refreshed.summary.wiki_projected_fact_count == 1
    assert refreshed.items[0].wiki_transaction_ids == ["canon-late-wiki"]
    assert replayed == refreshed


def _stores(tmp_path) -> tuple[EvidenceStore, CanonStore, WikiProjectionStore]:
    return (
        EvidenceStore(tmp_path / "evidence"),
        CanonStore(tmp_path / "canon"),
        WikiProjectionStore(tmp_path / "wiki"),
    )


def _evidence(
    store: EvidenceStore,
    *,
    chapter: int = 1,
    kind: str = "fact",
    claim: str,
    value: str,
    lifecycle: str = "active",
    resolves_fact_ids: list[str] | None = None,
) -> EvidenceRecord:
    return store.write(
        run_id="run-1",
        chapter_id=f"chapter-{chapter}",
        chapter_version_id=f"chapter-{chapter}-v1",
        kind=kind,  # type: ignore[arg-type]
        claim=claim,
        spans=[EvidenceSpan(start=0, end=16, quote="她把修复后的母带交给档案馆。")],
        subject_id="subject-lin",
        property_key="location",
        value=value,
        lifecycle=lifecycle,  # type: ignore[arg-type]
        effective_from_chapter=chapter,
        resolves_fact_ids=resolves_fact_ids,
    )


def _canon_fact(evidence: EvidenceRecord) -> CanonFact:
    return CanonFact(
        fact_id=f"fact-{evidence.evidence_id.removeprefix('evidence-')}",
        claim=evidence.claim,
        evidence_refs=[evidence.evidence_id],
        chapter_version_id=evidence.chapter_version_id,
        subject_id=evidence.subject_id,
        property_key=evidence.property_key,
        value=evidence.value,
        epistemic_status=evidence.epistemic_status,
        lifecycle=evidence.lifecycle,
        effective_from_chapter=evidence.effective_from_chapter,
        effective_to_chapter=evidence.effective_to_chapter,
        supersedes_fact_ids=evidence.supersedes_fact_ids,
        resolves_fact_ids=evidence.resolves_fact_ids,
    )

from __future__ import annotations

from novel_workflow.memory.canon_store import CanonFact, CanonStore
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.storage.domain_outbox import DomainOutbox
from novel_workflow.storage.event_projection import EventProjection
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ExportPreferences, NarrativeRunRepository, ProviderBinding, RunReadModel
from novel_workflow.storage.operation_store import OperationStore
from novel_workflow.workflows.book_scale_plan import build_book_scale_plan


def test_run_repository_separates_definition_from_graph_projection(tmp_path) -> None:
    store = NarrativeRunRepository(tmp_path / "runs")
    definition = store.create(
        run_id="run-1",
        project_id="project-1",
        workflow_revision="phase26",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=build_book_scale_plan(target_mode="total_chapters", target_value=3),
        provider_bindings={"info": ProviderBinding(provider_profile_id="fake", model="fake-model")},
        cover_asset_binding=CoverAssetBinding(
            provider_profile_id="fake-image", model="fake-image-model",
            candidate_count=1, size="256x384", quality="medium",
        ),
        export_preferences=ExportPreferences(format="zip"),
    )
    projected = store.project(
        "run-1",
        RunReadModel(
            run_id="run-1",
            project_id="project-1",
            thread_id="run-1",
            status="running",
            active_stage_id="info",
            stage_status={
                "info": "running",
                "characters": "locked",
                "summary": "locked",
                "outline": "locked",
                "detail": "locked",
                "text": "locked",
                "cover": "locked",
                "export": "locked",
            },
            updated_at="ignored",
        ),
    )

    assert definition.inputs == {"genre": "悬疑"}
    assert store.definition("run-1") == definition
    assert projected.status == "running"
    assert "status" not in store.definition("run-1").model_dump()


def test_event_projection_has_stable_sequence_and_idempotent_event_ids(tmp_path) -> None:
    events = EventProjection(tmp_path / "events")
    first = events.append("run-1", event_id="run-1:start", type="run.started", stage_id="info")
    duplicate = events.append("run-1", event_id="run-1:start", type="run.started", stage_id="info")
    second = events.append("run-1", event_id="run-1:info", type="node.started", stage_id="info")

    assert first == duplicate
    assert second.sequence == 2
    assert [item.sequence for item in events.read("run-1", after=1)] == [2]


def test_operation_receipts_do_not_repeat_or_change_completed_results(tmp_path) -> None:
    store = OperationStore(tmp_path / "operations")
    pending = store.begin(
        run_id="run-1",
        operation_key="run-1:info:generate",
        kind="generation",
        request_signature="a" * 64,
        provider_profile_id="fake",
        model="fake-model",
    )
    assert store.begin(
        run_id="run-1",
        operation_key="run-1:info:generate",
        kind="generation",
        request_signature="a" * 64,
    ) == pending
    completed = store.succeed("run-1", "run-1:info:generate", {"title": "雾港"})
    assert completed.status == "succeeded"
    assert store.succeed("run-1", "run-1:info:generate", {"title": "不同结果"}) == completed


def test_outbox_commits_canon_and_wiki_exactly_once(tmp_path) -> None:
    canon = CanonStore(tmp_path / "canon")
    wiki = WikiProjectionStore(tmp_path / "wiki")
    outbox = DomainOutbox(tmp_path / "outbox", canon=canon, wiki=wiki)
    fact = CanonFact(
        fact_id="fact-1",
        claim="林默在雾港仓库找到母带副本。",
        evidence_refs=["evidence-1"],
        chapter_version_id="chapter-1-v1",
    )
    outbox.enqueue("run-1", "outbox-chapter-1", "canon-chapter-1", [fact])

    first = outbox.flush("run-1", "outbox-chapter-1")
    second = outbox.flush("run-1", "outbox-chapter-1")

    assert first == second
    assert canon.facts("run-1") == [fact]
    assert len(wiki.list("run-1")) == 1


def test_outbox_replays_after_a_crash_before_canon_commit(tmp_path, monkeypatch) -> None:
    canon = CanonStore(tmp_path / "canon")
    wiki = WikiProjectionStore(tmp_path / "wiki")
    root = tmp_path / "outbox"
    outbox = DomainOutbox(root, canon=canon, wiki=wiki)
    fact = CanonFact(
        fact_id="fact-before-canon",
        claim="林默尚未公开母带。",
        evidence_refs=["evidence-before-canon"],
        chapter_version_id="chapter-1-v1",
    )
    outbox.enqueue("run-crash", "outbox-before-canon", "canon-before-canon", [fact])

    def crash_before_commit(*args, **kwargs):
        raise RuntimeError("process stopped before Canon commit")

    monkeypatch.setattr(canon, "commit", crash_before_commit)
    try:
        outbox.flush("run-crash", "outbox-before-canon")
    except RuntimeError:
        pass

    assert outbox.read("run-crash", "outbox-before-canon").status == "failed"
    assert canon.facts("run-crash") == []
    assert wiki.list("run-crash") == []

    replayed = DomainOutbox(root, canon=CanonStore(tmp_path / "canon"), wiki=WikiProjectionStore(tmp_path / "wiki"))
    receipt = replayed.flush("run-crash", "outbox-before-canon")

    assert receipt.status == "committed"
    assert replayed.canon.facts("run-crash") == [fact]
    assert len(replayed.wiki.list("run-crash")) == 1


def test_outbox_replays_after_canon_commit_without_duplicate_facts(tmp_path, monkeypatch) -> None:
    canon_root = tmp_path / "canon"
    wiki_root = tmp_path / "wiki"
    outbox_root = tmp_path / "outbox"
    canon = CanonStore(canon_root)
    wiki = WikiProjectionStore(wiki_root)
    outbox = DomainOutbox(outbox_root, canon=canon, wiki=wiki)
    fact = CanonFact(
        fact_id="fact-after-canon",
        claim="林默公开了母带。",
        evidence_refs=["evidence-after-canon"],
        chapter_version_id="chapter-1-v1",
    )
    outbox.enqueue("run-crash", "outbox-after-canon", "canon-after-canon", [fact])

    def crash_before_projection(*args, **kwargs):
        raise RuntimeError("process stopped before Wiki projection")

    monkeypatch.setattr(wiki, "project", crash_before_projection)
    try:
        outbox.flush("run-crash", "outbox-after-canon")
    except RuntimeError:
        pass

    assert outbox.read("run-crash", "outbox-after-canon").status == "failed"
    assert canon.facts("run-crash") == [fact]
    assert wiki.list("run-crash") == []

    replayed = DomainOutbox(
        outbox_root,
        canon=CanonStore(canon_root),
        wiki=WikiProjectionStore(wiki_root),
    )
    receipt = replayed.flush("run-crash", "outbox-after-canon")

    assert receipt.status == "committed"
    assert replayed.canon.facts("run-crash") == [fact]
    assert len(replayed.wiki.list("run-crash")) == 1

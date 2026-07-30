from __future__ import annotations

from novel_workflow.memory.canon import commit_canon_writebacks, preview_canon_writebacks


def test_preview_marks_same_claim_with_different_fact_as_explainable_conflict() -> None:
    preview = preview_canon_writebacks(
        [{
            "id": "canon-fact-1",
            "target": "母带",
            "claim_key": "location",
            "fact": "保存在档案馆",
            "status": "active",
        }],
        [{"target": "母带", "claim_key": "location", "fact": "被转移到码头"}],
        chapter_id="chapter-2",
        chapter="第2章",
        chapter_version=4,
        artifact_signature="a" * 64,
    )

    assert preview["candidates"][0]["status"] == "conflict"
    assert preview["conflicts"][0]["existing_fact"] == "保存在档案馆"
    assert preview["conflicts"][0]["incoming_fact"] == "被转移到码头"


def test_keep_existing_does_not_replace_canon_or_write_wiki() -> None:
    proposal = {
        "id": "proposal-1",
        "status": "accepted",
        "canon": {
            "candidates": [{
                "id": "candidate-1",
                "target": "母带",
                "claim_key": "location",
                "fact": "被转移到码头",
                "normalized_fact": "被转移到码头",
                "status": "conflict",
                "conflict_id": "conflict-1",
                "source": {"chapter": "第2章"},
                "writeback": {"target": "母带", "claim_key": "location", "fact": "被转移到码头"},
            }],
            "conflicts": [{
                "id": "conflict-1",
                "status": "pending",
                "target": "母带",
                "claim_key": "location",
                "existing_fact_id": "canon-fact-1",
                "existing_fact": "保存在档案馆",
                "incoming_fact": "被转移到码头",
            }],
        },
        "wiki_writebacks": [{"target": "母带", "fact": "被转移到码头"}],
    }
    result = commit_canon_writebacks(
        [{"id": "canon-fact-1", "target": "母带", "claim_key": "location", "fact": "保存在档案馆", "status": "active"}],
        [],
        {"writeback_proposal": {**proposal, "conflict_resolutions": {"conflict-1": "keep_existing"}}},
    )

    assert len(result["facts"]) == 1
    assert result["effective_writebacks"] == []
    assert result["resolved"][0]["resolution"] == "keep_existing"


def test_replace_existing_supersedes_old_fact_and_returns_effective_writeback() -> None:
    proposal = {
        "id": "proposal-1",
        "status": "accepted",
        "canon": {
            "candidates": [{
                "id": "candidate-1",
                "target": "母带",
                "claim_key": "location",
                "fact": "被转移到码头",
                "normalized_fact": "被转移到码头",
                "status": "conflict",
                "conflict_id": "conflict-1",
                "source": {"chapter": "第2章"},
                "writeback": {"target": "母带", "claim_key": "location", "fact": "被转移到码头"},
            }],
            "conflicts": [{"id": "conflict-1", "existing_fact_id": "canon-fact-1", "target": "母带"}],
        },
        "wiki_writebacks": [],
    }
    result = commit_canon_writebacks(
        [{"id": "canon-fact-1", "target": "母带", "claim_key": "location", "fact": "保存在档案馆", "status": "active"}],
        [],
        {"writeback_proposal": {**proposal, "conflict_resolutions": {"conflict-1": "replace_existing"}}},
    )

    assert result["facts"][0]["status"] == "superseded"
    assert result["facts"][1]["fact"] == "被转移到码头"
    assert result["effective_writebacks"][0]["claim_key"] == "location"


def test_automatic_writeback_keeps_unresolved_conflict_pending() -> None:
    result = commit_canon_writebacks(
        [{"id": "canon-fact-1", "target": "母带", "claim_key": "location", "fact": "保存在档案馆", "status": "active"}],
        [],
        {"id": "chapter-2", "title": "第2章", "version": 2, "wiki_writebacks": [{"target": "母带", "claim_key": "location", "fact": "被转移到码头"}]},
    )

    assert result["effective_writebacks"] == []
    assert result["conflicts"][0]["status"] == "pending"

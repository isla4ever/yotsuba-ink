from __future__ import annotations

from pathlib import Path

from novel_workflow.storage.phase32_artifact_draft_store import (
    Phase32ArtifactDraftStore,
)


def test_phase32_draft_store_preserves_history_and_latest_pointer(tmp_path: Path) -> None:
    store = Phase32ArtifactDraftStore(tmp_path)
    common = {
        "run_id": "run-draft-history",
        "decision_id": "run-draft-history:brief:candidate-1",
        "domain_revision": 0,
        "creation_route_id": "short_novel",
        "stage_id": "brief",
        "source_artifact_ref": "p32-brief-candidate-" + "a" * 32,
    }
    first = store.save(**common, payload={"premise": "第一版"})
    second = store.save(**common, payload={"premise": "第二版"})

    assert first.draft_ref != second.draft_ref
    assert store.read(common["run_id"], common["decision_id"], first.draft_ref) == first
    assert store.latest(common["run_id"], common["decision_id"]) == second
    assert [item.draft_ref for item in store.list(common["run_id"], common["decision_id"])] == [
        first.draft_ref,
        second.draft_ref,
    ]

from __future__ import annotations

from novel_workflow.storage.stage_artifact_draft_store import StageArtifactDraftStore
from tests.fakes import fake_brief_payload


def test_stage_artifact_draft_store_keeps_history_and_latest_decision_pointer(
    tmp_path,
) -> None:
    store = StageArtifactDraftStore(tmp_path / "stage_drafts")
    first_payload = {**fake_brief_payload(), "title": "盐潮旧证"}
    second_payload = {**first_payload, "title": "盐潮证词"}
    binding = {
        "run_id": "run-1",
        "stage_id": "brief",
        "decision_id": "run-1:brief:candidate-1",
        "domain_revision": 0,
        "source_artifact_id": "brief-candidate-1",
    }

    first = store.save(**binding, payload=first_payload)
    second = store.save(**binding, payload=second_payload)

    assert first.draft_id != second.draft_id
    assert store.read("run-1", first.draft_id) == first
    assert store.latest("run-1", binding["decision_id"]) == second
    assert store.list("run-1") == [first, second]
    assert store.save(**binding, payload=second_payload) == second
    assert store.save(**binding, payload=first_payload) == first
    assert store.latest("run-1", binding["decision_id"]) == first

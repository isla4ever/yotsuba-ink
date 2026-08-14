from __future__ import annotations

from novel_workflow.storage.artifact_store import ArtifactStore


def story_brief() -> dict[str, object]:
    return {
        "title": "雾港母带",
        "premise": "声音 archivist 在封闭港区追查一卷会改写公共记忆的母带。",
        "promise": "真相伴随代价。",
        "world_rules": ["公开广播会覆盖个人记忆"],
        "theme": "真相的代价",
        "ending_promise": "母带真相将被公开并改变港区秩序。",
        "voice": "第三人称限知、听觉细节驱动",
        "length_envelope": {"word_target_soft": 10000, "chapter_target_soft": 2},
    }


def test_artifact_store_keeps_candidate_and_commit_as_immutable_records(tmp_path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    candidate = store.save_candidate("run-1", "brief", story_brief(), source="provider:op-1")
    committed = store.commit("run-1", "brief", story_brief(), source="decision:accept-1")

    assert candidate.status == "candidate"
    assert committed.status == "committed"
    assert candidate.artifact_id != committed.artifact_id
    assert candidate.signature == committed.signature
    assert store.read("run-1", candidate.artifact_id) == candidate
    assert store.list("run-1", stage_id="brief") == [candidate, committed]
    assert store.latest("run-1", "brief", status="candidate") == candidate
    assert store.latest("run-1", "brief").artifact_id == committed.artifact_id
    assert store.commit("run-1", "brief", story_brief(), source="decision:accept-1") == committed

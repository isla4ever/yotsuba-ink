from __future__ import annotations

from novel_workflow.storage.artifact_store import ArtifactStore


def story_brief() -> dict[str, object]:
    return {
        "title": "雾港母带",
        "premise": "声音 archivist 在封闭港区追查一卷会改写公共记忆的母带。",
        "story_promise": {"genre": "悬疑", "audience": "成人", "tone": "克制而紧张"},
        "world_rules": ["公开广播会覆盖个人记忆"],
        "thematic_question": "共同记忆是否值得以个人真相为代价？",
        "ending_promise": "母带真相将被公开并改变港区秩序。",
        "voice": {"viewpoint": "第三人称限知", "tense": "过去时", "texture": "听觉细节驱动", "avoid": ["全知解释"]},
        "cast_requirements": [{"function": "调查真相", "importance": "protagonist"}],
    }


def test_artifact_store_keeps_candidate_and_commit_as_immutable_records(tmp_path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    candidate = store.save_candidate("run-1", "info", story_brief(), source="provider:op-1")
    committed = store.commit("run-1", "info", story_brief(), source="decision:accept-1")

    assert candidate.status == "candidate"
    assert committed.status == "committed"
    assert candidate.artifact_id != committed.artifact_id
    assert candidate.signature == committed.signature
    assert store.read("run-1", candidate.artifact_id) == candidate
    assert store.list("run-1", stage_id="info") == [candidate, committed]
    assert store.latest("run-1", "info", status="candidate") == candidate
    assert store.latest("run-1", "info").artifact_id == committed.artifact_id
    assert store.commit("run-1", "info", story_brief(), source="decision:accept-1") == committed

from __future__ import annotations

import pytest

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
        "length_envelope": {"word_target_soft": 10000},
    }


def detail_artifact() -> dict[str, object]:
    return {
        "chapters": [
            {
                "ref": "chapter-1",
                "volume_ref": "volume-1",
                "title": "异常哈希",
                "target_characters": 2500,
                "turn_refs": ["turn-1"],
                "purpose": "核对空白晶片的异常签名",
                "pov": "subject-1",
                "cast_ids": ["subject-1"],
                "scenes": [
                    {
                        "place": "修复间",
                        "objective": "校验晶片",
                        "conflict": "签名异常",
                        "turn": "恢复索引",
                        "result": "发现求救声",
                    },
                    {
                        "place": "档案室",
                        "objective": "核对日志",
                        "conflict": "记录缺失",
                        "turn": "固定时间戳",
                        "result": "留下调查入口",
                    },
                ],
                "handoff": "下一章追查晶片来源",
            }
        ]
    }


def character_bible(*, debut: str) -> dict[str, object]:
    return {
        "subjects": [
            {
                "id": "subject-1",
                "name": "林澈",
                "kind": "protagonist",
                "function": "修复潮汐记忆并建立独立证据链。",
                "background": "旧港公共档案修复师，长期负责事故录音的校准与归档。",
                "conflict_history": "她曾在首次修复时见过被替换的母带索引，却选择沉默。",
                "present_stakes": "若证据链失败，她会失去修复资格并承担隐瞒责任。",
                "temperament": "受压时先核对记录，再用程序事实逼迫对方表态。",
                "speech_style": "短句，少下判断，习惯先复述可验证记录。",
                "drive": "在大潮前查清事故真相。",
                "change": "从隐瞒亲属冲突到公开承担程序责任。",
                "debut": debut,
                "limits": ["不得让记忆证据单独定案。"],
                "demand_refs": ["demand-protagonist"],
            }
        ],
        "relations": [],
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


def test_artifact_store_saves_detail_with_frozen_turn_bindings(tmp_path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    candidate = store.save_candidate(
        "run-1",
        "detail",
        detail_artifact(),
        source="user-decision:detail-1",
        subject_ids={"subject-1"},
        chapter_refs={"chapter-1"},
        chapter_turn_refs={"chapter-1": ["turn-1"]},
        volume_cast_ids={"volume-1": {"subject-1"}},
    )

    assert candidate.payload["chapters"][0]["turn_refs"] == ["turn-1"]


def test_artifact_store_applies_dynamic_cast_chapter_target(tmp_path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")

    candidate = store.save_candidate(
        "run-1",
        "cast",
        character_bible(debut="chapter:45"),
        source="user-decision:cast-1",
        chapter_target=45,
    )
    committed = store.commit(
        "run-1",
        "cast",
        candidate.payload,
        source="decision:cast-1",
        chapter_target=45,
    )

    assert committed.payload["subjects"][0]["debut"] == "chapter:45"
    with pytest.raises(ValueError, match="exceed the frozen detail range"):
        store.save_candidate(
            "run-2",
            "cast",
            character_bible(debut="chapter:46"),
            source="user-decision:cast-2",
            chapter_target=45,
        )

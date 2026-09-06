from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.output_contracts.phase32_route_artifacts import (
    NovelBriefArtifact,
    ScreenplayBriefArtifact,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactStore,
    Phase32ArtifactStoreError,
)


def _novel_brief() -> NovelBriefArtifact:
    return NovelBriefArtifact(
        title="失序档案",
        premise="一名记者追查一份被篡改的城市档案。",
        audience_promise="让读者看到真相代价，而不是只看到谜底。",
        theme_question="记录真相是否值得牺牲安全？",
        world_rules=("所有公共档案都有可追溯的签名。",),
        ending_direction="主角公开证据并接受由此带来的代价。",
        narrative_voice="克制、具体、贴近现场",
        target_characters=20_000,
    )


def _screenplay_brief() -> ScreenplayBriefArtifact:
    return ScreenplayBriefArtifact(
        title="失序档案",
        sample_type="调查悬疑样片",
        target_minutes=12,
        premise="公共档案的签名链正在被有意抹除。",
        audience_promise="一部节奏克制、证据驱动的调查样片。",
        visible_conflict="主角必须在闭馆前证明签名页被替换。",
        ending_effect="被撕开的签名页在听证会上重新拼合。",
        tone="冷峻、克制、证据驱动",
    )


def test_candidate_commit_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    store = Phase32ArtifactStore(tmp_path)
    candidate = store.save_candidate(
        run_id="run-1",
        creation_route_id="short_novel",
        stage_id="brief",
        artifact=_novel_brief(),
        source_operation_key="run-1:brief:1",
    )

    assert candidate.status == "candidate"
    assert candidate.artifact_ref.startswith("p32-brief-candidate-")
    assert store.read("run-1", candidate.artifact_ref) == candidate

    committed = store.commit_candidate(
        run_id="run-1",
        creation_route_id="short_novel",
        stage_id="brief",
        candidate_ref=candidate.artifact_ref,
    )
    repeated = store.commit_candidate(
        run_id="run-1",
        creation_route_id="short_novel",
        stage_id="brief",
        candidate_ref=candidate.artifact_ref,
    )
    assert committed.status == "committed"
    assert committed.artifact_ref == repeated.artifact_ref
    assert [item.status for item in store.list("run-1", stage_id="brief")] == [
        "candidate",
        "committed",
    ]

    second_candidate = store.save_candidate(
        run_id="run-1",
        creation_route_id="short_novel",
        stage_id="brief",
        artifact=_novel_brief(),
        source_operation_key="run-1:brief:another-operation",
    )
    assert second_candidate.artifact_ref != candidate.artifact_ref
    assert (
        store.commit_candidate(
            run_id="run-1",
            creation_route_id="short_novel",
            stage_id="brief",
            candidate_ref=second_candidate.artifact_ref,
        ).artifact_ref
        == committed.artifact_ref
    )


def test_store_rejects_wrong_route_stage_and_unknown_refs(tmp_path: Path) -> None:
    store = Phase32ArtifactStore(tmp_path)
    candidate = store.save_candidate(
        run_id="run-2",
        creation_route_id="screenplay_sample",
        stage_id="brief",
        artifact=_screenplay_brief(),
        source_operation_key="run-2:brief:1",
    )
    with pytest.raises(Phase32ArtifactStoreError, match="does not belong"):
        store.commit_candidate(
            run_id="run-2",
            creation_route_id="short_novel",
            stage_id="brief",
            candidate_ref=candidate.artifact_ref,
        )
    with pytest.raises(FileNotFoundError):
        store.read("run-2", "p32-brief-committed-" + "0" * 64)


def test_store_rejects_payload_tampering(tmp_path: Path) -> None:
    store = Phase32ArtifactStore(tmp_path)
    candidate = store.save_candidate(
        run_id="run-3",
        creation_route_id="short_novel",
        stage_id="brief",
        artifact=_novel_brief(),
        source_operation_key="run-3:brief:1",
    )
    path = tmp_path / "run-3" / f"{candidate.artifact_ref}.json"
    payload = path.read_text(encoding="utf-8").replace("记者", "编辑", 1)
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(Phase32ArtifactStoreError, match="Malformed"):
        store.read("run-3", candidate.artifact_ref)


def test_store_rejects_artifact_type_outside_route_binding(tmp_path: Path) -> None:
    store = Phase32ArtifactStore(tmp_path)
    with pytest.raises(Phase32ArtifactStoreError, match="does not match"):
        store.save_candidate(
            run_id="run-4",
            creation_route_id="short_novel",
            stage_id="brief",
            artifact=_screenplay_brief(),
            source_operation_key="run-4:brief:1",
        )

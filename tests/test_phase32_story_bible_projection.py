from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_graph_execution import (
    project_phase32_read_model,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    BeatBoardArtifact,
    BeatBoardBeat,
    BookArchitectureArtifact,
    NovelBriefArtifact,
    PartContract,
    ScreenplayBriefArtifact,
    StoryMapAnchor,
    StoryMapArtifact,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_evidence_store import Phase32EvidenceStore
from novel_workflow.storage.phase32_writeback_outbox import Phase32WritebackOutbox
from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.memory.phase32_wiki_projection import Phase32WikiProjectionStore
from novel_workflow.storage.phase32_story_bible_projection import (
    Phase32StoryBibleProjection,
    Phase32StoryBibleProjectionError,
)
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)


@pytest.mark.parametrize(
    ("route", "structure_stage", "structure_artifact", "expected_kind"),
    (
        (
            SCREENPLAY_SAMPLE_ROUTE,
            "beat_board",
            BeatBoardArtifact(
                beats=(
                    BeatBoardBeat(
                        beat_ref="beat-opening",
                        dramatic_job="建立签名页遭替换的公开疑点。",
                        visible_pressure="档案馆将在十分钟后闭馆。",
                        character_decision="主角决定当场拆开封存袋核验骑缝章。",
                        outcome="保安封锁出口，主角失去安全离场的机会。",
                        setup_or_payoff_refs=("setup-signature",),
                        timing_hint="第 1-2 分钟",
                    ),
                )
            ),
            "beat",
        ),
        (
            SHORT_NOVEL_ROUTE,
            "story_map",
            StoryMapArtifact(
                opening_state="主角相信档案签名系统不可篡改。",
                story_question="谁在利用签名系统删除证词？",
                anchors=(
                    StoryMapAnchor(
                        anchor_ref="anchor-opening",
                        dramatic_job="迫使主角第一次公开质疑系统。",
                        pressure="证词将在午夜永久封存。",
                        choice_or_revelation="主角发现水印日期晚于封存命令。",
                        consequence_or_open_effect="调查从技术故障转为人为篡改。",
                        promise_refs=("promise-truth-cost",),
                    ),
                ),
                ending_state="主角公开证据，同时失去机构保护。",
                open_questions=("谁批准了第二份封存命令？",),
            ),
            "story_anchor",
        ),
        (
            LONG_NOVEL_ROUTE,
            "book_architecture",
            BookArchitectureArtifact(
                book_promise="追踪一套制度如何逐步吞噬记录真相的人。",
                ending_conditions=("签名链的真实控制者被公开。",),
                parts=(
                    PartContract(
                        part_ref="part-investigation",
                        ordinal=1,
                        entry_state="主角仍相信内部程序可以纠错。",
                        dramatic_question="制度会允许证据进入公开记录吗？",
                        promise_refs=("promise-system-cost",),
                        turning_point_refs=("turn-public-hearing",),
                        exit_state="主角被迫在制度外保存证据。",
                        unresolved_obligations=("找到首份被删改证词的原件。",),
                    ),
                ),
            ),
            "part",
        ),
    ),
    ids=lambda value: getattr(value, "route_id", str(value)),
)
def test_projection_uses_route_specific_committed_structure(
    tmp_path: Path,
    route,
    structure_stage: str,
    structure_artifact,
    expected_kind: str,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=route,
        run_id=f"story-bible-{route.route_id}",
        project_id=f"project-{route.route_id}",
        creative_intent="验证故事圣经只读取当前路线的正式 Artifact。",
    )
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    brief = artifacts.save_deterministic(
        run_id=fixture.definition.run_id,
        creation_route_id=route.route_id,
        stage_id="brief",
        artifact=_brief(route.route_id),
    )
    structure = artifacts.save_deterministic(
        run_id=fixture.definition.run_id,
        creation_route_id=route.route_id,
        stage_id=structure_stage,
        artifact=structure_artifact,
    )
    _commit_refs(
        fixture,
        {
            "brief": brief.artifact_ref,
            structure_stage: structure.artifact_ref,
        },
    )

    page = _projection(tmp_path, fixture, artifacts).page(
        fixture.definition.run_id,
        section="structure",
        limit=25,
    )

    assert page.creation_route_id == route.route_id
    assert page.summary.title == "失序档案"
    assert page.summary.formal_writeback_status == "not_started"
    assert page.items[0].kind == expected_kind
    assert page.items[0].source.artifact_ref == structure.artifact_ref
    assert page.items[0].source.stage_id == structure_stage
    assert page.items[0].status == "committed"


def test_projection_pages_only_the_accepted_text_prefix(tmp_path: Path) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SHORT_NOVEL_ROUTE,
        run_id="story-bible-accepted-units",
        project_id="project-accepted-units",
        creative_intent="验证正文单元只从 accepted prefix 投影。",
    )
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    first = artifacts.save_deterministic(
        run_id=fixture.definition.run_id,
        creation_route_id="short_novel",
        stage_id="text",
        artifact=ShortProseUnitArtifact(
            unit_ref="unit-1",
            unit_kind="section",
            title="封存前",
            pov_subject_ref="subject-reporter",
            content="玛雅把复印件贴近台灯，水印日期比封存命令晚了三天。",
        ),
    )
    second = artifacts.save_deterministic(
        run_id=fixture.definition.run_id,
        creation_route_id="short_novel",
        stage_id="text",
        artifact=ShortProseUnitArtifact(
            unit_ref="unit-2",
            unit_kind="section",
            title="第二道签名",
            pov_subject_ref="subject-reporter",
            content="她尚未交出的第二份证词仍留在私人保险箱。",
        ),
    )
    _commit_refs(
        fixture,
        {},
        sequential={
            "text": {
                "ordered_unit_refs": ["unit-1", "unit-2"],
                "committed_artifact_refs": {"unit-1": first.artifact_ref},
            }
        },
    )

    projection = _projection(tmp_path, fixture, artifacts)
    first_page = projection.page(
        fixture.definition.run_id,
        section="units",
        limit=1,
    )

    assert first_page.summary.accepted_unit_count == 1
    assert first_page.total == 1
    assert first_page.items[0].entry_ref == "unit-1"
    assert first_page.items[0].source.artifact_ref == first.artifact_ref
    assert second.artifact_ref not in {
        item.source.artifact_ref for item in first_page.items
    }


def test_projection_rejects_candidate_as_committed_authority(tmp_path: Path) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SHORT_NOVEL_ROUTE,
        run_id="story-bible-candidate-rejected",
        project_id="project-candidate-rejected",
        creative_intent="候选稿不能进入故事圣经。",
    )
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    candidate = artifacts.save_candidate(
        run_id=fixture.definition.run_id,
        creation_route_id="short_novel",
        stage_id="brief",
        artifact=_brief("short_novel"),
        source_operation_key="candidate-only",
    )
    _commit_refs(fixture, {"brief": candidate.artifact_ref})

    with pytest.raises(
        Phase32StoryBibleProjectionError,
        match="committed Artifact",
    ):
        _projection(tmp_path, fixture, artifacts).page(
            fixture.definition.run_id,
            section="overview",
            limit=25,
        )


def _brief(route_id: str):
    if route_id == "screenplay_sample":
        return ScreenplayBriefArtifact(
            title="失序档案",
            sample_type="调查悬疑样片",
            target_minutes=12,
            premise="公共档案的签名链正在被有意抹除。",
            audience_promise="观众将跟随主角逐步验证每一处签名矛盾。",
            visible_conflict="主角必须在闭馆前证明签名页被替换。",
            ending_effect="被撕开的签名页在听证会上重新拼合。",
            tone="冷峻、克制、证据驱动",
        )
    target = 20_000 if route_id == "short_novel" else 120_000
    return NovelBriefArtifact(
        title="失序档案",
        premise="一名记者追查一份被篡改的城市档案。",
        audience_promise="让读者看到真相被制度化删除的全过程。",
        theme_question="记录真相是否值得牺牲安全？",
        world_rules=("所有公共档案都有可追溯的签名。",),
        ending_direction="主角公开证据并接受由此带来的代价。",
        narrative_voice="克制、具体、贴近现场",
        target_characters=target,
    )


def _projection(tmp_path: Path, fixture, artifacts: Phase32ArtifactStore):
    canon = Phase32CanonStore(tmp_path / "canon")
    wiki = Phase32WikiProjectionStore(tmp_path / "wiki")
    return Phase32StoryBibleProjection(
        fixture.repository,
        artifacts,
        Phase32EvidenceStore(tmp_path / "evidence"),
        canon,
        wiki,
        Phase32WritebackOutbox(
            tmp_path / "outbox",
            canon=canon,
            wiki=wiki,
        ),
    )


def _commit_refs(fixture, refs: dict[str, str], *, sequential=None) -> None:
    record = fixture.repository.read(fixture.definition.run_id)
    state = record.state.model_copy(
        update={
            "artifact_refs": refs,
            "sequential_stage_progress": sequential or {},
        }
    ).validate_for_definition(fixture.definition)
    read_model = project_phase32_read_model(
        record.read_model,
        fixture.definition,
        state,
        decision=None,
        checkpoint_id="story-bible-fixture",
        provider_usage=record.read_model.provider_usage,
    )
    fixture.repository.commit_projection(
        fixture.definition.run_id,
        state=state,
        read_model=read_model,
    )

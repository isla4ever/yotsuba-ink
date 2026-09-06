from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from novel_workflow.orchestration.phase32_quality_review import (
    Phase32QualityReviewCommand,
    Phase32QualityReviewError,
    Phase32QualityReviewService,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ChapterArtifact,
    ScreenplayBlock,
    ScreenplayDraftArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    DetailChapterPlan,
    DetailPlanIndexArtifact,
    DetailScenePlan,
    DetailWindow,
)
from novel_workflow.quality.phase32_quality_report import (
    Phase32DeterministicBlocker,
    Phase32LiteraryWarning,
    Phase32ProseEvidenceAnchor,
    Phase32ScreenplayEvidenceAnchor,
)
from novel_workflow.runtime.graph.route_run_state import SequentialStageProgress
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_quality_report_store import (
    Phase32QualityReportStore,
)
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_read_model import ArtifactRefProjection
from novel_workflow.workflows.graph_run_definition import (
    freeze_graph_run_definition,
    freeze_phase32_scale_profile,
)
from novel_workflow.workflows.phase32_scale import (
    freeze_continuity_acceptance_scale_profile,
    freeze_release_smoke_scale_profile,
)
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)


_NOW = "2026-09-05T12:00:00+08:00"


def _fixture(tmp_path: Path, route, *, run_id: str):
    return create_phase32_run_fixture(
        tmp_path / "runtime",
        route=route,
        run_id=run_id,
        project_id=f"project-{run_id}",
        creative_intent="验证文本质量报告与人工冷读证据。",
    )


def _service(tmp_path: Path, fixture):
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    reports = Phase32QualityReportStore(tmp_path / "quality-reports")
    service = Phase32QualityReviewService(
        fixture.repository,
        artifacts,
        reports,
        clock=lambda: _NOW,
    )
    return service, artifacts, reports


def _continuity_fixture(tmp_path: Path, *, run_id: str):
    base = _fixture(
        tmp_path / "base",
        LONG_NOVEL_ROUTE,
        run_id=f"{run_id}-base",
    )
    source = base.definition
    definition = freeze_graph_run_definition(
        run_id=run_id,
        project_id=f"project-{run_id}",
        workflow_id=source.workflow_id,
        workflow_revision=source.workflow_revision,
        workflow_digest=source.workflow_digest,
        route_contract=source.route_contract,
        scale_profile=freeze_phase32_scale_profile(
            freeze_continuity_acceptance_scale_profile("long_novel")
        ),
        inputs=source.inputs,
        provider_bindings_by_stage=source.provider_bindings_by_stage,
        export_profile=source.export_profile,
        created_at=_NOW,
    )
    repository = Phase32RunRepository(tmp_path / "continuity-runtime")
    repository.create(definition, updated_at=_NOW)
    return SimpleNamespace(repository=repository, definition=definition)


def _detail_index(chapter_refs: tuple[str, ...]) -> DetailPlanIndexArtifact:
    chapters = tuple(
        DetailChapterPlan(
            chapter_ref=chapter_ref,
            ordinal=ordinal,
            volume_ref="volume-1",
            title=f"第{ordinal}章",
            pov_subject_ref="maya",
            cast_subject_refs=("maya",),
            dramatic_job=f"推进第{ordinal}章的连续性验证。",
            entry_state=f"第{ordinal}章进入状态。",
            scenes=(
                DetailScenePlan(
                    scene_ref=f"scene-{ordinal}",
                    ordinal=1,
                    location="档案室",
                    time_context="夜晚",
                    cast_subject_refs=("maya",),
                    goal="核验证据。",
                    opposition="时间不足。",
                    outcome="获得下一条线索。",
                ),
            ),
            conflict="公开证据与保护证人发生冲突。",
            stakes="错误选择会让证据失效。",
            exit_state=f"第{ordinal}章退出状态。",
            hook="新的签名差异出现。",
            handoff=f"交接至第{ordinal + 1}章。",
            length_hint=1_000,
        )
        for ordinal, chapter_ref in enumerate(chapter_refs, start=1)
    )
    return DetailPlanIndexArtifact(
        windows=(
            DetailWindow(
                window_ref="window-1",
                ordinal=1,
                volume_refs=("volume-1",),
                chapters=chapters,
                entry_state="进入连续性窗口。",
                handoff="窗口正文完成后进入复核。",
                next_window_entry_state="保留下一窗口入口状态。",
            ),
        )
    )


def _install_rolling_detail(
    fixture,
    artifacts: Phase32ArtifactStore,
    detail: DetailPlanIndexArtifact,
) -> str:
    artifact = artifacts.save_deterministic(
        run_id=fixture.definition.run_id,
        creation_route_id="long_novel",
        stage_id="rolling_detail",
        artifact=detail,
    )
    current = fixture.repository.read(fixture.definition.run_id)
    state_artifacts = dict(current.state.artifact_refs)
    state_artifacts["rolling_detail"] = artifact.artifact_ref
    read_artifacts = dict(current.read_model.artifact_refs)
    read_artifacts["rolling_detail"] = ArtifactRefProjection(
        artifact_kind="detail_plan_index",
        artifact_ref=artifact.artifact_ref,
    )
    fixture.repository.commit_projection(
        fixture.definition.run_id,
        state=current.state.model_copy(update={"artifact_refs": state_artifacts}),
        read_model=current.read_model.model_copy(
            update={"artifact_refs": read_artifacts, "updated_at": _NOW}
        ),
    )
    return artifact.artifact_ref


def _chapters(chapter_refs: tuple[str, ...]) -> tuple[ChapterArtifact, ...]:
    return tuple(
        ChapterArtifact(
            chapter_ref=chapter_ref,
            volume_ref="volume-1",
            title=f"第{ordinal}章",
            pov_subject_ref="maya",
            content=f"第{ordinal}章正文保留连续性证据。",
        )
        for ordinal, chapter_ref in enumerate(chapter_refs, start=1)
    )


def _install_text_prefix(
    fixture,
    artifacts: Phase32ArtifactStore,
    units: tuple[object, ...],
    *,
    ordered_unit_refs: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    route_id = fixture.definition.creation_route_id
    stage_id = "script" if route_id == "screenplay_sample" else "text"
    unit_refs: list[str] = []
    artifact_refs: list[str] = []
    for unit in units:
        record = artifacts.save_deterministic(
            run_id=fixture.definition.run_id,
            creation_route_id=route_id,
            stage_id=stage_id,
            artifact=unit,
        )
        unit_ref = (
            unit.scene_ref
            if isinstance(unit, ScreenplayDraftArtifact)
            else unit.unit_ref
            if isinstance(unit, ShortProseUnitArtifact)
            else unit.chapter_ref
        )
        unit_refs.append(unit_ref)
        artifact_refs.append(record.artifact_ref)
    frozen_order = ordered_unit_refs or tuple(unit_refs)
    progress = SequentialStageProgress(
        ordered_unit_refs=frozen_order,
        committed_artifact_refs=dict(zip(unit_refs, artifact_refs, strict=True)),
    )
    current = fixture.repository.read(fixture.definition.run_id)
    active_unit_ref = progress.next_unit_ref
    state = current.state.model_copy(
        update={
            "active_stage_id": stage_id,
            "active_unit_ref": active_unit_ref,
            "sequential_stage_progress": {
                stage_id: progress.model_dump(mode="json")
            },
        }
    )
    read_model = current.read_model.model_copy(
        update={
            "active_stage_id": stage_id,
            "active_unit_ref": active_unit_ref,
            "sequential_stage_progress": {stage_id: progress},
            "updated_at": _NOW,
        }
    )
    fixture.repository.commit_projection(
        fixture.definition.run_id,
        state=state,
        read_model=read_model,
    )
    return tuple(artifact_refs)


@pytest.mark.parametrize(
    ("route", "units", "unit_ref", "needle"),
    (
        (
            SHORT_NOVEL_ROUTE,
            (
                ShortProseUnitArtifact(
                    unit_ref="unit-1",
                    unit_kind="section",
                    title="雨夜证词",
                    pov_subject_ref="maya",
                    content="雨声压住了证人的第二次回答。",
                ),
            ),
            "unit-1",
            "第二次回答",
        ),
        (
            LONG_NOVEL_ROUTE,
            (
                ChapterArtifact(
                    chapter_ref="chapter-1",
                    volume_ref="volume-1",
                    title="签名页",
                    pov_subject_ref="maya",
                    content="她重新核对签名页，却没有立刻公开结论。",
                ),
            ),
            "chapter-1",
            "没有立刻公开",
        ),
    ),
)
def test_prose_review_binds_exact_committed_prefix_and_keeps_critical_advisory(
    tmp_path: Path,
    route,
    units,
    unit_ref: str,
    needle: str,
) -> None:
    fixture = _fixture(tmp_path, route, run_id=f"quality-{route.route_id}")
    service, artifacts, reports = _service(tmp_path, fixture)
    (artifact_ref,) = _install_text_prefix(fixture, artifacts, units)
    content = units[0].content
    start = content.index(needle)
    report = service.record_review(
        fixture.definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="editor-1",
            reviewer_role="cold_reader",
            outcome="revision_recommended",
            summary="结构完整，但关键段落的解释密度偏高。",
            literary_warnings=(
                Phase32LiteraryWarning(
                    code="exposition_density",
                    impact="critical",
                    observation=(
                        "关键结论集中解释，削弱了读者参与判断的空间。"
                    ),
                    recommended_action=(
                        "拆分信息，并保留一次可见行动来承载结论。"
                    ),
                    anchors=(
                        Phase32ProseEvidenceAnchor(
                            artifact_ref=artifact_ref,
                            unit_ref=unit_ref,
                            start_offset=start,
                            end_offset=start + len(needle),
                            exact_text=needle,
                        ),
                    ),
                ),
            ),
        ),
    )

    assert report.source_snapshot.accepted_prefix_complete is True
    assert [item.unit_ref for item in report.source_snapshot.committed_sources] == [
        unit_ref
    ]
    assert report.structure_contract == "passed"
    assert report.production_acceptance_status == "not_evaluated"
    assert report.literary_warnings[0].lane == "advisory"
    assert report.literary_warnings[0].impact == "critical"
    assert reports.read(fixture.definition.run_id, report.report_ref) == report


def test_production_acceptance_fails_closed_without_trusted_gate_receipt(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE, run_id="quality-no-gate-receipt")
    service, artifacts, reports = _service(tmp_path, fixture)
    _install_text_prefix(
        fixture,
        artifacts,
        (
            ShortProseUnitArtifact(
                unit_ref="unit-1",
                unit_kind="section",
                title="完整正文",
                pov_subject_ref="maya",
                content="完整前缀也不能替代可信的确定性质量闸门回执。",
            ),
        ),
    )
    command = Phase32QualityReviewCommand(
        reviewer_ref="editor-1",
        reviewer_role="cold_reader",
        outcome="continue_reading",
        summary="人工冷读通过，但没有 code-owned gate receipt。",
        production_acceptance_status="accepted",
    )

    with pytest.raises(Phase32QualityReviewError, match="trusted code-owned"):
        service.record_review(fixture.definition.run_id, command)

    forged = Phase32DeterministicBlocker(
        code="caller_forged_gate",
        evidence="调用方声称结构检查通过。",
        required_action="不得信任调用方注入的确定性闸门结果。",
    )
    with pytest.raises(TypeError, match="system_blockers"):
        service.record_review(
            fixture.definition.run_id,
            command,
            system_blockers=(forged,),  # type: ignore[call-arg]
        )
    assert reports.list(fixture.definition.run_id) == []


def test_prose_anchor_must_match_exact_committed_offsets(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE, run_id="quality-bad-anchor")
    service, artifacts, reports = _service(tmp_path, fixture)
    unit = ShortProseUnitArtifact(
        unit_ref="unit-1",
        unit_kind="section",
        title="雨夜证词",
        pov_subject_ref="maya",
        content="她看见水印，却没有说出来源。",
    )
    (artifact_ref,) = _install_text_prefix(fixture, artifacts, (unit,))

    with pytest.raises(Phase32QualityReviewError, match="does not match"):
        service.record_review(
            fixture.definition.run_id,
            Phase32QualityReviewCommand(
                reviewer_ref="editor-1",
                reviewer_role="cold_reader",
                outcome="revision_recommended",
                summary="证据必须精确绑定。",
                literary_warnings=(
                    Phase32LiteraryWarning(
                        code="unclear_source",
                        impact="high",
                        observation="来源交代不足。",
                        recommended_action="补充可见来源。",
                        anchors=(
                            Phase32ProseEvidenceAnchor(
                                artifact_ref=artifact_ref,
                                unit_ref="unit-1",
                                start_offset=0,
                                end_offset=2,
                                exact_text="错误",
                            ),
                        ),
                    ),
                ),
            ),
        )

    assert reports.list(fixture.definition.run_id) == []


def test_screenplay_anchor_binds_exact_block_kind_index_and_span(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, SCREENPLAY_SAMPLE_ROUTE, run_id="quality-screenplay")
    service, artifacts, _reports = _service(tmp_path, fixture)
    script = ScreenplayDraftArtifact(
        scene_ref="scene-1",
        blocks=(
            ScreenplayBlock(kind="scene_heading", text="INT. 档案室 - NIGHT"),
            ScreenplayBlock(kind="action", text="玛雅把湿透的签名页贴到灯下。"),
        ),
    )
    (artifact_ref,) = _install_text_prefix(fixture, artifacts, (script,))
    warning = Phase32LiteraryWarning(
        code="repeated_weather_image",
        impact="moderate",
        observation="湿冷意象与前场重复。",
        recommended_action="换成与证据动作直接相关的视觉细节。",
        anchors=(
            Phase32ScreenplayEvidenceAnchor(
                artifact_ref=artifact_ref,
                unit_ref="scene-1",
                block_index=1,
                block_kind="action",
                start_offset=3,
                end_offset=6,
                exact_text="湿透的",
            ),
        ),
    )

    report = service.record_review(
        fixture.definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="script-editor",
            reviewer_role="screenplay_cold_reader",
            outcome="continue_reading",
            summary="场景动作成立，保留一项非阻断意象建议。",
            literary_warnings=(warning,),
        ),
    )
    assert report.source_snapshot.stage_id == "script"

    bad_anchor = warning.anchors[0].model_copy(update={"block_kind": "dialogue"})
    with pytest.raises(Phase32QualityReviewError, match="block kind"):
        service.record_review(
            fixture.definition.run_id,
            Phase32QualityReviewCommand(
                reviewer_ref="script-editor-2",
                reviewer_role="screenplay_cold_reader",
                outcome="revision_recommended",
                summary="块类型也必须精确匹配。",
                literary_warnings=(warning.model_copy(update={"anchors": (bad_anchor,)}),),
            ),
        )


def test_incomplete_prefix_is_a_system_blocker_and_cannot_be_accepted(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE, run_id="quality-partial")
    service, artifacts, _reports = _service(tmp_path, fixture)
    unit = ShortProseUnitArtifact(
        unit_ref="unit-1",
        unit_kind="section",
        title="第一节",
        pov_subject_ref="maya",
        content="第一节正文。",
    )
    _install_text_prefix(
        fixture,
        artifacts,
        (unit,),
        ordered_unit_refs=("unit-1", "unit-2"),
    )
    report = service.record_review(
        fixture.definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="editor-1",
            reviewer_role="cold_reader",
            outcome="continue_reading",
            summary="仅审阅当前前缀，不能作为整部作品验收。",
        ),
    )
    blocker = report.deterministic_blockers[0]
    assert report.structure_contract == "blocked"
    assert blocker.lane == "system"
    assert blocker.effect == "block"
    assert blocker.code == "accepted_prefix_incomplete"

    with pytest.raises(Phase32QualityReviewError, match="complete, unblocked"):
        service.record_review(
            fixture.definition.run_id,
            Phase32QualityReviewCommand(
                reviewer_ref="editor-2",
                reviewer_role="cold_reader",
                outcome="continue_reading",
                summary="不能越过未完成前缀。",
                production_acceptance_status="accepted",
            ),
        )


def test_append_only_supersession_projects_old_review_as_stale(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE, run_id="quality-supersession")
    service, artifacts, reports = _service(tmp_path, fixture)
    _install_text_prefix(
        fixture,
        artifacts,
        (
            ShortProseUnitArtifact(
                unit_ref="unit-1",
                unit_kind="section",
                title="唯一一节",
                pov_subject_ref="maya",
                content="她把证词封入证物袋。",
            ),
        ),
    )
    first = service.record_review(
        fixture.definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="editor-1",
            reviewer_role="cold_reader",
            outcome="revision_recommended",
            summary="第一轮建议返工。",
        ),
    )
    second = service.record_review(
        fixture.definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="editor-2",
            reviewer_role="cold_reader",
            outcome="continue_reading",
            summary="复核后可继续阅读。",
        ),
    )

    assert second.sequence == 2
    assert second.supersedes_report_ref == first.report_ref
    assert reports.read(fixture.definition.run_id, first.report_ref) == first
    projections = service.projections(fixture.definition.run_id)
    assert projections[0].freshness == "stale"
    assert projections[0].stale_reasons == ("superseded",)
    assert projections[1].freshness == "current"
    assert projections[1].stale_reasons == ()


def test_growing_accepted_prefix_marks_latest_review_source_changed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE, run_id="quality-prefix-growth")
    service, artifacts, _reports = _service(tmp_path, fixture)
    first_unit = ShortProseUnitArtifact(
        unit_ref="unit-1",
        unit_kind="section",
        title="第一节",
        pov_subject_ref="maya",
        content="她先封存签名页。",
    )
    second_unit = ShortProseUnitArtifact(
        unit_ref="unit-2",
        unit_kind="section",
        title="第二节",
        pov_subject_ref="maya",
        content="随后她公开水印来源。",
    )
    _install_text_prefix(
        fixture,
        artifacts,
        (first_unit,),
        ordered_unit_refs=("unit-1", "unit-2"),
    )
    report = service.record_review(
        fixture.definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="editor-1",
            reviewer_role="cold_reader",
            outcome="continue_reading",
            summary="这是未完成 accepted prefix 的阶段性冷读。",
        ),
    )

    _install_text_prefix(
        fixture,
        artifacts,
        (first_unit, second_unit),
        ordered_unit_refs=("unit-1", "unit-2"),
    )
    (projection,) = service.projections(fixture.definition.run_id)
    assert projection.report.report_ref == report.report_ref
    assert projection.freshness == "stale"
    assert projection.stale_reasons == ("source_changed",)


def test_release_smoke_report_cannot_claim_production_acceptance(tmp_path: Path) -> None:
    base = _fixture(tmp_path / "base", SHORT_NOVEL_ROUTE, run_id="quality-smoke-base")
    source = base.definition
    smoke_definition = freeze_graph_run_definition(
        run_id="release-smoke-quality-short",
        project_id="release-smoke-quality-project",
        workflow_id=source.workflow_id,
        workflow_revision=source.workflow_revision,
        workflow_digest=source.workflow_digest,
        route_contract=source.route_contract,
        scale_profile=freeze_phase32_scale_profile(
            freeze_release_smoke_scale_profile("short_novel")
        ),
        inputs=source.inputs,
        provider_bindings_by_stage=source.provider_bindings_by_stage,
        export_profile=source.export_profile,
        created_at=_NOW,
    )
    repository = Phase32RunRepository(tmp_path / "smoke-runtime")
    repository.create(smoke_definition, updated_at=_NOW)
    fixture = SimpleNamespace(repository=repository, definition=smoke_definition)
    service, artifacts, reports = _service(tmp_path / "smoke", fixture)
    _install_text_prefix(
        fixture,
        artifacts,
        (
            ShortProseUnitArtifact(
                unit_ref="unit-1",
                unit_kind="section",
                title="烟测正文",
                pov_subject_ref="maya",
                content="用于验证链路，不冒充正式文学验收。",
            ),
        ),
    )

    with pytest.raises(Phase32QualityReviewError, match="Release-smoke"):
        service.record_review(
            smoke_definition.run_id,
            Phase32QualityReviewCommand(
                reviewer_ref="editor-1",
                reviewer_role="cold_reader",
                outcome="continue_reading",
                summary="烟测可读，但不属于生产验收。",
                production_acceptance_status="accepted",
            ),
        )
    report = service.record_review(
        smoke_definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="editor-1",
            reviewer_role="cold_reader",
            outcome="continue_reading",
            summary="烟测记录只保留为 release-smoke evidence。",
        ),
    )
    assert report.evidence_scope == "release_smoke"
    assert report.production_acceptance_status == "not_evaluated"
    assert len(reports.list(smoke_definition.run_id)) == 1


def test_continuity_acceptance_rejects_one_chapter_rolling_detail(
    tmp_path: Path,
) -> None:
    fixture = _continuity_fixture(
        tmp_path,
        run_id="continuity-quality-one-chapter",
    )
    service, artifacts, reports = _service(tmp_path, fixture)
    chapter_refs = ("chapter-1",)
    _install_rolling_detail(fixture, artifacts, _detail_index(chapter_refs))
    _install_text_prefix(
        fixture,
        artifacts,
        _chapters(chapter_refs),
        ordered_unit_refs=chapter_refs,
    )

    with pytest.raises(Phase32QualityReviewError, match="exactly 12 chapters"):
        service.record_review(
            fixture.definition.run_id,
            Phase32QualityReviewCommand(
                reviewer_ref="editor-1",
                reviewer_role="cold_reader",
                outcome="continue_reading",
                summary="一章样本不能冒充 exact-12 continuity evidence。",
            ),
        )
    assert reports.list(fixture.definition.run_id) == []


def test_continuity_acceptance_text_order_must_match_rolling_detail(
    tmp_path: Path,
) -> None:
    fixture = _continuity_fixture(
        tmp_path,
        run_id="continuity-quality-order-mismatch",
    )
    service, artifacts, reports = _service(tmp_path, fixture)
    chapter_refs = tuple(f"chapter-{ordinal}" for ordinal in range(1, 13))
    _install_rolling_detail(fixture, artifacts, _detail_index(chapter_refs))
    _install_text_prefix(
        fixture,
        artifacts,
        _chapters(("chapter-1",)),
        ordered_unit_refs=chapter_refs[:-1] + ("chapter-13",),
    )

    with pytest.raises(Phase32QualityReviewError, match="exactly match"):
        service.record_review(
            fixture.definition.run_id,
            Phase32QualityReviewCommand(
                reviewer_ref="editor-1",
                reviewer_role="cold_reader",
                outcome="continue_reading",
                summary="正文冻结顺序与 Rolling Detail 不一致。",
            ),
        )
    assert reports.list(fixture.definition.run_id) == []


def test_exact12_continuity_report_binds_planning_version_and_stales_on_replacement(
    tmp_path: Path,
) -> None:
    fixture = _continuity_fixture(
        tmp_path,
        run_id="continuity-quality-exact12",
    )
    service, artifacts, reports = _service(tmp_path, fixture)
    chapter_refs = tuple(f"chapter-{ordinal}" for ordinal in range(1, 13))
    initial_detail = _detail_index(chapter_refs)
    initial_detail_ref = _install_rolling_detail(
        fixture,
        artifacts,
        initial_detail,
    )
    _install_text_prefix(
        fixture,
        artifacts,
        _chapters(chapter_refs[:4]),
        ordered_unit_refs=chapter_refs,
    )

    with pytest.raises(Phase32QualityReviewError, match="Continuity-acceptance"):
        service.record_review(
            fixture.definition.run_id,
            Phase32QualityReviewCommand(
                reviewer_ref="editor-1",
                reviewer_role="cold_reader",
                outcome="continue_reading",
                summary="私有 continuity evidence 不能成为 production acceptance。",
                production_acceptance_status="accepted",
            ),
        )
    report = service.record_review(
        fixture.definition.run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="editor-1",
            reviewer_role="cold_reader",
            outcome="continue_reading",
            summary="记录合法 exact-12 窗口的阶段性人工冷读。",
        ),
    )
    assert report.evidence_scope == "continuity_acceptance"
    assert report.production_acceptance_status == "not_evaluated"
    assert report.source_snapshot.ordered_unit_refs == chapter_refs
    assert report.source_snapshot.planning_source is not None
    assert (
        report.source_snapshot.planning_source.artifact_ref == initial_detail_ref
    )
    assert all(
        source.artifact_ref != initial_detail_ref
        for source in report.source_snapshot.committed_sources
    )
    assert tuple(
        item.unit_ref for item in report.source_snapshot.committed_sources
    ) == chapter_refs[:4]
    assert report.source_snapshot.accepted_prefix_complete is False
    assert report.deterministic_blockers[0].code == "accepted_prefix_incomplete"
    assert len(reports.list(fixture.definition.run_id)) == 1

    revised_window = initial_detail.windows[0].model_copy(
        update={"handoff": "同一十二章顺序下，滚动规划内容已完成新版本修订。"}
    )
    revised_detail = initial_detail.model_copy(update={"windows": (revised_window,)})
    revised_detail_ref = _install_rolling_detail(
        fixture,
        artifacts,
        revised_detail,
    )
    assert revised_detail_ref != initial_detail_ref

    (projection,) = service.projections(fixture.definition.run_id)
    assert projection.report.report_ref == report.report_ref
    assert projection.freshness == "stale"
    assert projection.stale_reasons == ("source_changed",)

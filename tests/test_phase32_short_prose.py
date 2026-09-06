from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32GraphExecutionService,
)
from novel_workflow.orchestration.phase32_run_fixture import (
    create_phase32_run_fixture,
)
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    CharacterBibleArtifact,
    CharacterRecord,
    CharacterRelationship,
    SectionPlanArtifact,
    SectionPlanUnit,
    StoryMapAnchor,
    StoryMapArtifact,
)
from novel_workflow.providers.phase32_contract import Phase32ProviderResponse
from novel_workflow.runtime.graph.phase32_checkpointer import open_phase32_checkpointer
from novel_workflow.runtime.graph.phase32_driver import (
    Phase32DriverError,
    Phase32RouteDriver,
)
from novel_workflow.runtime.graph.phase32_provider_input import (
    compile_phase32_stage_context,
)
from novel_workflow.runtime.graph.route_run_state import (
    SequentialStageProgress,
    initial_route_run_state,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_specs import SHORT_NOVEL_ROUTE
from tests.test_phase32_driver import FakePhase32Gateway, _FixtureGateway
from tests.test_phase32_route_graph import _definition


def _character(
    subject_ref: str,
    display_name: str,
    role: str,
) -> CharacterRecord:
    return CharacterRecord(
        subject_ref=subject_ref,
        display_name=display_name,
        role=role,
        desire="查明档案签名链的真实来源",
        stakes="错误公开会让证据和职业信誉同时失效",
        constraints=("不能把未经核验的怀疑当作事实",),
        voice="使用短句，先核对具体证据",
        arc_scope="从独自调查转向承担公开证据的后果",
    )


def _upstream(store: Phase32ArtifactStore, run_id: str):
    cast = store.save_deterministic(
        run_id=run_id,
        creation_route_id="short_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact(
            characters=(
                _character("maya", "玛雅", "档案记者"),
                _character("guard", "周警卫", "闭馆值班员"),
                _character("director", "林主任", "听证协调人"),
            ),
            relationships=(
                CharacterRelationship(
                    from_subject_ref="maya",
                    to_subject_ref="guard",
                    pressure="玛雅需要证据，周警卫必须执行闭馆程序",
                    change_trigger="周警卫亲眼看到水印日期矛盾",
                ),
            ),
        ),
    )
    story_map = store.save_deterministic(
        run_id=run_id,
        creation_route_id="short_novel",
        stage_id="story_map",
        artifact=StoryMapArtifact(
            opening_state="玛雅只拥有一张来源不明的复印件。",
            story_question="谁修改了公共档案的签名链？",
            anchors=(
                StoryMapAnchor(
                    anchor_ref="anchor-evidence",
                    dramatic_job="让复印件成为可核验的证据。",
                    pressure="档案馆即将闭馆。",
                    choice_or_revelation="玛雅决定现场核对水印。",
                    consequence_or_open_effect="她发现日期与封存记录矛盾。",
                    promise_refs=("promise-evidence",),
                ),
                StoryMapAnchor(
                    anchor_ref="anchor-hearing",
                    dramatic_job="把证据推进到公开听证。",
                    pressure="机构要求撤回公开议程。",
                    choice_or_revelation="玛雅公开自己的取证过程。",
                    consequence_or_open_effect="证据被登记，她失去原职。",
                    promise_refs=("promise-hearing",),
                ),
            ),
            ending_state="签名链进入公共记录，玛雅承担职业代价。",
        ),
    )
    section_plan = store.save_deterministic(
        run_id=run_id,
        creation_route_id="short_novel",
        stage_id="section_plan",
        artifact=SectionPlanArtifact(
            units=(
                SectionPlanUnit(
                    unit_ref="unit-1",
                    ordinal=1,
                    title="复印件",
                    dramatic_job="确认复印件来自封存卷宗。",
                    pov_subject_ref="maya",
                    scene_load="档案室核验。",
                    handoff="下一单元从水印日期与封存时间的矛盾开始。",
                    soft_character_budget=3_000,
                    promise_refs=("promise-evidence",),
                ),
                SectionPlanUnit(
                    unit_ref="unit-2",
                    ordinal=2,
                    title="时间戳",
                    dramatic_job="把日期矛盾变成可公开核验的签名链。",
                    pov_subject_ref="maya",
                    scene_load="走廊拦截与证物封存。",
                    handoff="下一单元从公开听证的证据资格争议开始。",
                    soft_character_budget=3_400,
                    promise_refs=("promise-evidence",),
                ),
                SectionPlanUnit(
                    unit_ref="unit-3",
                    ordinal=3,
                    title="听证",
                    dramatic_job="让证据和职业代价同时落地。",
                    pov_subject_ref="maya",
                    scene_load="公开听证。",
                    handoff="故事在证据进入公共记录后收束。",
                    soft_character_budget=3_600,
                    promise_refs=("promise-hearing",),
                ),
            )
        ),
    )
    return cast, story_map, section_plan


class _TwoUnitShortProseGateway(_FixtureGateway):
    async def generate(self, request, *, binding):
        if request.stage_id != "section_plan":
            return await super().generate(request, binding=binding)
        self.requests.append(request)
        return Phase32ProviderResponse(
            payload=SectionPlanArtifact(
                units=(
                    SectionPlanUnit(
                        unit_ref="unit-1",
                        ordinal=1,
                        title="复印件",
                        dramatic_job="确认复印件来自封存卷宗。",
                        pov_subject_ref="maya",
                        scene_load="档案室核验。",
                        handoff="下一单元从水印日期与封存时间的矛盾开始。",
                        soft_character_budget=3_000,
                        promise_refs=("promise-signature-chain",),
                    ),
                    SectionPlanUnit(
                        unit_ref="unit-2",
                        ordinal=2,
                        title="时间戳",
                        dramatic_job="把日期矛盾变成可公开核验的签名链。",
                        pov_subject_ref="maya",
                        scene_load="走廊拦截与证物封存。",
                        handoff="证据进入听证准备。",
                        soft_character_budget=3_400,
                        promise_refs=("promise-signature-chain",),
                    ),
                )
            ).model_dump(mode="json")
        )


def test_short_prose_context_is_narrow_and_binds_only_previous_unit(
    tmp_path: Path,
) -> None:
    definition = _definition(SHORT_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    cast, story_map, section_plan = _upstream(store, definition.run_id)
    previous = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="short_novel",
        stage_id="text",
        artifact=ShortProseUnitArtifact(
            unit_ref="unit-1",
            unit_kind="section",
            title="复印件",
            pov_subject_ref="maya",
            content="SHOULD-NOT-REACH-CONTEXT" + "旧内容" * 700 + "PREVIOUS-TAIL",
        ),
    )
    progress = SequentialStageProgress(
        ordered_unit_refs=("unit-1", "unit-2", "unit-3"),
        committed_artifact_refs={"unit-1": previous.artifact_ref},
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "unit-2",
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "story_map": story_map.artifact_ref,
                "section_plan": section_plan.artifact_ref,
            },
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )

    context = compile_phase32_stage_context(
        artifact_store=store,
        definition=definition,
        state=state,
        stage=definition.stage("text"),
    )

    sequential = context["sequential_unit"]
    assert sequential["unit_ref"] == "unit-2"
    assert sequential["unit_kind"] == "section"
    assert sequential["accepted_unit_count"] == 1
    assert sequential["previous_unit_handoff"].startswith("下一单元从水印日期")
    assert sequential["previous_unit_tail"].endswith("PREVIOUS-TAIL")
    assert "SHOULD-NOT-REACH-CONTEXT" not in sequential["previous_unit_tail"]
    assert len(sequential["previous_unit_tail"]) <= 1_200
    assert [
        item["unit_ref"]
        for item in context["upstream_artifacts"]["section_plan"]["payload"]["units"]
    ] == ["unit-2"]
    assert [
        item["anchor_ref"]
        for item in context["upstream_artifacts"]["story_map"]["payload"]["anchors"]
    ] == ["anchor-evidence"]
    assert {
        item["subject_ref"]
        for item in context["upstream_artifacts"]["cast"]["payload"]["characters"]
    } == {"maya", "guard"}


@pytest.mark.asyncio
async def test_short_prose_provider_rejects_frozen_title_drift(tmp_path: Path) -> None:
    definition = _definition(SHORT_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    cast, story_map, section_plan = _upstream(store, definition.run_id)
    progress = SequentialStageProgress(
        ordered_unit_refs=("unit-1", "unit-2", "unit-3")
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "unit-1",
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "story_map": story_map.artifact_ref,
                "section_plan": section_plan.artifact_ref,
            },
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    driver = Phase32RouteDriver(
        store,
        FakePhase32Gateway(
            ShortProseUnitArtifact(
                unit_ref="unit-1",
                unit_kind="section",
                title="被 Provider 改写的标题",
                pov_subject_ref="maya",
                content="正文内容本身非空。",
            ).model_dump(mode="json")
        ),
    )

    with pytest.raises(Phase32DriverError, match="frozen Section Plan and Cast"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("text"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"


@pytest.mark.asyncio
async def test_short_prose_reopens_sqlite_at_second_unit_and_advances_to_cover(
    tmp_path: Path,
) -> None:
    policy = ReviewPolicy(
        policy_id="review.short_novel.text-recovery",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="every_unit",
        warning_policy="continue_and_surface",
        auto_continue_stages=("brief", "story_map", "cast", "section_plan"),
        mandatory_decision_stages=("text", "cover"),
    )
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SHORT_NOVEL_ROUTE,
        run_id="short-prose-two-unit-recovery",
        project_id="project-short-prose-recovery",
        creative_intent="验证短中篇正文按冻结单元顺序生成并跨刷新恢复。",
        review_policy=policy,
    )
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    gateway = _TwoUnitShortProseGateway({})
    driver = Phase32RouteDriver(artifact_store, gateway)
    service = Phase32GraphExecutionService(fixture.repository)

    async with open_phase32_checkpointer(tmp_path / "checkpoints") as checkpointer:
        first = await service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
        )
        assert first.decision is not None
        assert first.decision["stage_id"] == "text"
        assert first.decision["unit_ref"] == "unit-1"
        second = await service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume={
                "decision_id": first.decision["decision_id"],
                "action": "accept",
                "domain_revision": first.decision["domain_revision"],
            },
        )

    assert second.decision is not None
    assert second.decision["stage_id"] == "text"
    assert second.decision["unit_ref"] == "unit-2"
    second_progress = second.record.read_model.sequential_stage_progress["text"]
    assert tuple(second_progress.committed_artifact_refs) == ("unit-1",)
    first_artifact_ref = second_progress.committed_artifact_refs["unit-1"]
    first_artifact = artifact_store.read(fixture.definition.run_id, first_artifact_ref)
    assert first_artifact.status == "committed"
    assert first_artifact.payload["unit_ref"] == "unit-1"

    text_requests = [request for request in gateway.requests if request.stage_id == "text"]
    assert len(text_requests) == 2
    second_context = text_requests[1].context["sequential_unit"]
    assert second_context["current_unit"]["unit_ref"] == "unit-2"
    assert second_context["accepted_unit_count"] == 1
    assert second_context["previous_unit_tail"].endswith("封入证物袋。")

    reopened_repository = Phase32RunRepository(fixture.repository.root)
    refreshed = reopened_repository.read(fixture.definition.run_id)
    assert refreshed.read_model.active_stage_id == "text"
    assert refreshed.read_model.active_unit_ref == "unit-2"
    assert refreshed.read_model.pending_decisions[0].unit_ref == "unit-2"

    reopened_service = Phase32GraphExecutionService(reopened_repository)
    async with open_phase32_checkpointer(tmp_path / "checkpoints") as checkpointer:
        third = await reopened_service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume={
                "decision_id": second.decision["decision_id"],
                "action": "accept",
                "domain_revision": second.decision["domain_revision"],
            },
        )

    assert third.decision is not None
    assert third.decision["stage_id"] == "cover"
    assert third.record.read_model.stage_status["text"] == "completed"
    assert third.record.read_model.active_unit_ref == ""
    final_progress = third.record.read_model.sequential_stage_progress["text"]
    assert final_progress.complete is True
    assert tuple(final_progress.committed_artifact_refs) == ("unit-1", "unit-2")

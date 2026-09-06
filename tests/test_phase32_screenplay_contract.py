from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ScreenplayBlock,
    ScreenplayDraftArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    CharacterBibleArtifact,
    CharacterRecord,
    SceneDeckArtifact,
    SceneDeckScene,
)
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
from novel_workflow.providers.structured_schema import schema_example
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.workflows.phase32_prompt_contract import (
    build_phase32_provider_task_snapshot,
)
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import LONG_NOVEL_ROUTE, SCREENPLAY_SAMPLE_ROUTE
from tests.test_phase32_driver import FakePhase32Gateway
from tests.test_phase32_route_graph import _definition


def _cast() -> CharacterBibleArtifact:
    return CharacterBibleArtifact(
        characters=(
            CharacterRecord(
                subject_ref="maya",
                display_name="玛雅",
                role="档案记者",
                desire="找出被替换的签名页",
                stakes="证据失效会让调查失败",
                constraints=("不能把未经核验的怀疑当作事实",),
                voice="先核对证据再说话",
                arc_scope="从独自调查转向承担公开证据的后果",
            ),
        )
    )


def _scene_deck(*, heading: str = "INT. 档案室 - NIGHT") -> SceneDeckArtifact:
    return SceneDeckArtifact(
        scenes=(
            SceneDeckScene(
                scene_ref="scene-1",
                heading=heading,
                location_and_time="市档案馆，闭馆前十分钟",
                cast_subject_refs=("maya",),
                visible_goal="找到被调换的签名页。",
                opposition="保安要求她离开。",
                outcome="她带走一张带水印的复印件。",
                soft_page_target=2.5,
            ),
        )
    )


def _valid_script_payload() -> dict[str, object]:
    return ScreenplayDraftArtifact(
        scene_ref="scene-1",
        blocks=(
            ScreenplayBlock(kind="scene_heading", text="INT. 档案室 - NIGHT"),
            ScreenplayBlock(kind="action", text="玛雅在关灯前翻开最后一页。"),
        ),
    ).model_dump(mode="json")


def _upstream(tmp_path: Path):
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="screenplay_sample",
        stage_id="cast",
        artifact=_cast(),
    )
    deck = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="screenplay_sample",
        stage_id="scene_deck",
        artifact=_scene_deck(),
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "script",
            "active_unit_ref": "scene-1",
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "scene_deck": deck.artifact_ref,
            },
            "sequential_stage_progress": {
                "script": SequentialStageProgress(
                    ordered_unit_refs=("scene-1",)
                ).model_dump(mode="json")
            },
        }
    )
    return definition, store, state


def test_screenplay_prompt_and_context_freeze_one_scene_boundary(tmp_path: Path) -> None:
    definition, store, state = _upstream(tmp_path)
    snapshot = build_phase32_provider_task_snapshot(
        "screenplay_sample", definition.stage("script")
    )

    assert snapshot.prompt_template_id == "prompt.phase32.screenplay_sample.script.v4"
    assert "唯一 scene_heading" in snapshot.prompt_template
    assert "不得合并其他 scene" in snapshot.prompt_template
    assert "scene_heading、action、transition 必须省略 speaker_ref" in snapshot.prompt_template
    assert "禁止 dialogue_text、content、block_type" in snapshot.prompt_template
    block_schema = snapshot.output_schema["$defs"]["ScreenplayBlock"]["properties"]
    assert "对白也使用 text" in block_schema["text"]["description"]
    assert "禁止使用空字符串" in block_schema["speaker_ref"]["description"]

    context = compile_phase32_stage_context(
        artifact_store=store,
        definition=definition,
        state=state,
        stage=definition.stage("script"),
    )
    contract = context["scene_execution_contract"]
    assert contract["scene_ref"] == "scene-1"
    assert contract["heading"] == "INT. 档案室 - NIGHT"
    assert contract["cast_subject_refs"] == ["maya"]
    assert contract["boundary"] == (
        "one_contiguous_scene_only; use one frozen location/time; "
        "do not merge or reference another scene"
    )
    assert [
        scene["scene_ref"]
        for scene in context["upstream_artifacts"]["scene_deck"]["payload"]["scenes"]
    ] == ["scene-1"]


def test_screenplay_json_example_omits_optional_speaker_ref() -> None:
    manifest = RouteGraphCompiler().compile(SCREENPLAY_SAMPLE_ROUTE)
    snapshot = build_phase32_provider_task_snapshot(
        "screenplay_sample", manifest.stages[4]
    )

    example = schema_example(snapshot.output_schema)
    block = example["blocks"][0]
    assert set(block) == {"kind", "text"}
    assert "speaker_ref" not in block


def test_nested_long_detail_json_example_keeps_chapters_and_scenes_as_objects() -> None:
    manifest = RouteGraphCompiler().compile(LONG_NOVEL_ROUTE)
    snapshot = build_phase32_provider_task_snapshot(
        "long_novel", next(stage for stage in manifest.stages if stage.stage_id == "rolling_detail")
    )

    example = schema_example(snapshot.output_schema)
    chapter = example["windows"][0]["chapters"][0]
    assert isinstance(chapter, dict)
    assert set(("chapter_ref", "volume_ref", "scenes")).issubset(chapter)
    assert isinstance(chapter["scenes"][0], dict)


def test_scene_deck_prompt_v4_requires_atomic_location_and_time_boundaries() -> None:
    manifest = RouteGraphCompiler().compile(SCREENPLAY_SAMPLE_ROUTE)
    snapshot = build_phase32_provider_task_snapshot(
        "screenplay_sample", manifest.stages[3]
    )

    assert snapshot.prompt_template_id == "prompt.phase32.screenplay_sample.scene_deck.v4"
    assert "heading 必须只包含一个地点和一个时间标记" in snapshot.prompt_template
    assert "禁止使用斜杠、分号" in snapshot.prompt_template
    assert "不要把电话、抵达、进门或离开等转场压进同一个 scene" in snapshot.prompt_template


@pytest.mark.asyncio
async def test_screenplay_driver_accepts_exactly_bound_scene(tmp_path: Path) -> None:
    definition, store, state = _upstream(tmp_path)
    driver = Phase32RouteDriver(store, FakePhase32Gateway(_valid_script_payload()))

    candidate = await driver.generate_stage(
        definition=definition,
        state=state,
        stage=definition.stage("script"),
    )

    assert candidate.unit_ref == "scene-1"
    await driver.validate_stage(
        definition=definition,
        state=state,
        stage=definition.stage("script"),
        candidate=candidate,
    )


@pytest.mark.asyncio
async def test_screenplay_driver_rejects_multiple_scene_headings(tmp_path: Path) -> None:
    definition, store, state = _upstream(tmp_path)
    payload = {
        "scene_ref": "scene-1",
        "blocks": [
            {
                "kind": "scene_heading",
                "text": "INT. 档案室 - NIGHT",
                "speaker_ref": None,
            },
            {"kind": "action", "text": "玛雅翻开最后一页。", "speaker_ref": None},
            {
                "kind": "scene_heading",
                "text": "INT. 走廊 - NIGHT",
                "speaker_ref": None,
            },
            {"kind": "action", "text": "脚步声停在门外。", "speaker_ref": None},
        ],
    }
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))

    with pytest.raises(Phase32DriverError, match="Artifact payload"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("script"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"


@pytest.mark.asyncio
async def test_screenplay_driver_rejects_scene_deck_location_transition(
    tmp_path: Path,
) -> None:
    definition, store, state = _upstream(tmp_path)
    bad_deck = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="screenplay_sample",
        stage_id="scene_deck",
        artifact=_scene_deck(
            heading="INT. 档案室/陈默家门口 - NIGHT",
        ),
    )
    state = state.model_copy(
        update={"artifact_refs": {**state.artifact_refs, "scene_deck": bad_deck.artifact_ref}}
    )
    driver = Phase32RouteDriver(store, FakePhase32Gateway(_valid_script_payload()))

    with pytest.raises(Phase32DriverError, match="frozen Scene Deck and Cast"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("script"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"

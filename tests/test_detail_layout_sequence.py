from __future__ import annotations

import math
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.output_contracts.artifacts_vnext import VolumeArchitectureArtifact
from novel_workflow.runtime.graph.detail_planning import (
    detail_layout_turn_windows,
    detail_layout_volume_window,
)
from novel_workflow.runtime.graph.provider_gateway import StructuredProviderResult
from novel_workflow.runtime.graph.runtime import NarrativeRuntime, filesystem_stores
from novel_workflow.storage.narrative_run_repository import ExportPreferences, ProviderBinding
from novel_workflow.workflows.hierarchical_scale import plan_hierarchical_narrative_scale
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.fakes import FakeNarrativeProvider, fake_spine_payload
from tests.phase27_bindings import cover_asset_binding, provider_binding


class SimulatedProcessStop(BaseException):
    pass


def _bindings() -> dict[str, ProviderBinding]:
    return {
        stage: provider_binding(stage, max_tokens=6_000 if stage == "detail" else 12_000)
        for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
    }


def _create_three_volume_run(stores: Any, run_id: str) -> None:
    scale_profile = NarrativeScaleProfile(
        word_target_soft=7_500,
        capacity_policy={
            "volume_chapters_min": 1,
            "volume_chapters_preferred": 1,
            "volume_chapters_max": 2,
            "spine_chapters_per_turn_min": 0.5,
            "spine_chapters_per_turn_preferred": 1.0,
            "spine_chapters_per_turn_max": 1.5,
        },
    )
    stores.runs.create(
        run_id=run_id,
        project_id="project-1",
        workflow_id="workflow-1",
        workflow_revision="phase27-vnext",
        workflow_digest="a" * 64,
        quality_mode="fast",
        inputs={"project_brief": {"genre": "悬疑"}},
        scale_profile=scale_profile,
        hierarchical_scale_plan=plan_hierarchical_narrative_scale(
            scale_profile,
            quality_mode="fast",
        ),
        provider_bindings=_bindings(),
        cover_asset_binding=cover_asset_binding(),
        export_preferences=ExportPreferences(format="zip"),
    )


def _create_fifty_k_run(stores: Any, run_id: str) -> None:
    scale_profile = NarrativeScaleProfile(word_target_soft=50_000)
    stores.runs.create(
        run_id=run_id,
        project_id="project-1",
        workflow_id="workflow-1",
        workflow_revision="phase27-vnext",
        workflow_digest="a" * 64,
        quality_mode="fast",
        inputs={"project_brief": {"genre": "悬疑"}},
        scale_profile=scale_profile,
        hierarchical_scale_plan=plan_hierarchical_narrative_scale(
            scale_profile,
            quality_mode="fast",
        ),
        provider_bindings=_bindings(),
        cover_asset_binding=cover_asset_binding(),
        export_preferences=ExportPreferences(format="zip"),
    )


def _install_three_volume_boundaries(provider: FakeNarrativeProvider) -> None:
    original = provider.generate_proposal
    original_stage = provider.generate_stage

    async def generate_stage(request):
        result = await original_stage(request)
        if request.stage_id == "spine":
            return result.model_copy(update={"payload": fake_spine_payload(3)})
        return result

    async def generate_proposal(request):
        if request.proposal_type != "volume_boundary":
            return await original(request)
        provider.proposal_requests.append(request)
        return StructuredProviderResult(
            payload={
                "proposals": [
                    {
                        "boundary_key": f"boundary-{index}",
                        "turn_refs": [f"turn-{index}"],
                        "reason": f"第 {index} 个自然闭合",
                    }
                    for index in range(1, 4)
                ]
            },
            usage={"total_tokens": 2},
        )

    provider.generate_stage = generate_stage
    provider.generate_proposal = generate_proposal


def _long_form_architecture() -> VolumeArchitectureArtifact:
    volumes = []
    titles = ("声纹疑云", "证词回响", "终局听证")
    for index, (start, end, length_hint) in enumerate(
        ((1, 8, "medium"), (9, 16, "long"), (17, 25, "short")),
        start=1,
        ):
        turn_count = end - start + 1
        volumes.append(
            {
                "id": f"volume-{index}",
                "title": titles[index - 1],
                "promise": "兑现本卷局部承诺",
                "conflict": "压力持续升级",
                "climax": "本卷冲突达到峰值",
                "climax_turn_ref": f"turn-{start + math.ceil(turn_count * 0.6) - 1}",
                "closure": "局部问题闭合并留下下一卷压力",
                "turn_refs": [f"turn-{turn}" for turn in range(start, end + 1)],
                "cast_ids": ["subject-1"],
                "length_hint": length_hint,
            }
        )
    return VolumeArchitectureArtifact.model_validate({"volumes": volumes})


def test_later_volume_window_uses_the_precomputed_exact_allocation() -> None:
    architecture = _long_form_architecture()
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    window = detail_layout_volume_window(
        architecture=architecture,
        profile=profile,
        spine_turn_count=25,
        volume_index=1,
        allocated_chapters=13,
    )

    assert (window.chapter_min, window.chapter_target, window.chapter_max) == (13, 13, 13)
    assert window.book_chapter_min == 38
    assert window.book_chapter_target == 40
    assert window.book_chapter_max == 50
    with pytest.raises(ValueError, match="changed the frozen chapter allocation"):
        detail_layout_volume_window(
            architecture=architecture,
            profile=profile,
            spine_turn_count=25,
            volume_index=1,
            allocated_chapters=12,
        )


def test_fifty_k_volume_partitions_into_bounded_contiguous_turn_windows() -> None:
    architecture = VolumeArchitectureArtifact.model_validate(
        {
            "volumes": [
                {
                    "id": "volume-1",
                    "title": "雾锁归途",
                    "promise": "三天内证明灾害会发生",
                    "conflict": "旧日污点让所有人拒绝相信预警",
                    "climax": "公开承认误报并启动应急机制",
                    "climax_turn_ref": "turn-9",
                    "closure": "城市获救但主角承担不可逆代价",
                    "turn_refs": [f"turn-{index}" for index in range(1, 11)],
                    "cast_ids": ["subject-1"],
                    "length_hint": "long",
                }
            ]
        }
    )

    windows = detail_layout_turn_windows(
        architecture=architecture,
        profile=NarrativeScaleProfile(word_target_soft=50_000),
        spine_turn_count=10,
        volume_index=0,
        allocated_chapters=0,
    )

    assert [window.scope_ref for window in windows] == [
        f"volume-1:turn-window-{index}" for index in range(1, 5)
    ]
    assert [list(window.turn_refs) for window in windows] == [
        ["turn-1", "turn-2", "turn-3"],
        ["turn-4", "turn-5", "turn-6"],
        ["turn-7", "turn-8"],
        ["turn-9", "turn-10"],
    ]
    assert [window.chapter_target for window in windows] == [5, 5, 5, 5]
    assert [window.chapter_offset for window in windows] == [0, 5, 10, 15]
    assert [window.allocated_chapters for window in windows] == [0, 5, 10, 15]


@pytest.mark.asyncio
async def test_detail_layout_calls_each_volume_with_an_exact_narrow_context(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _install_three_volume_boundaries(provider)
    _create_three_volume_run(stores, "run-detail-volume-sequence")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    projection = await runtime.start("run-detail-volume-sequence")

    assert projection.status == "completed", projection.failure
    requests = [
        request
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    ]
    assert [request.operation_key for request in requests] == [
        f"run-detail-volume-sequence:detail_layout:proposal:1:volume-{index}:turn-window-1"
        for index in range(1, 4)
    ]
    assert [
        request.context["material"]["scale_plan"]["allocated_chapters"]
        for request in requests
    ] == [0, 1, 2]
    assert [
        request.context["material"]["scale_plan"]["chapter_range"]
        for request in requests
    ] == [[1, 1], [1, 1], [1, 1]]
    for index, request in enumerate(requests, start=1):
        material = request.context["material"]
        assert [item["id"] for item in material["volume_contracts"]] == [
            f"volume-{index}"
        ]
        assert [item["id"] for item in material["story_spine"]["turns"]] == [
            f"turn-{index}"
        ]
        assert len(material["chapter_slots"]) == material["scale_plan"]["chapter_target"]


@pytest.mark.asyncio
async def test_detail_layout_recovery_reuses_finished_turn_window_receipts(
    tmp_path,
    monkeypatch,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _create_fifty_k_run(stores, "run-detail-window-replay")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())
    original_succeed = stores.operations.succeed
    stopped = False

    def stop_after_second_window(run_id, operation_key, *args, **kwargs):
        nonlocal stopped
        result = original_succeed(run_id, operation_key, *args, **kwargs)
        if operation_key.endswith(":volume-1:turn-window-2") and not stopped:
            stopped = True
            raise SimulatedProcessStop("process stopped after the second window receipt")
        return result

    monkeypatch.setattr(stores.operations, "succeed", stop_after_second_window)
    with pytest.raises(SimulatedProcessStop, match="second window receipt"):
        await runtime.start("run-detail-window-replay")

    initial_requests = [
        request.operation_key
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    ]
    assert initial_requests == [
        "run-detail-window-replay:detail_layout:proposal:1:volume-1:turn-window-1",
        "run-detail-window-replay:detail_layout:proposal:1:volume-1:turn-window-2",
    ]
    second_request = next(
        request
        for request in provider.proposal_requests
        if request.operation_key == initial_requests[1]
    )
    assert [
        turn["id"]
        for turn in second_request.context["material"]["story_spine"]["turns"]
    ] == ["turn-4", "turn-5", "turn-6"]
    assert second_request.context["material"]["previous_window_layout"][
        "completed_turn_refs"
    ] == ["turn-1", "turn-2", "turn-3"]
    assert second_request.context["material"]["previous_window_layout"][
        "completed_dramatic_jobs"
    ] == [
        chapter["dramatic_job"]
        for chapter in second_request.context["material"]["previous_window_layout"]["chapters"]
    ]

    monkeypatch.setattr(stores.operations, "succeed", original_succeed)
    recovered = await runtime.recover("run-detail-window-replay")

    assert recovered.status == "completed", recovered.failure
    assert [
        request.operation_key
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    ] == [
        *initial_requests,
        "run-detail-window-replay:detail_layout:proposal:1:volume-1:turn-window-3",
        "run-detail-window-replay:detail_layout:proposal:1:volume-1:turn-window-4",
    ]


@pytest.mark.asyncio
async def test_detail_layout_rejects_cross_window_turn_regression(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    original = provider.generate_proposal

    async def regress_to_first_window(request):
        result = await original(request)
        if request.operation_key.endswith(":volume-1:turn-window-2"):
            chapters = result.payload["volumes"][0]["chapters"]
            return result.model_copy(
                update={
                    "payload": {
                        **result.payload,
                        "volumes": [
                            {
                                **result.payload["volumes"][0],
                                "chapters": [
                                    {**chapter, "turn_refs": ["turn-1"]}
                                    for chapter in chapters
                                ],
                            }
                        ],
                    }
                }
            )
        return result

    provider.generate_proposal = regress_to_first_window
    _create_fifty_k_run(stores, "run-detail-window-regression")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    failed = await runtime.start("run-detail-window-regression")

    assert failed.status == "awaiting_decision"
    assert failed.failure["evidence_ref"].endswith(
        ":volume-1:turn-window-2"
    )
    assert "outside volume-1:turn-window-2" in failed.failure["message"]
    assert [
        request.operation_key
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    ] == [
        "run-detail-window-regression:detail_layout:proposal:1:volume-1:turn-window-1",
        "run-detail-window-regression:detail_layout:proposal:1:volume-1:turn-window-2",
    ]


@pytest.mark.asyncio
async def test_invalid_middle_volume_requires_a_fresh_explicit_attempt(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = FakeNarrativeProvider()
    _install_three_volume_boundaries(provider)
    original = provider.generate_proposal
    invalid_once = False

    async def generate_invalid_middle_volume_once(request):
        nonlocal invalid_once
        result = await original(request)
        if (
            request.proposal_type == "detail_layout"
            and request.operation_key.endswith(":proposal:1:volume-2:turn-window-1")
            and not invalid_once
        ):
            invalid_once = True
            chapter = result.payload["volumes"][0]["chapters"][0]
            return result.model_copy(
                update={
                    "payload": {
                        **result.payload,
                        "volumes": [
                            {
                                **result.payload["volumes"][0],
                                "chapters": [
                                    {**chapter, "dramatic_job": "先承受压力"},
                                    {**chapter, "dramatic_job": "再作出选择"},
                                ],
                            }
                        ],
                    }
                }
            )
        return result

    provider.generate_proposal = generate_invalid_middle_volume_once
    _create_three_volume_run(stores, "run-detail-volume-regenerate")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    failed = await runtime.start("run-detail-volume-regenerate")

    assert failed.status == "awaiting_decision"
    assert failed.failure["evidence_ref"].endswith(
        ":proposal:1:volume-2:turn-window-1"
    )
    assert "frozen window requires exactly 1" in failed.failure["message"]
    decision = dict(failed.pending_decisions[0])
    completed = await runtime.resume(
        "run-detail-volume-regenerate",
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "regenerate",
        },
    )

    assert completed.status == "completed", completed.failure
    detail_keys = [
        request.operation_key
        for request in provider.proposal_requests
        if request.proposal_type == "detail_layout"
    ]
    assert detail_keys == [
        "run-detail-volume-regenerate:detail_layout:proposal:1:volume-1:turn-window-1",
        "run-detail-volume-regenerate:detail_layout:proposal:1:volume-2:turn-window-1",
        "run-detail-volume-regenerate:detail_layout:proposal:2:volume-1:turn-window-1",
        "run-detail-volume-regenerate:detail_layout:proposal:2:volume-2:turn-window-1",
        "run-detail-volume-regenerate:detail_layout:proposal:2:volume-3:turn-window-1",
    ]

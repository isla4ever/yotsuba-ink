from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.orchestration.planning_aggregate_commit import (
    HierarchicalPlanningCommitter,
)
from novel_workflow.output_contracts.artifacts_vnext import StorySpineArtifact
from novel_workflow.runtime.graph.context_compiler import NarrativeContextCompiler
from novel_workflow.runtime.graph.planning_authority import (
    FlatPlanningArtifactRejected,
    HierarchicalPlanningAuthority,
    PlanningCandidateNotCommitted,
)
from novel_workflow.runtime.graph.runtime import NarrativeRuntime, filesystem_stores
from novel_workflow.storage.narrative_run_repository import ExportPreferences
from novel_workflow.workflows.hierarchical_scale import plan_hierarchical_narrative_scale
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.fakes import FakeNarrativeProvider
from tests.fakes_hierarchical import FakeHierarchicalPlanningProvider
from tests.phase27_bindings import cover_asset_binding, provider_binding


def _create_million_run(stores, run_id: str = "run-million-runtime"):
    profile = NarrativeScaleProfile(word_target_soft=1_000_000)
    plan = plan_hierarchical_narrative_scale(profile, quality_mode="deep")
    stores.runs.create(
        run_id=run_id,
        project_id="project-million-runtime",
        workflow_id="official-deepseek-deep",
        workflow_revision="phase29-wave-1",
        workflow_digest="a" * 64,
        quality_mode="deep",
        inputs={"project_brief": {"genre": "悬疑"}},
        scale_profile=profile,
        hierarchical_scale_plan=plan,
        provider_bindings={
            stage: provider_binding(stage)
            for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
        },
        cover_asset_binding=cover_asset_binding(),
        export_preferences=ExportPreferences(format="zip", include_cover_image=False),
    )
    return plan


@pytest.mark.asyncio
async def test_runtime_mounts_recoverable_hierarchical_authority_and_context_is_bounded(
    tmp_path,
) -> None:
    root = tmp_path / "runtime"
    stores = filesystem_stores(root)
    plan = _create_million_run(stores)
    runtime = NarrativeRuntime.create(
        stores,
        FakeNarrativeProvider(),
        checkpointer=InMemorySaver(),
    )
    skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(plan)

    spine = runtime.planning.commit_spine(
        "run-million-runtime",
        skeleton.spine_root,
        skeleton.parts,
        skeleton.turns,
        source="fake-provider:spine:v1",
    )
    volumes = runtime.planning.commit_volumes(
        "run-million-runtime",
        skeleton.volume_root,
        skeleton.volumes,
        spine_version_id=spine.version_id,
        source="fake-provider:volumes:v1",
    )
    detail = runtime.planning.commit_detail(
        "run-million-runtime",
        skeleton.detail_index,
        skeleton.windows,
        skeleton.chapters,
        volume_version_id=volumes.version_id,
        source="fake-provider:detail:v1",
    )

    assert runtime.planning.store is stores.planning_aggregates
    assert stores.planning_aggregates.root == root / "planning_aggregates"
    state = {
        "run_id": "run-million-runtime",
        "domain_revision": 3,
        "artifact_refs": {
            "spine": spine.version_id,
            "volumes": volumes.version_id,
            "detail": detail.version_id,
        },
    }
    compiler = NarrativeContextCompiler(
        stores.runs,
        stores.artifacts,
        stores.chapters,
        planning=runtime.planning,
    )
    part_ref = skeleton.parts[2].id
    window_ref = skeleton.windows[8].id

    spine_packet = compiler.hierarchical_spine_part(state, part_ref)  # type: ignore[arg-type]
    volume_packet = compiler.hierarchical_volume_part(state, part_ref)  # type: ignore[arg-type]
    detail_packet = compiler.hierarchical_detail_window(state, window_ref)  # type: ignore[arg-type]

    assert spine_packet["sources"]["spine"]["version_id"] == spine.version_id
    assert spine_packet["material"]["part"]["id"] == part_ref
    assert len(spine_packet["material"]["turns"]) == plan.parts[2].turn_target
    assert len(volume_packet["material"]["volumes"]) == plan.parts[2].volume_target
    assert 1 <= len(detail_packet["material"]["chapters"]) <= plan.detail_window_max
    assert {item["detail_window_ref"] for item in detail_packet["material"]["chapters"]} == {
        window_ref
    }
    assert len(detail_packet["material"]["chapters"]) < plan.chapter_target

    recovered_stores = filesystem_stores(root)
    recovered = HierarchicalPlanningAuthority(
        recovered_stores.runs,
        recovered_stores.planning_aggregates,
    ).detail_window_context("run-million-runtime", detail.version_id, window_ref)
    assert recovered["source"]["signature"] == detail.signature
    assert recovered["chapters"] == detail_packet["material"]["chapters"]


@pytest.mark.asyncio
async def test_runtime_authority_rejects_scale_drift_before_publishing(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    plan = _create_million_run(stores, "run-scale-drift")
    skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(plan)
    authority = HierarchicalPlanningAuthority(stores.runs, stores.planning_aggregates)
    missing_turn = skeleton.turns[1:]

    with pytest.raises(ValueError, match="local turn target"):
        authority.commit_spine(
            "run-scale-drift",
            skeleton.spine_root,
            skeleton.parts,
            missing_turn,
            source="fake-provider:spine:drifted",
        )

    assert not (stores.planning_aggregates.root / "run-scale-drift").exists()


@pytest.mark.asyncio
async def test_spine_candidate_stays_out_of_committed_authority_until_acceptance(
    tmp_path,
) -> None:
    root = tmp_path / "runtime"
    stores = filesystem_stores(root)
    plan = _create_million_run(stores, "run-spine-candidate")
    skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(plan)
    authority = HierarchicalPlanningAuthority(stores.runs, stores.planning_aggregates)

    candidate = authority.save_spine_candidate(
        "run-spine-candidate",
        skeleton.spine_root,
        skeleton.parts,
        skeleton.turns,
        source="fake-provider:spine:generate:1",
    )

    assert candidate.candidate_id.startswith("spine-candidate-")
    assert candidate.unit_counts == {"parts": 6, "turns": 200}
    assert stores.planning_aggregates.list_versions("run-spine-candidate", "spine") == []
    with pytest.raises(FileNotFoundError):
        stores.planning_aggregates.latest_version("run-spine-candidate", "spine")
    replayed_candidate = authority.save_spine_candidate(
        "run-spine-candidate",
        skeleton.spine_root,
        skeleton.parts,
        skeleton.turns,
        source="fake-provider:spine:generate:1",
    )
    assert replayed_candidate == candidate
    assert len(stores.planning_aggregates.list_candidates("run-spine-candidate", "spine")) == 1
    with pytest.raises(PlanningCandidateNotCommitted, match="is not committed"):
        authority.spine_part_context(
            "run-spine-candidate",
            candidate.candidate_id,
            skeleton.parts[0].id,
        )

    committed = authority.accept_spine_candidate(
        "run-spine-candidate",
        candidate.candidate_id,
    )

    assert committed.signature == candidate.signature
    assert stores.planning_aggregates.latest_version("run-spine-candidate", "spine") == (
        committed.version_id
    )
    assert stores.planning_aggregates.read_candidate(
        "run-spine-candidate",
        "spine",
        candidate.candidate_id,
    )["root"] == skeleton.spine_root.model_dump(mode="json")

    recovered_stores = filesystem_stores(root)
    recovered = HierarchicalPlanningAuthority(
        recovered_stores.runs,
        recovered_stores.planning_aggregates,
    ).accept_spine_candidate("run-spine-candidate", candidate.candidate_id)
    assert recovered == committed
    assert len(recovered_stores.planning_aggregates.list_versions("run-spine-candidate", "spine")) == 1


@pytest.mark.asyncio
async def test_spine_regeneration_keeps_candidates_auditable_and_stale_replay_idempotent(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    plan = _create_million_run(stores, "run-spine-regenerate")
    skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(plan)
    authority = HierarchicalPlanningAuthority(stores.runs, stores.planning_aggregates)
    first = authority.save_spine_candidate(
        "run-spine-regenerate",
        skeleton.spine_root,
        skeleton.parts,
        skeleton.turns,
        source="fake-provider:spine:generate:1",
    )
    second = authority.save_spine_candidate(
        "run-spine-regenerate",
        skeleton.spine_root,
        skeleton.parts,
        skeleton.turns,
        source="fake-provider:spine:generate:2",
    )

    assert first.candidate_id != second.candidate_id
    assert [item.candidate_id for item in stores.planning_aggregates.list_candidates(
        "run-spine-regenerate",
        "spine",
    )] == [first.candidate_id, second.candidate_id]

    first_commit = authority.accept_spine_candidate(
        "run-spine-regenerate",
        first.candidate_id,
    )
    second_commit = authority.accept_spine_candidate(
        "run-spine-regenerate",
        second.candidate_id,
    )
    replay = authority.accept_spine_candidate(
        "run-spine-regenerate",
        first.candidate_id,
    )

    assert replay == first_commit
    assert second_commit.version_id != first_commit.version_id
    assert stores.planning_aggregates.latest_version("run-spine-regenerate", "spine") == (
        second_commit.version_id
    )
    assert len(stores.planning_aggregates.list_versions("run-spine-regenerate", "spine")) == 2


@pytest.mark.asyncio
async def test_spine_acceptance_revalidates_scale_and_rejects_flat_artifact_refs(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    plan = _create_million_run(stores, "run-spine-accept-guard")
    skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(plan)
    authority = HierarchicalPlanningAuthority(stores.runs, stores.planning_aggregates)
    removed_part_ref = skeleton.parts[-1].id
    drifted_parts = skeleton.parts[:-1]
    drifted_turns = [turn for turn in skeleton.turns if turn.part_ref != removed_part_ref]
    drifted_turn_refs = {turn.id for turn in drifted_turns}
    drifted_root = skeleton.spine_root.model_copy(
        update={
            "part_refs": [part.id for part in drifted_parts],
            "book_milestones": [
                binding
                for binding in skeleton.spine_root.book_milestones
                if binding.turn_ref in drifted_turn_refs
            ],
        }
    )
    candidate = HierarchicalPlanningCommitter(
        stores.planning_aggregates
    ).save_spine_candidate(
        "run-spine-accept-guard",
        drifted_root,
        drifted_parts,
        drifted_turns,
        source="test:scale-drift-candidate",
    )

    with pytest.raises(ValueError, match="frozen Part target"):
        authority.accept_spine_candidate(
            "run-spine-accept-guard",
            candidate.candidate_id,
        )
    assert stores.planning_aggregates.list_versions("run-spine-accept-guard", "spine") == []

    for flat_ref in (
        "spine-candidate-flat-artifact-ref",
        "spine-committed-flat-artifact-ref",
    ):
        with pytest.raises(FlatPlanningArtifactRejected, match="flat Spine Artifact ref"):
            authority.accept_spine_candidate("run-spine-accept-guard", flat_ref)


@pytest.mark.asyncio
async def test_incomplete_hierarchical_candidate_is_not_misclassified_as_flat(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    plan = _create_million_run(stores, "run-incomplete-candidate")
    skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(plan)
    authority = HierarchicalPlanningAuthority(stores.runs, stores.planning_aggregates)
    candidate = authority.save_spine_candidate(
        "run-incomplete-candidate",
        skeleton.spine_root,
        skeleton.parts,
        skeleton.turns,
        source="fake-provider:spine:generate:1",
    )
    candidate_dir = (
        stores.planning_aggregates.root
        / "run-incomplete-candidate"
        / "candidates"
        / "spine"
        / candidate.candidate_id
    )
    (candidate_dir / "units" / candidate.unit_files["turns"][0]).unlink()

    with pytest.raises(FileNotFoundError, match="Incomplete hierarchical Spine candidate"):
        authority.accept_spine_candidate(
            "run-incomplete-candidate",
            candidate.candidate_id,
        )


def test_context_rejects_a_flat_planning_artifact_ref_for_an_executable_run(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    _create_million_run(stores, "run-flat-rejected")
    flat = stores.artifacts.commit(
        "run-flat-rejected",
        "spine",
        _flat_spine().model_dump(mode="json"),
        source="test:retired-flat-spine",
    )
    authority = HierarchicalPlanningAuthority(stores.runs, stores.planning_aggregates)
    compiler = NarrativeContextCompiler(
        stores.runs,
        stores.artifacts,
        stores.chapters,
        planning=authority,
    )
    state = {
        "run_id": "run-flat-rejected",
        "artifact_refs": {"spine": flat.artifact_id},
    }

    with pytest.raises(FlatPlanningArtifactRejected, match="flat spine Artifact ref"):
        compiler.hierarchical_spine_part(  # type: ignore[arg-type]
            state,
            "part-not-used-because-ref-is-rejected",
        )

    state["artifact_refs"]["spine"] = "spine-v-missing-persisted-version"
    with pytest.raises(FileNotFoundError, match="Missing committed hierarchical spine"):
        compiler.hierarchical_spine_part(  # type: ignore[arg-type]
            state,
            "part-not-used-because-ref-is-missing",
        )


def _flat_spine() -> StorySpineArtifact:
    return StorySpineArtifact.model_validate(
        {
            "turns": [
                {
                    "id": "turn-1",
                    "cause": "未来电话点名旧案证人",
                    "change": "主角确认电话包含未公开的事故细节",
                    "progress_type": "information",
                    "milestones": ["inciting", "commitment"],
                },
                {
                    "id": "turn-2",
                    "cause": "证人承认死亡消息来自身份掩护",
                    "change": "父亲以新身份留下的证据链被揭示",
                    "progress_type": "relationship",
                    "milestones": ["midpoint_reversal", "crisis", "climax"],
                },
                {
                    "id": "turn-3",
                    "cause": "揭示迫使家人面对当年的选择",
                    "change": "旧案得到处理且主角承担职业处分",
                    "progress_type": "external",
                    "milestones": ["aftermath"],
                },
            ],
            "ending": "家人接受父亲当年假死隐匿的真相，主角承担处分。",
            "open_questions": ["未来电话的来源是否会在故事外延续？"],
            "progress_types": ["information", "relationship", "external"],
        }
    )

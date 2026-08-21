from __future__ import annotations

import asyncio
import os
import shutil
import threading

import pytest

from novel_workflow.orchestration.planning_aggregate_commit import (
    HierarchicalPlanningCommitter,
)
from novel_workflow.storage.planning_aggregate_store import PlanningAggregateStore
from novel_workflow.workflows.hierarchical_scale import plan_hierarchical_narrative_scale
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.fakes_hierarchical import FakeHierarchicalPlanningProvider


def million_plan():
    return plan_hierarchical_narrative_scale(
        NarrativeScaleProfile(word_target_soft=1_000_000),
        quality_mode="deep",
    )


def test_fake_provider_generates_and_commits_a_complete_bounded_skeleton(tmp_path) -> None:
    async def run():
        provider = FakeHierarchicalPlanningProvider()
        skeleton = await provider.generate_planning_skeleton(million_plan())
        store = PlanningAggregateStore(tmp_path)
        committer = HierarchicalPlanningCommitter(store)

        spine = committer.commit_spine(
            "run-million",
            skeleton.spine_root,
            skeleton.parts,
            skeleton.turns,
            source="fake-provider:spine:v1",
        )
        volumes = committer.commit_volumes(
            "run-million",
            skeleton.spine_root,
            skeleton.volume_root,
            skeleton.parts,
            skeleton.volumes,
            source="fake-provider:volumes:v1",
        )
        detail = committer.commit_detail(
            "run-million",
            skeleton.detail_index,
            skeleton.windows,
            skeleton.chapters,
            source="fake-provider:detail:v1",
        )

        assert provider.calls == 1
        assert spine.unit_counts == {"parts": 6, "turns": 200}
        assert volumes.unit_counts == {"volumes": 29}
        assert detail.unit_counts == {"windows": 17, "chapters": 400}
        assert store.latest_version("run-million", "spine") == spine.version_id
        assert store.latest_version("run-million", "volumes") == volumes.version_id
        assert store.latest_version("run-million", "detail") == detail.version_id

        snapshot = store.read("run-million", "detail")
        assert len(snapshot["root"]["chapter_order"]) == 400
        assert len(snapshot["units"]["chapters"]) == 400
        assert "chapters" not in snapshot["root"]
        assert len(store.list_versions("run-million", "detail")) == 1

    asyncio.run(run())


def test_repeating_the_same_skeleton_commit_is_idempotent(tmp_path) -> None:
    async def run():
        skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(million_plan())
        committer = HierarchicalPlanningCommitter(PlanningAggregateStore(tmp_path))
        first = committer.commit_spine(
            "run-replay",
            skeleton.spine_root,
            skeleton.parts,
            skeleton.turns,
            source="fake-provider:spine:v1",
        )
        second = committer.commit_spine(
            "run-replay",
            skeleton.spine_root,
            skeleton.parts,
            skeleton.turns,
            source="fake-provider:spine:v1",
        )

        assert second == first
        assert len(committer.store.list_versions("run-replay", "spine")) == 1

    asyncio.run(run())


def test_changing_source_creates_a_new_immutable_version(tmp_path) -> None:
    async def run():
        skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(million_plan())
        committer = HierarchicalPlanningCommitter(PlanningAggregateStore(tmp_path))
        first = committer.commit_spine(
            "run-source",
            skeleton.spine_root,
            skeleton.parts,
            skeleton.turns,
            source="fake-provider:spine:v1",
        )
        second = committer.commit_spine(
            "run-source",
            skeleton.spine_root,
            skeleton.parts,
            skeleton.turns,
            source="author-amendment:spine:v2",
        )

        assert second.version_id != first.version_id
        assert committer.store.latest_version("run-source", "spine") == second.version_id
        assert [manifest.version_id for manifest in committer.store.list_versions("run-source", "spine")] == [
            first.version_id,
            second.version_id,
        ]

    asyncio.run(run())


def test_invalid_aggregate_is_rejected_before_any_unit_file_is_published(tmp_path) -> None:
    async def run():
        skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(million_plan())
        committer = HierarchicalPlanningCommitter(PlanningAggregateStore(tmp_path))
        broken_parts = list(skeleton.parts)
        broken_parts[0] = broken_parts[0].model_copy(
            update={"turn_refs": broken_parts[0].turn_refs[:-1]}
        )

        with pytest.raises(ValueError, match="coverage|missing|unreferenced"):
            committer.commit_spine(
                "run-invalid",
                skeleton.spine_root,
                broken_parts,
                skeleton.turns,
                source="fake-provider:spine:invalid",
            )
        assert not (tmp_path / "run-invalid").exists()

    asyncio.run(run())


def test_invalid_replay_does_not_change_an_existing_latest_pointer(tmp_path) -> None:
    async def run():
        skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(million_plan())
        committer = HierarchicalPlanningCommitter(PlanningAggregateStore(tmp_path))
        valid = committer.commit_detail(
            "run-detail",
            skeleton.detail_index,
            skeleton.windows,
            skeleton.chapters,
            source="fake-provider:detail:v1",
        )
        broken_chapters = list(skeleton.chapters)
        broken_chapters[0] = broken_chapters[0].model_copy(
            update={"detail_window_ref": "window-missing"}
        )

        with pytest.raises(ValueError, match="unknown window"):
            committer.commit_detail(
                "run-detail",
                skeleton.detail_index,
                skeleton.windows,
                broken_chapters,
                source="author-amendment:detail:v2",
            )

        assert committer.store.latest_version("run-detail", "detail") == valid.version_id
        assert len(committer.store.list_versions("run-detail", "detail")) == 1

    asyncio.run(run())


def test_missing_unit_is_reported_when_reading_a_published_version(tmp_path) -> None:
    async def run():
        skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(million_plan())
        committer = HierarchicalPlanningCommitter(PlanningAggregateStore(tmp_path))
        manifest = committer.commit_detail(
            "run-missing-unit",
            skeleton.detail_index,
            skeleton.windows,
            skeleton.chapters,
            source="fake-provider:detail:v1",
        )
        missing_file = tmp_path / "run-missing-unit" / "detail" / manifest.version_id / "units" / manifest.unit_files["chapters"][0]
        missing_file.unlink()

        with pytest.raises(FileNotFoundError):
            committer.store.read("run-missing-unit", "detail")

    asyncio.run(run())


def test_retry_ignores_a_stale_pid_thread_temp_directory(tmp_path) -> None:
    async def run():
        skeleton = await FakeHierarchicalPlanningProvider().generate_planning_skeleton(million_plan())
        store = PlanningAggregateStore(tmp_path)
        committer = HierarchicalPlanningCommitter(store)
        manifest = committer.commit_spine(
            "run-stale-temp",
            skeleton.spine_root,
            skeleton.parts,
            skeleton.turns,
            source="fake-provider:spine:v1",
        )
        version_dir = tmp_path / "run-stale-temp" / "spine" / manifest.version_id
        shutil.rmtree(version_dir)
        stale_dir = version_dir.parent / (
            f".{manifest.version_id}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        stale_dir.mkdir()

        retry = committer.commit_spine(
            "run-stale-temp",
            skeleton.spine_root,
            skeleton.parts,
            skeleton.turns,
            source="fake-provider:spine:v1",
        )

        assert retry.version_id == manifest.version_id
        assert store.latest_version("run-stale-temp", "spine") == manifest.version_id
        assert stale_dir.exists()

    asyncio.run(run())

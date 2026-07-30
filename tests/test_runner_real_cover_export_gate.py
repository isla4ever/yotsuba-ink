from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.provider_profile_store import ProviderProfileStore
from novel_workflow.storage.provider_secret_store import ProviderSecretStore
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import ProviderProfile
from tests.workflow_runner_harness import planning_workflow


ROOT = Path("runtime/novel_workflow")
PROFILE_ID = "openai-compatible"
IMAGE_PROFILE_ID = "openai-compatible-image"
MODEL = "deepseek-v4-pro-202606"


def _real_provider_gate_enabled() -> bool:
    if os.environ.get("NOVEL_RUN_REAL_PROVIDER_GATES") != "1":
        return False
    secrets = ProviderSecretStore(ROOT / "provider_secrets.sqlite3")
    return secrets.has_api_key(PROFILE_ID) and secrets.has_api_key(IMAGE_PROFILE_ID)


def _real_provider_registry() -> ProviderRegistry:
    profile_store = ProviderProfileStore(ROOT / "provider_profiles.sqlite3")
    secret_store = ProviderSecretStore(ROOT / "provider_secrets.sqlite3")
    profiles = [ProviderProfile.model_validate(item) for item in profile_store.list()]
    assert secret_store.has_api_key(PROFILE_ID)
    assert secret_store.has_api_key(IMAGE_PROFILE_ID)
    return ProviderRegistry.from_profiles(profiles, secret_resolver=secret_store.get_api_key)


async def _run_and_approve_until_done(
    runner: NovelWorkflowRunner,
    workflow: Any,
    store: RunStore,
    run_id: str,
    inputs: dict[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    runner_done = asyncio.Event()

    async def approve_when_needed() -> None:
        confirmed: set[str] = set()
        while not runner_done.is_set():
            await asyncio.sleep(0.2)
            approval = store.read(run_id).get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id not in confirmed:
                store.approve_artifact(
                    run_id,
                    node_id=node_id,
                    output_key=str(approval["output_key"]),
                    artifact=approval["artifact"],
                )
                confirmed.add(node_id)

    approver = asyncio.create_task(approve_when_needed())
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            events.append(event)
    finally:
        runner_done.set()
        await approver
    return events


@pytest.mark.asyncio
@pytest.mark.skipif(not _real_provider_gate_enabled(), reason="real provider gates are opt-in")
async def test_real_provider_reaches_cover_and_export_in_balanced_mode(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text", "cover", "export"], provider_profile_id=PROFILE_ID)
    workflow.quality_mode = "balanced"
    workflow.nodes[-2].provider_profile_id = "openai-compatible"
    workflow.nodes[-2].image_provider_profile_id = IMAGE_PROFILE_ID
    workflow.stage_configs["cover"].provider_profile_id = "openai-compatible"
    workflow.stage_configs["cover"].image_provider_profile_id = IMAGE_PROFILE_ID
    for node_id in ["info", "summary", "outline", "detail", "text"]:
        node = next(item for item in workflow.nodes if item.id == node_id)
        node.variant_policy.enabled = False
        node.model_settings.model = MODEL
        node.model_settings.max_tokens = 1600 if node_id == "info" else 1800 if node_id != "text" else 2200
        workflow.stage_configs[node_id].variant_policy = node.variant_policy
        workflow.stage_configs[node_id].model_settings = node.model_settings
    workflow.stage_configs["cover"].model_settings.model = MODEL
    workflow.stage_configs["export"].model_settings.model = "deepseek-v4-pro-202606"

    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    runner = NovelWorkflowRunner(providers=_real_provider_registry(), wiki_store=wiki, run_store=store)

    run_id = "real-cover-export"
    inputs = {
        "project_id": "p-real-cover-export",
        "title": "真实封面导出门禁",
        "quality_mode": "balanced",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 1, "conflict_density": "中高"},
            "detail": {"chapter_count": 1, "must_include": ["目标", "冲突", "伏笔", "章末钩子"]},
            "text": {"chapter_count": 1, "chapter_words": 800, "batch_generate": False},
            "cover": {"cover_style": "电影感悬疑", "aspect_ratio": "2:3"},
            "export": {"export_format": "Markdown + JSON"},
        },
    }
    store.create(run_id, workflow, inputs)

    events = await _run_and_approve_until_done(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[0] == "run_started"
    assert event_types[-1] == "run_completed"
    assert "run_export_ready" not in event_types
    assert "cover" in {str(event.get("node_id") or "") for event in events}
    assert "export" in {str(event.get("node_id") or "") for event in events}
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "cover" for event in events)
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "export" for event in events)
    assert any(event["type"] == "node_completed" and event.get("node_id") == "export" for event in events)

    state = store.read(run_id)["state"]
    cover = state["artifacts"]["cover"]
    export_artifact = state["artifacts"]["export"]
    assert state["runtime_phase"] == "completed"
    assert state["pending_export_return"] is False
    assert state["progress"]["cover"] == {"status": "completed", "output_key": "cover"}
    assert state["progress"]["export"] == {"status": "completed", "output_key": "export"}
    assert cover["brief"]
    assert cover["candidates"]
    assert cover["selected_candidate_id"]
    assert export_artifact["manifest"]
    assert export_artifact["chapters"]
    assert export_artifact["package_status"]["ready"] is True
    assert export_artifact["package_status"]["kind"] == "md"
    assert export_artifact["validation"]["cover"] == "ready"
    assert export_artifact["validation"]["quality"] == "ready"
    assert not state["errors"]

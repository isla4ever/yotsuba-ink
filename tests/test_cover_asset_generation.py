from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.memory.wiki import WikiStore
from novel_workflow.orchestration.cover_asset_retry import retry_cover_asset_candidate
from novel_workflow.orchestration.cover_assets import generate_cover_assets
from novel_workflow.providers.base import GeneratedImage, ImageProvider
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import FakeTextProvider, fake_png_bytes


class SequenceImageProvider(ImageProvider):
    name = "sequence-image"

    def __init__(self, responses: list[GeneratedImage | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        self.calls.append({"prompt": prompt, "context": dict(context)})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _plan() -> dict[str, Any]:
    return {
        "brief": "雾港、磁带与证词构成悬疑封面。",
        "visual_keywords": ["雾港", "磁带", "声纹"],
        "composition": "2:3 竖版，保留上方标题安全区。",
        "copy_suggestions": ["雾港旧声"],
        "prompt": "cinematic mist harbor, cassette tape, suspense novel cover",
        "candidates": [
            {"id": f"cover-{index}", "image_url": "/fake/from-text.png", "composition": f"构图 {index}", "palette": "冷青", "quality_summary": "标题区清晰"}
            for index in range(1, 4)
        ],
        "selected_candidate_id": "cover-2",
    }


def _image(*, cost: float | None = None, content: bytes | None = None) -> GeneratedImage:
    usage = {"cost_usd": cost} if cost is not None else {}
    return GeneratedImage(content=content or fake_png_bytes(), mime_type="image/png", usage=usage)


def _setup(tmp_path, provider: ImageProvider, *, stage_config: dict[str, Any] | None = None):
    workflow = default_workflow().model_copy(deep=True)
    workflow.nodes = [next(node for node in workflow.nodes if node.id == "cover")]
    workflow.edges = []
    workflow.stage_configs = {"cover": workflow.stage_configs["cover"]}
    image_profile = next(item for item in workflow.provider_profiles if item.id == "openai-compatible-image")
    image_profile.estimated_cost_per_output_usd = 0.04
    inputs = {"project_id": "cover-assets", "stage_configs": {"cover": {"candidate_count": 3, "aspect_ratio": "2:3", **(stage_config or {})}}}
    store = RunStore(tmp_path / "runs")
    store.create("cover-assets", workflow, inputs)
    state = NovelRunState(run_id="cover-assets", project_id="cover-assets", workflow_id=workflow.id, inputs=inputs, run_has_started=True)
    store.update_state("cover-assets", state)
    registry = ProviderRegistry(
        text_provider=FakeTextProvider(),
        image_provider=provider,
        text_providers={"openai-compatible": FakeTextProvider()},
        image_providers={"openai-compatible-image": provider},
    )
    runner = NovelWorkflowRunner(registry, WikiStore(tmp_path / "wiki"), store)
    return workflow, workflow.nodes[0], state, store, runner


@pytest.mark.asyncio
async def test_each_cover_candidate_generates_once_and_persists_real_assets(tmp_path) -> None:
    provider = SequenceImageProvider([_image(), _image(), _image()])
    workflow, node, state, store, runner = _setup(tmp_path, provider)

    events = [event async for event in generate_cover_assets(runner, node, state, workflow, state.run_id, plan=_plan())]

    artifact = state.artifacts["cover"]
    assert len(provider.calls) == 3
    assert len({call["context"]["idempotency_key"] for call in provider.calls}) == 3
    assert all(candidate["asset_status"] == "ready" for candidate in artifact["candidates"])
    assert all(candidate["asset_source"] == "production" for candidate in artifact["candidates"])
    assert all(candidate["image_url"].startswith("/api/runs/cover-assets/cover-assets/") for candidate in artifact["candidates"])
    progress = [event for event in events if event["type"] == "asset_progress_updated"]
    assert {event["asset_status"] for event in progress} == {"generating", "ready"}
    assert all(event["candidate_id"] and event["generation_key"] for event in progress)
    stored = store.read(state.run_id)["state"]["artifacts"]["cover"]
    assert stored["asset_generation"]["status"] == "ready"


@pytest.mark.asyncio
async def test_persisted_assets_are_reused_without_calling_provider_again(tmp_path) -> None:
    provider = SequenceImageProvider([_image(), _image(), _image()])
    workflow, node, state, _, runner = _setup(tmp_path, provider)
    _ = [event async for event in generate_cover_assets(runner, node, state, workflow, state.run_id, plan=_plan())]
    replacement = SequenceImageProvider([])
    runner.providers.image_providers["openai-compatible-image"] = replacement

    _ = [event async for event in generate_cover_assets(runner, node, state, workflow, state.run_id)]

    assert replacement.calls == []
    assert all(candidate["asset_status"] == "ready" for candidate in state.artifacts["cover"]["candidates"])


@pytest.mark.asyncio
async def test_invalid_image_is_failed_and_can_be_retried_without_losing_successes(tmp_path) -> None:
    provider = SequenceImageProvider([_image(), _image(content=b"not-an-image"), _image(), _image()])
    workflow, node, state, store, runner = _setup(tmp_path, provider)
    _ = [event async for event in generate_cover_assets(runner, node, state, workflow, state.run_id, plan=_plan())]
    failed = state.artifacts["cover"]["candidates"][1]
    assert failed["asset_status"] == "failed"
    assert state.artifacts["cover"]["asset_generation"]["status"] == "partial"
    assert state.artifacts["cover"]["selected_candidate_id"] == "cover-1"
    state.approval_required = True
    state.stage_confirmation_state["cover"] = {"status": "pending"}
    store.update_state(state.run_id, state)
    store.request_approval(state.run_id, "cover", "cover", state.artifacts["cover"])

    result = await retry_cover_asset_candidate(runner, workflow, run_id=state.run_id, candidate_id="cover-2", request_id="retry-cover-2")

    assert result["artifact"]["candidates"][1]["asset_status"] == "ready"
    assert result["artifact"]["asset_generation"]["status"] == "ready"
    assert len(provider.calls) == 4


@pytest.mark.asyncio
async def test_all_invalid_candidates_never_enter_ready(tmp_path) -> None:
    provider = SequenceImageProvider([_image(content=b"bad-1"), _image(content=b"bad-2"), _image(content=b"bad-3")])
    workflow, node, state, _, runner = _setup(tmp_path, provider)

    with pytest.raises(RuntimeError, match="所有封面候选均生成失败"):
        _ = [event async for event in generate_cover_assets(runner, node, state, workflow, state.run_id, plan=_plan())]

    assert all(candidate["asset_status"] == "failed" for candidate in state.artifacts["cover"]["candidates"])
    assert state.artifacts["cover"]["asset_generation"]["status"] == "failed"


@pytest.mark.asyncio
async def test_image_cost_budget_stops_later_candidates(tmp_path) -> None:
    provider = SequenceImageProvider([_image(cost=0.04), _image(), _image()])
    workflow, node, state, _, runner = _setup(tmp_path, provider, stage_config={"image_budget_usd": 0.05})

    events = [event async for event in generate_cover_assets(runner, node, state, workflow, state.run_id, plan=_plan())]

    assert len(provider.calls) == 1
    statuses = [candidate["asset_status"] for candidate in state.artifacts["cover"]["candidates"]]
    assert statuses == ["ready", "blocked", "planned"]
    assert any(event["type"] == "stage_budget_exceeded" for event in events)


@pytest.mark.asyncio
async def test_cover_asset_url_serves_the_verified_immutable_bytes(tmp_path) -> None:
    provider = SequenceImageProvider([_image(), _image(), _image()])
    workflow, node, state, store, runner = _setup(tmp_path, provider)
    _ = [event async for event in generate_cover_assets(runner, node, state, workflow, state.run_id, plan=_plan())]
    candidate = state.artifacts["cover"]["candidates"][0]
    app = create_app()
    app.state.run_store = store

    response = TestClient(app).get(candidate["image_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"].endswith("immutable")
    assert response.content == fake_png_bytes()

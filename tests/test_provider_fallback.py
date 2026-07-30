from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from novel_workflow.orchestration.cover_provider_execution import generate_cover_with_fallback
from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.fallback import fallback_decision
from novel_workflow.providers.lifecycle import provider_deletion_references
from novel_workflow.providers.readiness import live_provider_readiness_report
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.stages.registry import StageRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.usage import drain_budget_events
from novel_workflow.workflows.schemas import FallbackTarget, NovelRunState, ProviderProfile
from novel_workflow.workflows.templates import default_workflow
from novel_workflow.memory.wiki import WikiStore
from tests.fakes import FakeImageProvider, FakeTextProvider, fake_png_bytes


class SequenceTextProvider(TextProvider):
    name = "sequence-text"

    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise AssertionError("structured generation expected")

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        self.calls.append({"prompt": prompt, "task_name": task_name, "context": context, "schema": schema})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class SequenceImageProvider(ImageProvider):
    name = "sequence-image"

    def __init__(self, response: GeneratedImage | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        self.calls.append({"prompt": prompt, "context": context})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _text_setup(tmp_path, primary: TextProvider, backup: TextProvider):
    workflow = default_workflow().model_copy(deep=True)
    node = workflow.nodes[0]
    node.provider_profile_id = "primary-text"
    node.fallback_targets = [FallbackTarget(provider_profile_id="backup-text", model="backup-model", priority=1)]
    state = NovelRunState(run_id="fallback-text", project_id="fallback-text", workflow_id=workflow.id, inputs={"title": "备用链路"})
    store = RunStore(tmp_path / "runs")
    store.create(state.run_id, workflow, state.inputs)
    store.update_state(state.run_id, state)
    registry = ProviderRegistry(
        text_provider=primary,
        image_provider=FakeImageProvider(),
        text_providers={"primary-text": primary, "backup-text": backup},
        image_providers={"openai-compatible-image": FakeImageProvider()},
    )
    stages = StageRegistry(registry, WikiStore(tmp_path / "wiki"), workflow.prompt_templates, store)
    return workflow, node, state, store, stages


@pytest.mark.asyncio
async def test_text_fallback_uses_independent_budget_operations_and_audit_events(tmp_path) -> None:
    primary = SequenceTextProvider(ProviderResponseError("insufficient_balance", "balance"))
    backup = SequenceTextProvider(FakeTextProvider())
    backup.response = await FakeTextProvider().generate_structured("", task_name="info_recommend", context={}, schema=None)
    _, node, state, _, stages = _text_setup(tmp_path, primary, backup)

    result = await stages.execute(node, state)
    events = drain_budget_events(state)

    assert result["selected_title"] == "雾港旧声"
    assert len(primary.calls) == 1
    assert len(backup.calls) == 1
    assert [event["type"] for event in events] == [
        "provider_attempt_started",
        "provider_attempt_failed",
        "provider_fallback_scheduled",
        "provider_attempt_started",
        "provider_attempt_succeeded",
    ]
    operations = state.budget_state["scopes"][node.id]["operations"]
    assert [(item["provider_profile_id"], item["status"]) for item in operations] == [
        ("primary-text", "failed"),
        ("backup-text", "completed"),
    ]
    assert primary.calls[0]["context"]["idempotency_key"] != backup.calls[0]["context"]["idempotency_key"]


@pytest.mark.asyncio
async def test_text_contract_failure_never_switches_provider(tmp_path) -> None:
    primary = SequenceTextProvider(ProviderResponseError("json_parse_failed", "invalid json"))
    backup = SequenceTextProvider({"should": "not run"})
    _, node, state, _, stages = _text_setup(tmp_path, primary, backup)

    with pytest.raises(ProviderResponseError, match="invalid json"):
        await stages.execute(node, state)

    assert not backup.calls
    assert [event["type"] for event in drain_budget_events(state)][-1] == "provider_fallback_blocked"
    assert len(state.budget_state["scopes"][node.id]["operations"]) == 1


@pytest.mark.asyncio
async def test_image_fallback_uses_a_derived_generation_key(tmp_path) -> None:
    workflow = default_workflow().model_copy(deep=True)
    node = next(item for item in workflow.nodes if item.id == "cover")
    node.image_provider_profile_id = "primary-image"
    node.image_fallback_targets = [FallbackTarget(provider_profile_id="backup-image", model="backup-image-model", priority=1)]
    workflow.provider_profiles.extend([
        ProviderProfile(id="primary-image", name="Primary", kind="openai-compatible-image", template_id="openai-compatible-image", default_model="primary-image-model"),
        ProviderProfile(id="backup-image", name="Backup", kind="openai-compatible-image", template_id="openai-compatible-image", default_model="backup-image-model", estimated_cost_per_output_usd=0.05),
    ])
    primary = SequenceImageProvider(ProviderResponseError("insufficient_balance", "balance"))
    backup = SequenceImageProvider(GeneratedImage(content=fake_png_bytes(), mime_type="image/png"))
    registry = ProviderRegistry(
        text_provider=FakeTextProvider(),
        image_provider=primary,
        text_providers={"openai-compatible": FakeTextProvider()},
        image_providers={"primary-image": primary, "backup-image": backup},
    )
    state = NovelRunState(run_id="fallback-image", project_id="fallback-image", workflow_id=workflow.id, inputs={"stage_configs": {"cover": {"candidate_count": 1}}})
    store = RunStore(tmp_path / "runs")
    store.create(state.run_id, workflow, state.inputs)
    store.update_state(state.run_id, state)
    runner = type("Runner", (), {"providers": registry, "run_store": store})()

    result = await generate_cover_with_fallback(
        runner, node, state, workflow,
        run_id=state.run_id,
        candidate_id="cover-1",
        prompt="cover prompt",
        base_generation_key="a" * 64,
        primary_model="primary-image-model",
        size="1024x1536",
        quality="medium",
        candidate_count=1,
        explicit_retry=False,
    )

    assert result.target.provider_profile_id == "backup-image"
    assert result.generation_key != "a" * 64
    assert primary.calls[0]["context"]["idempotency_key"] == "a" * 64
    assert backup.calls[0]["context"]["idempotency_key"] == result.generation_key
    operations = state.budget_state["image"]["scopes"][node.id]["operations"]
    assert [(item["kind"], item["status"]) for item in operations] == [("generation", "failed"), ("fallback", "completed")]


@pytest.mark.asyncio
async def test_image_timeout_does_not_create_a_second_paid_image(tmp_path) -> None:
    workflow = default_workflow().model_copy(deep=True)
    node = next(item for item in workflow.nodes if item.id == "cover")
    node.image_provider_profile_id = "primary-image"
    node.image_fallback_targets = [FallbackTarget(provider_profile_id="backup-image", model="backup-image-model", priority=1)]
    workflow.provider_profiles.extend([
        ProviderProfile(id="primary-image", name="Primary", kind="openai-compatible-image", template_id="openai-compatible-image", default_model="primary-image-model"),
        ProviderProfile(id="backup-image", name="Backup", kind="openai-compatible-image", template_id="openai-compatible-image", default_model="backup-image-model"),
    ])
    primary = SequenceImageProvider(ProviderResponseError("timeout", "timeout"))
    backup = SequenceImageProvider(GeneratedImage(content=fake_png_bytes(), mime_type="image/png"))
    registry = ProviderRegistry(FakeTextProvider(), primary, image_providers={"primary-image": primary, "backup-image": backup})
    state = NovelRunState(run_id="uncertain-image", project_id="uncertain-image", workflow_id=workflow.id, inputs={"stage_configs": {"cover": {"candidate_count": 1}}})
    store = RunStore(tmp_path / "runs")
    store.create(state.run_id, workflow, state.inputs)
    store.update_state(state.run_id, state)
    runner = type("Runner", (), {"providers": registry, "run_store": store})()

    with pytest.raises(ProviderResponseError, match="timeout"):
        await generate_cover_with_fallback(
            runner, node, state, workflow,
            run_id=state.run_id, candidate_id="cover-1", prompt="cover prompt", base_generation_key="b" * 64,
            primary_model="primary-image-model", size="1024x1536", quality="medium", candidate_count=1, explicit_retry=False,
        )

    assert not backup.calls
    blocked = [event for event in drain_budget_events(state) if event["type"] == "provider_fallback_blocked"]
    assert blocked and blocked[0]["response_uncertain"] is True


def test_fallback_contract_rejects_duplicate_provider_and_priority() -> None:
    workflow = default_workflow().model_dump()
    workflow["nodes"][0]["fallback_targets"] = [
        {"provider_profile_id": "same", "model": "a", "enabled": True, "priority": 1},
        {"provider_profile_id": "same", "model": "b", "enabled": True, "priority": 1},
    ]
    from novel_workflow.workflows.schemas import WorkflowDefinition

    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate(workflow)


def test_fallback_error_policy_distinguishes_text_and_uncertain_image_failures() -> None:
    assert fallback_decision(ProviderResponseError("timeout", "timeout"), "text").allowed is True
    image = fallback_decision(ProviderResponseError("timeout", "timeout"), "image")
    assert image.allowed is False
    assert image.response_uncertain is True
    assert fallback_decision(ProviderResponseError("json_parse_failed", "json"), "text").allowed is False


def test_readiness_and_provider_lifecycle_include_enabled_fallback_targets() -> None:
    workflow = default_workflow().model_copy(deep=True)
    for profile in workflow.provider_profiles:
        profile.base_url = "https://provider.example/v1"
    backup = ProviderProfile(
        id="backup-text",
        name="Backup",
        kind="openai-compatible",
        template_id="openai-compatible-text",
        base_url="https://backup.example/v1",
        default_model="backup-model",
    )
    workflow.provider_profiles.append(backup)
    workflow.nodes[0].fallback_targets = [
        FallbackTarget(provider_profile_id=backup.id, model=backup.default_model, priority=1)
    ]

    report = live_provider_readiness_report(workflow, secret_resolver=lambda _provider_id: "configured")
    check = next(item for item in report.checks if item.provider_id == backup.id)

    assert report.ok is True
    assert any("文本备用 1" in label for label in check.used_by)
    assert any("文本备用 1" in label for label in provider_deletion_references(backup, [workflow]))

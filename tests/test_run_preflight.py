from __future__ import annotations

import json

import pytest

from novel_workflow.orchestration.run_preflight import (
    PROVIDER_STAGES,
    RunPreflightError,
    RunPreflightService,
)
from novel_workflow.providers.template_contract import ProviderTemplate
from novel_workflow.storage.json_store import JsonStore
from novel_workflow.storage.provider_profile_store import ProviderProfileStore
from novel_workflow.storage.provider_secret_store import ProviderSecretStore
from novel_workflow.workflows.prompt_templates import default_prompt_templates
from novel_workflow.workflows.schemas import ProviderProfile
from novel_workflow.workflows.templates import default_workflow


TEXT_PROVIDER_ID = "phase27-text"
IMAGE_PROVIDER_ID = "phase27-image"


def _service(tmp_path) -> tuple[
    RunPreflightService,
    ProviderProfileStore,
    JsonStore,
    ProviderSecretStore,
]:
    providers = ProviderProfileStore(tmp_path / "providers.sqlite3")
    prompts = JsonStore(tmp_path / "prompts")
    secrets = ProviderSecretStore(tmp_path / "secrets.sqlite3")
    providers.write(
        TEXT_PROVIDER_ID,
        ProviderProfile(
            id=TEXT_PROVIDER_ID,
            name="Offline DeepSeek",
            kind="openai-compatible",
            template_id="deepseek-text",
            base_url="https://provider.invalid/v1",
            default_model="deepseek-v4-pro",
            model_options=["deepseek-v4-pro"],
        ).model_dump(mode="json"),
    )
    providers.write(
        IMAGE_PROVIDER_ID,
        ProviderProfile(
            id=IMAGE_PROVIDER_ID,
            name="Offline Image",
            kind="openai-compatible-image",
            template_id="openai-compatible-image",
            base_url="https://images.invalid/v1",
            default_model="gpt-image-2",
            model_options=["gpt-image-2"],
        ).model_dump(mode="json"),
    )
    for prompt in default_prompt_templates():
        prompts.write(prompt.id, prompt.model_dump(mode="json"))
    secrets.set_api_key(TEXT_PROVIDER_ID, "offline-text-secret")
    secrets.set_api_key(IMAGE_PROVIDER_ID, "offline-image-secret")
    return (
        RunPreflightService(
            provider_store=providers,
            prompt_store=prompts,
            secret_store=secrets,
        ),
        providers,
        prompts,
        secrets,
    )


def _workflow(*, text_provider_id: str = TEXT_PROVIDER_ID, image_provider_id: str = IMAGE_PROVIDER_ID):
    workflow = default_workflow().model_copy(deep=True)
    for node in workflow.nodes:
        if node.id != "export":
            node.provider_profile_id = text_provider_id
            node.model_settings.model = "deepseek-v4-pro"
            node.model_settings.temperature = 0.3
            node.model_settings.max_tokens = 12_000
            node.model_settings.top_p = 0.8
            node.model_settings.timeout_seconds = 30
        if node.id == "cover":
            node.image_provider_profile_id = image_provider_id
    return workflow


def _freeze(service: RunPreflightService):
    return service.freeze_workflow(_workflow())


def test_deepseek_json_object_contract_freezes_every_phase27_task(tmp_path) -> None:
    service, _, _, _ = _service(tmp_path)

    frozen = _freeze(service)

    assert set(frozen.provider_bindings) == set(PROVIDER_STAGES)
    assert {
        task.effective_mode
        for binding in frozen.provider_bindings.values()
        for task in binding.structured_tasks.values()
    } == {"json_object"}
    assert frozen.provider_bindings["spine"].structured_tasks.keys() == {
        "spine",
        "role_demand.proposal",
    }
    assert frozen.provider_bindings["text"].structured_tasks.keys() == {
        "text.review.continuity",
        "text.review.character",
        "text.review.prose",
        "text.evidence",
    }


def test_prompt_only_provider_is_rejected_before_run_creation(tmp_path) -> None:
    service, providers, _, secrets = _service(tmp_path)
    providers.write(
        "prompt-only",
        ProviderProfile(
            id="prompt-only",
            name="Prompt only",
            kind="openai-compatible",
            template_id="openai-compatible-text",
            base_url="https://prompt-only.invalid/v1",
            default_model="unknown-model",
        ).model_dump(mode="json"),
    )
    secrets.set_api_key("prompt-only", "offline-prompt-only-secret")

    with pytest.raises(RunPreflightError) as captured:
        service.freeze_workflow(_workflow(text_provider_id="prompt-only"))

    assert captured.value.code == "strict_structured_output_required"


def test_incompatible_strict_schema_is_rejected_before_run_creation(
    tmp_path,
    monkeypatch,
) -> None:
    service, _, _, _ = _service(tmp_path)
    incompatible = ProviderTemplate(
        id="deepseek-text",
        label="Strict test template",
        kind="openai-compatible",
        base_url="https://provider.invalid/v1",
        default_model="deepseek-v4-pro",
        api_key_env="UNUSED_TEST_KEY",
        docs_url="https://docs.invalid",
        structured_output_mode="json_schema",
        supports_json_schema=True,
        schema_max_chars=256,
    )
    monkeypatch.setattr(
        "novel_workflow.orchestration.run_preflight.require_provider_template",
        lambda _template_id, _kind: incompatible,
    )

    with pytest.raises(RunPreflightError) as captured:
        _freeze(service)

    assert captured.value.code == "strict_schema_unsupported"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("unknown", "provider_not_found"),
        ("disabled", "provider_disabled"),
        ("kind", "provider_kind_mismatch"),
    ],
)
def test_provider_identity_and_kind_fail_closed(
    tmp_path,
    mutation: str,
    expected_code: str,
) -> None:
    service, providers, _, _ = _service(tmp_path)
    provider_id = "missing-provider"
    if mutation == "disabled":
        profile = ProviderProfile.model_validate(providers.read(TEXT_PROVIDER_ID))
        providers.write(
            TEXT_PROVIDER_ID,
            profile.model_copy(update={"enabled": False}).model_dump(mode="json"),
        )
        provider_id = TEXT_PROVIDER_ID
    elif mutation == "kind":
        provider_id = IMAGE_PROVIDER_ID

    with pytest.raises(RunPreflightError) as captured:
        service.freeze_workflow(_workflow(text_provider_id=provider_id))

    assert captured.value.code == expected_code


def test_environment_secret_cannot_replace_the_saved_secret(
    tmp_path,
    monkeypatch,
) -> None:
    service, _, _, secrets = _service(tmp_path)
    secrets.delete_api_key(TEXT_PROVIDER_ID)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment-only-secret")

    with pytest.raises(RunPreflightError) as captured:
        _freeze(service)

    assert captured.value.code == "secret_missing"


def test_frozen_binding_is_unchanged_after_settings_and_prompt_edits(tmp_path) -> None:
    service, providers, prompts, _ = _service(tmp_path)
    frozen = _freeze(service)
    brief = frozen.provider_bindings["brief"]

    profile = ProviderProfile.model_validate(providers.read(TEXT_PROVIDER_ID))
    providers.write(
        TEXT_PROVIDER_ID,
        profile.model_copy(
            update={"base_url": "https://changed.invalid/v1"}
        ).model_dump(mode="json"),
    )
    prompt = prompts.read("prompt-brief")
    prompts.write("prompt-brief", {**prompt, "content": "changed after Run creation"})

    assert brief.provider_config.base_url == "https://provider.invalid/v1"
    assert brief.prompt_template != "changed after Run creation"
    assert brief.prompt_template_id == "prompt-brief"


def test_frozen_run_projection_contains_no_secret_or_settings_only_metadata(tmp_path) -> None:
    service, _, _, _ = _service(tmp_path)
    payload = _freeze(service).model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "offline-text-secret" not in serialized
    assert "offline-image-secret" not in serialized
    assert "api_key_env" not in serialized
    assert "docs_url" not in serialized
    assert "capability_docs" not in serialized

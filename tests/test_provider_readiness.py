from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.providers.readiness import (
    ProviderReadinessError,
    ensure_live_provider_readiness,
    live_provider_readiness_report,
)
from novel_workflow.providers.registry import ProviderRegistry, ProviderUnavailableError
from novel_workflow.workflows.schemas import ProviderProfile
from novel_workflow.workflows.templates import default_workflow


def _anthropic_evaluation_profile() -> ProviderProfile:
    return ProviderProfile(
        id="anthropic-evaluation",
        name="Claude compatibility evaluation",
        kind="openai-compatible",
        template_id="anthropic-openai-text",
        base_url="https://api.anthropic.com/v1",
        default_model="claude-sonnet-5",
        model_options=["claude-sonnet-5"],
        enabled=True,
    )


def test_readiness_report_deduplicates_shared_stage_providers() -> None:
    workflow = default_workflow()
    for profile in workflow.provider_profiles:
        profile.base_url = "https://provider.example/v1"
    secrets = {profile.id for profile in workflow.provider_profiles}

    report = live_provider_readiness_report(
        workflow,
        secret_resolver=lambda provider_id: "configured" if provider_id in secrets else None,
    )

    assert report.ok is True
    assert report.scope == "configuration_only"
    assert report.checked_provider_count == 2
    text_check = next(check for check in report.checks if check.expected_kind == "openai-compatible")
    image_check = next(check for check in report.checks if check.expected_kind == "openai-compatible-image")
    assert len(text_check.used_by) > 3
    assert image_check.used_by == ["AI 封面图片生成"]
    assert all(check.ready for check in report.checks)


def test_readiness_report_keeps_text_and_image_blockers_visible() -> None:
    workflow = default_workflow()

    report = live_provider_readiness_report(workflow)

    assert report.ok is False
    assert report.checked_provider_count == 2
    assert len(report.checks) == 2
    assert all("secret_missing" in check.issue_codes for check in report.checks)
    assert "Provider 配置不完整" in report.message
    assert "DeepSeek 官方文本" in report.message
    assert "图片接口" in report.message

    with pytest.raises(ProviderReadinessError) as raised:
        ensure_live_provider_readiness(workflow)
    assert raised.value.report == report


def test_readiness_blocks_legacy_profiles_with_unknown_templates() -> None:
    workflow = default_workflow()
    workflow.provider_profiles[0].template_id = "retired-template"
    for profile in workflow.provider_profiles:
        profile.base_url = "https://provider.example/v1"

    report = live_provider_readiness_report(
        workflow,
        secret_resolver=lambda provider_id: "configured",
    )

    text_check = next(check for check in report.checks if check.expected_kind == "openai-compatible")
    assert report.ok is False
    assert text_check.issue_codes == ["provider_template_invalid"]
    assert "厂商模板无效" in text_check.message


def test_readiness_api_is_configuration_only_and_does_not_create_a_run(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    text_provider = next(item for item in client.get("/api/providers").json() if item["kind"] == "openai-compatible")
    text_provider["base_url"] = "https://private-provider.example/v1"
    client.post("/api/providers", json=text_provider)
    client.post(f"/api/providers/{text_provider['id']}/secret", json={"api_key": "unit-test-secret"})

    response = client.post(
        "/api/providers/readiness",
        json={"workflow_id": default_workflow().id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["scope"] == "configuration_only"
    assert payload["checked_provider_count"] == 2
    text_check = next(check for check in payload["checks"] if check["provider_id"] == text_provider["id"])
    image_check = next(check for check in payload["checks"] if check["expected_kind"] == "openai-compatible-image")
    assert text_check["ready"] is True
    assert image_check["issue_codes"] == ["base_url_missing", "secret_missing"]
    runs_root = tmp_path / "runtime" / "novel_workflow" / "runs"
    assert not runs_root.exists() or not any(runs_root.iterdir())
    assert "unit-test-secret" not in response.text
    assert "private-provider.example" not in response.text


def test_readiness_api_rejects_unknown_workflow_without_creating_state(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    response = client.post("/api/providers/readiness", json={"workflow_id": "missing-workflow"})

    assert response.status_code == 404
    runs_root = tmp_path / "runtime" / "novel_workflow" / "runs"
    assert not runs_root.exists() or not any(runs_root.iterdir())


def test_provider_template_api_exposes_tokenhub_image_contract(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    response = client.get("/api/providers/templates")

    assert response.status_code == 200
    template = next(item for item in response.json() if item["id"] == "tokenhub-hunyuan-image")
    assert template["base_url"] == "https://tokenhub.tencentmaas.com/v1"
    assert template["default_model"] == "hy-image-v3.0"
    assert template["docs_url"] == "https://cloud.tencent.com/document/product/1823/130080"
    assert template["execution_allowed"] is False
    assert "提交任务与查询任务" in template["execution_policy_note"]
    assert template["supports_image_quality"] is False
    gpt_image = next(item for item in response.json() if item["id"] == "gpt-image-2-gateway")
    assert gpt_image["default_model"] == "gpt-image-2"
    assert gpt_image["image_static_parameters"] == {"response_format": "b64_json"}
    assert len(response.json()) == 32
    template_ids = {item["id"] for item in response.json()}
    assert {
        "deepseek-text",
        "xiaomi-mimo-text",
        "xiaomi-mimo-api-text",
        "dashscope-text",
        "siliconflow-text",
        "moonshot-text",
        "zhipu-text",
        "zhipu-coding-plan",
        "openrouter-text",
        "zhipu-cogview-image",
        "siliconflow-image",
        "openrouter-image",
        "gemini-text",
        "groq-text",
        "together-text",
        "xai-text",
        "mistral-text",
        "fireworks-text",
        "cerebras-text",
        "anthropic-openai-text",
        "xai-image",
        "together-image",
    } <= template_ids
    zhipu_coding_plan = next(item for item in response.json() if item["id"] == "zhipu-coding-plan")
    assert zhipu_coding_plan["base_url"] == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert zhipu_coding_plan["default_model"] == "glm-5.2"
    anthropic = next(item for item in response.json() if item["id"] == "anthropic-openai-text")
    assert anthropic["integration_tier"] == "compatibility"
    assert anthropic["supports_response_format"] is False
    together = next(item for item in response.json() if item["id"] == "together-image")
    assert together["image_size_field"] == "width_height"
    assert together["image_static_parameters"]["response_format"] == "base64"
    zhipu_image = next(item for item in response.json() if item["id"] == "zhipu-cogview-image")
    assert zhipu_image["default_model"] == "glm-image"
    assert zhipu_image["docs_url"].endswith("/image-generation/glm-image")
    openrouter_image = next(item for item in response.json() if item["id"] == "openrouter-image")
    assert openrouter_image["image_endpoint_path"] == "/images"
    assert openrouter_image["models_endpoint_path"] == "/images/models"
    assert "/guides/overview/multimodal/image-generation" in openrouter_image["docs_url"]


def test_provider_templates_disable_unmetered_sdk_retries() -> None:
    from novel_workflow.providers.templates import list_provider_templates

    assert all(template.max_retries == 0 for template in list_provider_templates())


def test_provider_stage_parameters_only_use_phase27_authorities() -> None:
    from novel_workflow.providers.templates import list_provider_templates

    legacy = {"info", "summary", "characters", "outline"}
    phase27 = {
        "brief",
        "spine",
        "cast",
        "volumes",
        "detail",
        "text",
        "text.evidence",
        "text.review",
        "cover",
        "export",
    }
    for template in list_provider_templates():
        parameter_maps = [
            template.stage_request_parameters,
            template.stage_extra_body_parameters,
        ]
        for capability in template.model_capabilities:
            parameter_maps.extend(
                [
                    capability.stage_request_parameters,
                    capability.stage_extra_body_parameters,
                ]
            )
        for stage_parameters in parameter_maps:
            assert legacy.isdisjoint(stage_parameters), template.id
            assert set(stage_parameters).issubset(phase27), template.id


@pytest.mark.parametrize(
    ("parameters", "expected_ready"),
    [
        (["temperature", "max_tokens"], False),
        (["response_format", "temperature"], True),
        (["structured_outputs", "reasoning"], True),
    ],
)
def test_openrouter_readiness_uses_discovered_parameter_hints(
    parameters: list[str],
    expected_ready: bool,
) -> None:
    workflow = default_workflow()
    model = "openai/gpt-5.6"
    profile = ProviderProfile(
        id="openrouter-live",
        name="OpenRouter",
        kind="openai-compatible",
        template_id="openrouter-text",
        base_url="https://openrouter.ai/api/v1",
        default_model=model,
        model_options=[model],
        model_supported_parameters={model: parameters},
        enabled=True,
    )
    workflow.provider_profiles.append(profile)
    for existing in workflow.provider_profiles:
        existing.base_url = existing.base_url or "https://provider.example/v1"
    for node in workflow.nodes:
        if node.type != "export":
            node.provider_profile_id = profile.id
            node.model_settings.model = model

    report = live_provider_readiness_report(workflow, secret_resolver=lambda _: "configured")
    check = next(item for item in report.checks if item.provider_id == profile.id)

    assert check.ready is expected_ready
    assert ("model_parameter_not_supported" in check.issue_codes) is (not expected_ready)


def test_policy_blocked_image_template_never_enters_provider_registry() -> None:
    profile = ProviderProfile(
        id="tokenhub-image-blocked",
        name="TokenHub HY Image",
        kind="openai-compatible-image",
        template_id="tokenhub-hunyuan-image",
        base_url="https://tokenhub.tencentmaas.com/v1",
        default_model="hy-image-v3.0",
        model_options=["hy-image-v3.0"],
        enabled=True,
    )

    registry = ProviderRegistry.from_profiles(
        [profile],
        secret_resolver=lambda _: "configured-secret",
    )

    assert "tokenhub-image-blocked" not in registry.image_providers
    with pytest.raises(ProviderUnavailableError):
        registry.image_for("tokenhub-image-blocked")


def test_anthropic_compatibility_is_blocked_by_workflow_readiness() -> None:
    workflow = default_workflow()
    profile = _anthropic_evaluation_profile()
    workflow.provider_profiles.append(profile)
    for node in workflow.nodes:
        if node.type != "export":
            node.provider_profile_id = profile.id
            node.model_settings.model = profile.default_model

    report = live_provider_readiness_report(
        workflow,
        secret_resolver=lambda provider_id: "configured" if provider_id == profile.id else None,
    )
    check = next(item for item in report.checks if item.provider_id == profile.id)

    assert check.ready is False
    assert "provider_workflow_blocked" in check.issue_codes
    assert "provider_policy_blocked" not in check.issue_codes


def test_anthropic_compatibility_never_enters_provider_registry() -> None:
    profile = _anthropic_evaluation_profile()

    registry = ProviderRegistry.from_profiles(
        [profile],
        secret_resolver=lambda _: "configured-secret",
    )

    assert profile.id not in registry.text_providers
    with pytest.raises(ProviderUnavailableError):
        registry.text_for(profile.id)


def test_profile_registry_does_not_fall_back_to_global_environment(monkeypatch) -> None:
    monkeypatch.setenv("NOVEL_LLM_BASE_URL", "https://environment.example/v1")
    monkeypatch.setenv("NOVEL_LLM_API_KEY", "environment-secret")
    profile = ProviderProfile(
        id="frozen-profile",
        name="Frozen profile",
        kind="openai-compatible",
        template_id="openai-compatible-text",
        base_url="https://profile.example/v1",
        default_model="profile-model",
        enabled=True,
    )

    registry = ProviderRegistry.from_profiles([profile], secret_resolver=lambda _: None)

    assert profile.id not in registry.text_providers
    with pytest.raises(ProviderUnavailableError):
        registry.text_for(profile.id)


def test_provider_registry_rejects_runtime_inherit_selection(monkeypatch) -> None:
    monkeypatch.setenv("NOVEL_LLM_BASE_URL", "https://environment.example/v1")
    monkeypatch.setenv("NOVEL_LLM_API_KEY", "environment-secret")
    registry = ProviderRegistry.from_env()

    with pytest.raises(ProviderUnavailableError):
        registry.text_for("inherit")


def test_provider_stage_probe_route_does_not_exist() -> None:
    from novel_workflow.api.app import create_app

    routes = {
        (route.path, method)
        for route in create_app().routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/providers/stage-probe", "POST") not in routes


def test_provider_template_exposes_xiaomi_mimo_token_plan_contract() -> None:
    from novel_workflow.providers.templates import provider_template

    template = provider_template("xiaomi-mimo-text", "openai-compatible")

    assert template.base_url == "https://token-plan-cn.xiaomimimo.com/v1"
    assert template.default_model == "mimo-v2.5-pro"
    assert template.model_options == ["mimo-v2.5-pro", "mimo-v2.5"]
    assert template.api_key_env == "XIAOMI_MIMO_API_KEY"
    assert template.supports_response_format is True
    assert template.structured_output_mode == "json_object"
    assert template.requires_json_example is True


def test_new_project_templates_use_documented_stable_models() -> None:
    from novel_workflow.providers.templates import provider_template

    kimi = provider_template("moonshot-text", "openai-compatible")
    qwen = provider_template("dashscope-text", "openai-compatible")

    assert kimi.default_model == "kimi-k3"
    assert kimi.model_options == ["kimi-k3", "kimi-k2.6"]
    assert "kimi-k2.5" not in kimi.model_options
    assert qwen.model_options == [
        "qwen3.7-max",
        "qwen3.7-plus",
        "qwen3.7-flash",
        "qwen3.6-flash",
    ]

    groq = provider_template("groq-text", "openai-compatible")
    assert groq.model_options == [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
    ]
    assert "llama-3.3-70b-versatile" not in groq.model_options
    assert groq.max_tokens_field == "max_completion_tokens"

    mistral = provider_template("mistral-text", "openai-compatible")
    assert mistral.docs_url == "https://docs.mistral.ai/api/endpoint/chat"
    assert mistral.supports_prompt_cache_key is True

    kimi = provider_template("moonshot-text", "openai-compatible")
    assert kimi.supports_prompt_cache_key is True


def test_tokenhub_template_uses_pay_as_you_go_catalog_contract() -> None:
    from novel_workflow.providers.templates import provider_template

    template = provider_template("tokenhub-text", "openai-compatible")

    assert template.base_url == "https://tokenhub.tencentmaas.com/v1"
    assert template.default_model == "deepseek-v4-pro"
    assert "deepseek-v4-pro-202606" not in template.model_options
    assert {
        "deepseek-v3.2",
        "hy3",
        "hy3-preview",
        "glm-5.2",
        "kimi-k3",
        "minimax-m2.5",
        "minimax-m2.7",
        "qwen3.5-plus",
    }.issubset(template.model_options)
    assert template.integration_tier == "gateway"
    assert template.docs_url == "https://cloud.tencent.com/document/product/1823/130079"
    assert template.structured_output_mode == "json_schema"
    assert template.supports_json_schema is True
    assert template.requires_json_example is True


def test_deepseek_pro_reserves_structured_output_capacity() -> None:
    from novel_workflow.providers.templates import provider_template

    template = provider_template("deepseek-text", "openai-compatible")
    capability = next(
        item
        for item in template.model_capabilities
        if item.model_pattern == "deepseek-v4-pro*"
    )

    assert capability.stage_request_parameters == {}
    assert capability.stage_extra_body_parameters["brief"] == {
        "thinking": {"type": "disabled"}
    }
    assert capability.stage_extra_body_parameters["spine"] == {
        "thinking": {"type": "disabled"}
    }
    assert all(
        capability.stage_extra_body_parameters[stage] == {
            "thinking": {"type": "disabled"}
        }
        for stage in ("cast", "volumes", "detail", "text", "text.evidence", "text.review")
    )


def test_materialization_preserves_the_explicit_provider_and_model() -> None:
    from novel_workflow.workflows.schemas import ProviderProfile
    from novel_workflow.workflows.templates import materialize_workflow_for_execution

    workflow = default_workflow()
    workflow.provider_profiles.append(
        ProviderProfile(
            id="xiaomi-mimo-api-text",
            name="小米 MiMo Token Plan",
            kind="openai-compatible",
            template_id="xiaomi-mimo-api-text",
            base_url="https://api.xiaomimimo.com/v1",
            default_model="mimo-v2.5-pro",
            model_options=["mimo-v2.5-pro"],
            enabled=True,
        )
    )
    brief = next(node for node in workflow.nodes if node.id == "brief")
    brief.provider_profile_id = "xiaomi-mimo-api-text"
    brief.model_settings.model = "mimo-v2.5-pro"
    live = materialize_workflow_for_execution(workflow)

    live_brief = next(node for node in live.nodes if node.id == "brief")
    assert live_brief.provider_profile_id == "xiaomi-mimo-api-text"
    assert live_brief.model_settings.model == "mimo-v2.5-pro"

    report = live_provider_readiness_report(live, secret_resolver=lambda _: "configured")

    check = next(item for item in report.checks if item.provider_id == "xiaomi-mimo-api-text")
    assert check.model == "mimo-v2.5-pro"
    assert check.ready is True
    assert "model_not_discovered" not in check.issue_codes


def test_readiness_still_blocks_a_manually_selected_undiscovered_model() -> None:
    from novel_workflow.workflows.schemas import ProviderProfile
    from novel_workflow.workflows.templates import materialize_workflow_for_execution

    workflow = default_workflow()
    workflow.provider_profiles.append(
        ProviderProfile(
            id="xiaomi-mimo-api-text",
            name="小米 MiMo API",
            kind="openai-compatible",
            template_id="xiaomi-mimo-api-text",
            base_url="https://api.xiaomimimo.com/v1",
            default_model="mimo-v2.5-pro",
            model_options=["mimo-v2.5-pro"],
            enabled=True,
        )
    )
    live = materialize_workflow_for_execution(workflow)
    live.nodes[0].provider_profile_id = "xiaomi-mimo-api-text"
    live.nodes[0].model_settings.model = "mimo-v2.5"

    report = live_provider_readiness_report(live, secret_resolver=lambda _: "configured")
    check = next(item for item in report.checks if item.provider_id == "xiaomi-mimo-api-text")

    assert check.ready is False
    assert "model_not_discovered" in check.issue_codes


def test_readiness_blocks_token_plan_for_application_execution() -> None:
    from novel_workflow.workflows.schemas import ProviderProfile

    workflow = default_workflow()
    workflow.provider_profiles.append(
        ProviderProfile(
            id="xiaomi-mimo-token-plan",
            name="小米 MiMo Token Plan",
            kind="openai-compatible",
            template_id="xiaomi-mimo-text",
            base_url="https://token-plan-cn.xiaomimimo.com/v1",
            default_model="mimo-v2.5-pro",
            model_options=["mimo-v2.5-pro", "mimo-v2.5"],
            enabled=True,
        )
    )
    for node in workflow.nodes:
        if node.type != "export":
            node.provider_profile_id = "xiaomi-mimo-token-plan"
    report = live_provider_readiness_report(workflow, secret_resolver=lambda _: "configured")
    check = next(item for item in report.checks if item.provider_id == "xiaomi-mimo-token-plan")

    assert check.ready is False
    assert "provider_policy_blocked" in check.issue_codes
    assert "按量计费 API" in check.message


def test_vendor_api_roots_are_not_rewritten_to_openai_v1() -> None:
    from novel_workflow.providers.templates import openai_base_url

    assert openai_base_url("https://open.bigmodel.cn/api/paas/v4/") == "https://open.bigmodel.cn/api/paas/v4"
    assert openai_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions") == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_workflow_reads_live_provider_profiles_and_keeps_new_vendor_instances(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    official = client.get("/api/workflows/default").json()
    duplicated = client.post(
        f"/api/workflows/{official['id']}/duplicate",
        json={"new_id": "wf-provider-live-copy", "name": "Provider live copy"},
    )
    assert duplicated.status_code == 200
    workflow = duplicated.json()
    workflow["provider_profiles"][0]["name"] = "stale workflow copy"
    workflow["provider_profiles"][0]["base_url"] = "https://stale.invalid/v1"
    created = {
        "id": "deepseek-secondary",
        "name": "DeepSeek Secondary",
        "kind": "openai-compatible",
        "template_id": "deepseek-text",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-v4-pro",
        "model_options": ["deepseek-v4-pro"],
        "enabled": True,
    }

    assert client.post("/api/providers", json=created).status_code == 200
    saved = client.post("/api/workflows", json=workflow).json()
    refreshed = client.get(f"/api/workflows/{workflow['id']}").json()

    assert all(item["name"] != "stale workflow copy" for item in saved["provider_profiles"])
    assert any(item["id"] == created["id"] for item in saved["provider_profiles"])
    assert any(item["id"] == created["id"] for item in refreshed["provider_profiles"])


def test_unused_provider_can_be_deleted_with_its_saved_secret(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = {
        "id": "temporary-gemini",
        "name": "Temporary Gemini",
        "kind": "openai-compatible",
        "template_id": "gemini-text",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-3.5-flash",
        "model_options": ["gemini-3.5-flash"],
        "is_global_default": False,
        "enabled": True,
    }
    assert client.post("/api/providers", json=provider).status_code == 200
    assert client.post("/api/providers/temporary-gemini/secret", json={"api_key": "delete-me"}).status_code == 200

    response = client.delete("/api/providers/temporary-gemini")

    assert response.status_code == 200
    assert all(item["id"] != "temporary-gemini" for item in client.get("/api/providers").json())
    assert client.delete("/api/providers/temporary-gemini/secret").status_code == 404


def test_referenced_or_global_provider_cannot_be_deleted(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = next(item for item in client.get("/api/providers").json() if item["kind"] == "openai-compatible")

    response = client.delete(f"/api/providers/{provider['id']}")

    assert response.status_code == 409
    assert "无法删除" in response.json()["detail"]
    assert "全局默认" in response.json()["detail"]
    assert any(item["id"] == provider["id"] for item in client.get("/api/providers").json())


def test_provider_save_rejects_unknown_or_mismatched_template(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = next(item for item in client.get("/api/providers").json() if item["kind"] == "openai-compatible")

    unknown = client.post("/api/providers", json={**provider, "id": "unknown-template", "template_id": "not-real"})
    mismatched = client.post("/api/providers", json={**provider, "id": "wrong-kind", "template_id": "xai-image"})

    assert unknown.status_code == 422
    assert "Unknown provider template" in unknown.json()["detail"]
    assert mismatched.status_code == 422
    assert "does not support kind" in mismatched.json()["detail"]


def test_global_default_provider_is_persisted_atomically_by_kind(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    original = next(item for item in client.get("/api/providers").json() if item["kind"] == "openai-compatible")
    provider = {
        "id": "secondary-groq",
        "name": "Secondary Groq",
        "kind": "openai-compatible",
        "template_id": "groq-text",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": "openai/gpt-oss-120b",
        "model_options": ["openai/gpt-oss-120b"],
        "is_global_default": False,
        "enabled": True,
    }
    assert client.post("/api/providers", json=provider).status_code == 200

    response = client.post("/api/providers/default", json={"provider_id": provider["id"], "kind": provider["kind"]})

    assert response.status_code == 200
    updated = {item["id"]: item for item in response.json()}
    assert updated[provider["id"]]["is_global_default"] is True
    assert updated[original["id"]]["is_global_default"] is False
    refreshed = {item["id"]: item for item in client.get("/api/providers").json()}
    assert refreshed[provider["id"]]["is_global_default"] is True
    assert refreshed[original["id"]]["is_global_default"] is False


def test_disabled_provider_cannot_become_global_default(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = {
        "id": "disabled-gemini",
        "name": "Disabled Gemini",
        "kind": "openai-compatible",
        "template_id": "gemini-text",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-3.5-flash",
        "model_options": ["gemini-3.5-flash"],
        "is_global_default": False,
        "enabled": False,
    }
    assert client.post("/api/providers", json=provider).status_code == 200

    response = client.post("/api/providers/default", json={"provider_id": provider["id"], "kind": provider["kind"]})

    assert response.status_code == 409
    assert "Disabled Provider" in response.json()["detail"]

from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.providers.readiness import (
    ProviderReadinessError,
    ensure_live_provider_readiness,
    live_provider_readiness_report,
)
from novel_workflow.workflows.templates import default_workflow


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
    assert "文本接口" in report.message
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

    response = client.post("/api/providers/readiness", json={"workflow_id": "default-novel-workflow"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["scope"] == "configuration_only"
    assert payload["checked_provider_count"] == 2
    text_check = next(check for check in payload["checks"] if check["provider_id"] == text_provider["id"])
    image_check = next(check for check in payload["checks"] if check["expected_kind"] == "openai-compatible-image")
    assert text_check["ready"] is True
    assert image_check["issue_codes"] == ["base_url_missing", "secret_missing"]
    assert not any((tmp_path / "runtime" / "novel_workflow" / "runs").iterdir())
    assert "unit-test-secret" not in response.text
    assert "private-provider.example" not in response.text


def test_readiness_api_rejects_unknown_workflow_without_creating_state(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    response = client.post("/api/providers/readiness", json={"workflow_id": "missing-workflow"})

    assert response.status_code == 404
    assert not any((tmp_path / "runtime" / "novel_workflow" / "runs").iterdir())


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
    assert template["image_size_separator"] == ":"
    assert template["image_size_field"] == "size"
    assert template["image_count_field"] == "images"
    assert template["image_response_field"] == "data"
    assert template["supports_image_quality"] is False
    assert len(response.json()) == 28
    template_ids = {item["id"] for item in response.json()}
    assert {
        "deepseek-text",
        "dashscope-text",
        "siliconflow-text",
        "moonshot-text",
        "zhipu-text",
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
    anthropic = next(item for item in response.json() if item["id"] == "anthropic-openai-text")
    assert anthropic["integration_tier"] == "compatibility"
    assert anthropic["supports_response_format"] is False
    together = next(item for item in response.json() if item["id"] == "together-image")
    assert together["image_size_field"] == "width_height"
    assert together["image_static_parameters"]["response_format"] == "base64"


def test_vendor_api_roots_are_not_rewritten_to_openai_v1() -> None:
    from novel_workflow.providers.templates import openai_base_url

    assert openai_base_url("https://open.bigmodel.cn/api/paas/v4/") == "https://open.bigmodel.cn/api/paas/v4"
    assert openai_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions") == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_workflow_reads_live_provider_profiles_and_keeps_new_vendor_instances(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    workflow = client.get("/api/workflows/default").json()
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
    refreshed = client.get("/api/workflows/default").json()

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

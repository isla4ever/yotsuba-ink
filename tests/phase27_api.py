from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.workflows.schemas import ProviderProfile
from novel_workflow.workflows.templates import default_workflow


PROVIDER_STAGES = ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
TEXT_PROVIDER_ID = "phase27-deepseek"
IMAGE_PROVIDER_ID = "phase27-image"
TEXT_MODEL = "deepseek-v4-pro"
IMAGE_MODEL = "gpt-image-2"


def configure_phase27_providers(client: TestClient) -> None:
    text_profile = {
        "id": TEXT_PROVIDER_ID,
        "name": "Phase 27 Offline DeepSeek",
        "kind": "openai-compatible",
        "template_id": "deepseek-text",
        "base_url": "https://provider.invalid/v1",
        "api_key_env": "PHASE27_TEST_TEXT_API_KEY",
        "default_model": TEXT_MODEL,
        "model_options": [TEXT_MODEL],
        "enabled": True,
    }
    image_profile = {
        "id": IMAGE_PROVIDER_ID,
        "name": "Phase 27 Offline Image",
        "kind": "openai-compatible-image",
        "template_id": "openai-compatible-image",
        "base_url": "https://images.invalid/v1",
        "api_key_env": "PHASE27_TEST_IMAGE_API_KEY",
        "default_model": IMAGE_MODEL,
        "model_options": [IMAGE_MODEL],
        "enabled": True,
    }
    for profile in (text_profile, image_profile):
        response = client.post("/api/providers", json=profile)
        assert response.status_code == 200, response.text
        secret = client.post(
            f"/api/providers/{profile['id']}/secret",
            json={"api_key": f"offline-test-secret-{profile['id']}"},
        )
        assert secret.status_code == 200, secret.text
    workflow = default_workflow().model_copy(deep=True)
    workflow.provider_profiles = [
        ProviderProfile.model_validate(text_profile),
        ProviderProfile.model_validate(image_profile),
    ]
    for node in workflow.nodes:
        if node.id != "export":
            node.provider_profile_id = TEXT_PROVIDER_ID
            node.model_settings.model = TEXT_MODEL
            node.model_settings.temperature = 0.3
            node.model_settings.max_tokens = 12_000
            node.model_settings.top_p = 0.8
            node.model_settings.timeout_seconds = 30
        if node.id == "cover":
            node.image_provider_profile_id = IMAGE_PROVIDER_ID
    response = client.post("/api/workflows", json=workflow.model_dump(mode="json"))
    assert response.status_code == 200, response.text


__all__ = [
    "IMAGE_PROVIDER_ID",
    "PROVIDER_STAGES",
    "TEXT_PROVIDER_ID",
    "configure_phase27_providers",
]

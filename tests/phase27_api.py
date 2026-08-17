from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.workflows.templates import (
    DEEPSEEK_FLASH_MODEL,
    DEEPSEEK_PRO_MODEL,
    DEEPSEEK_PROVIDER_ID,
    DEFAULT_IMAGE_MODEL,
    IMAGE_PROVIDER_ID as OFFICIAL_IMAGE_PROVIDER_ID,
)


PROVIDER_STAGES = ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
TEXT_PROVIDER_ID = DEEPSEEK_PROVIDER_ID
IMAGE_PROVIDER_ID = OFFICIAL_IMAGE_PROVIDER_ID
TEXT_MODEL = DEEPSEEK_PRO_MODEL
IMAGE_MODEL = DEFAULT_IMAGE_MODEL


def configure_phase27_providers(client: TestClient) -> None:
    text_profile = {
        "id": TEXT_PROVIDER_ID,
        "name": "Phase 27 Offline DeepSeek",
        "kind": "openai-compatible",
        "template_id": "deepseek-text",
        "base_url": "https://provider.invalid/v1",
        "api_key_env": "PHASE27_TEST_TEXT_API_KEY",
        "default_model": TEXT_MODEL,
        "model_options": [DEEPSEEK_PRO_MODEL, DEEPSEEK_FLASH_MODEL],
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
__all__ = [
    "IMAGE_PROVIDER_ID",
    "PROVIDER_STAGES",
    "TEXT_PROVIDER_ID",
    "configure_phase27_providers",
]

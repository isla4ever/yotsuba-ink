from __future__ import annotations

import asyncio
import base64
import binascii
import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import requests
from openai import AsyncOpenAI

from novel_workflow.providers.base import GeneratedImage, ImageProvider
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.openai_sdk import (
    create_openai_client,
    translate_openai_error,
)
from novel_workflow.providers.templates import (
    image_request_parameters,
    provider_template,
)

MAX_IMAGE_BYTES = 25 * 1024 * 1024


class OpenAICompatibleImageProvider(ImageProvider):
    name = "openai-compatible-image"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout_seconds: int = 180,
        template_id: str = "openai-compatible-image",
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.template_id = template_id
        self.template = provider_template(template_id, "openai-compatible-image")
        self.base_url = normalize_image_base_url(
            base_url,
            endpoint_path=self.template.image_endpoint_path,
        )
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client = client or create_openai_client(
            base_url=self.base_url,
            api_key=api_key,
            max_retries=self.template.max_retries,
        )

    @classmethod
    def from_env(cls) -> OpenAICompatibleImageProvider | None:
        import os

        base_url = os.environ.get("NOVEL_IMAGE_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("NOVEL_IMAGE_API_KEY") or os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("NOVEL_IMAGE_MODEL") or "gpt-image-2"
        if not base_url or not api_key:
            return None
        return cls(base_url, api_key, model)

    @classmethod
    def from_profile(
        cls,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 180,
        template_id: str = "openai-compatible-image",
    ) -> OpenAICompatibleImageProvider | None:
        if not base_url or not api_key or not model:
            return None
        return cls(base_url, api_key, model, timeout_seconds=timeout_seconds, template_id=template_id)

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        model = str(context.get("model") or self.model)
        size = str(context.get("size") or "1024x1536")
        quality = str(context.get("quality") or "medium")
        timeout_seconds = int(context.get("timeout_seconds") or self.timeout_seconds)
        idempotency_key = str(context.get("idempotency_key") or uuid4().hex)
        request = image_request_parameters(
            self.template,
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
        )
        headers = {"Idempotency-Key": idempotency_key}
        try:
            payload = await self._client.post(
                self.template.image_endpoint_path,
                cast_to=dict[str, Any],
                body=request,
                options={"headers": headers, "timeout": timeout_seconds},
            )
        except Exception as exc:
            raise translate_openai_error(exc, timeout_seconds=timeout_seconds) from exc
        try:
            item = payload[self.template.image_response_field][0]
        except (KeyError, IndexError, TypeError) as exc:
            field = self.template.image_response_field
            raise ProviderResponseError("response_shape_error", f"Image provider response is missing {field}[0]") from exc
        if not isinstance(item, dict):
            raise ProviderResponseError("response_shape_error", "Image provider data[0] is not an object")
        content, mime_type = await self._image_content(item)
        return GeneratedImage(
            content=content,
            mime_type=mime_type,
            provider_asset_id=str(item.get("id") or payload.get("id") or ""),
            revised_prompt=str(item.get("revised_prompt") or ""),
            usage={
                key: value
                for key, value in (payload.get("usage") or {}).items()
                if value is not None
            } if isinstance(payload.get("usage"), dict) else {},
        )

    async def probe(self) -> None:
        try:
            await self._client.get(
                self.template.models_endpoint_path,
                cast_to=dict[str, Any],
                options={"timeout": min(self.timeout_seconds, 30)},
            )
        except Exception as exc:
            raise translate_openai_error(exc, timeout_seconds=min(self.timeout_seconds, 30)) from exc

    async def _image_content(self, item: dict[str, Any]) -> tuple[bytes, str]:
        encoded = item.get("b64_json")
        if isinstance(encoded, str) and encoded.strip():
            try:
                content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ProviderResponseError("invalid_base64", "Image provider returned invalid base64 content") from exc
            return _bounded_content(content), str(item.get("media_type") or "")
        source_url = str(item.get("url") or "").strip()
        if not source_url:
            raise ProviderResponseError("empty_image", "Image provider returned neither image bytes nor a URL")
        _validate_remote_url(source_url)
        try:
            return await asyncio.to_thread(_download_remote_image, source_url, timeout_seconds)
        except requests.RequestException as exc:
            raise ProviderResponseError("asset_download_failed", "Unable to download generated image") from exc


def normalize_image_base_url(base_url: str, *, endpoint_path: str) -> str:
    normalized = base_url.rstrip("/")
    suffix = "/" + endpoint_path.strip("/")
    if suffix != "/" and normalized.endswith(suffix):
        return normalized[: -len(suffix)]
    return normalized


def _bounded_content(content: bytes) -> bytes:
    if not content:
        raise ProviderResponseError("empty_image", "Image provider returned empty image content")
    if len(content) > MAX_IMAGE_BYTES:
        raise ProviderResponseError("image_too_large", "Generated image exceeds the 25 MB limit")
    return content


def _validate_remote_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProviderResponseError("unsafe_asset_url", "Image asset URL must be a public HTTPS URL")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ProviderResponseError("asset_dns_failed", "Image asset host could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ProviderResponseError("unsafe_asset_url", "Image asset URL resolved to a non-public address")


def _download_remote_image(source_url: str, timeout_seconds: int) -> tuple[bytes, str]:
    with requests.get(
        source_url,
        headers={"Accept": "image/png,image/jpeg,image/webp"},
        timeout=timeout_seconds,
        stream=True,
        allow_redirects=False,
    ) as response:
        if 300 <= response.status_code < 400:
            raise ProviderResponseError("asset_redirect_rejected", "Image asset redirects are not accepted")
        response.raise_for_status()
        try:
            content_length = int(response.headers.get("content-length") or 0)
        except (TypeError, ValueError):
            content_length = 0
        if content_length > MAX_IMAGE_BYTES:
            raise ProviderResponseError("image_too_large", "Generated image exceeds the 25 MB limit")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > MAX_IMAGE_BYTES:
                raise ProviderResponseError("image_too_large", "Generated image exceeds the 25 MB limit")
        # Remote image URLs do not carry a provider-declared media type. CDN
        # Content-Type headers are advisory and may disagree with valid bytes;
        # the asset store derives the canonical MIME from the image structure.
        return _bounded_content(bytes(content)), ""

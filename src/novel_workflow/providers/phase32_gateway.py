"""Real text Provider adapter for the Phase 32 route runtime."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from novel_workflow.providers.base import ImageProvider, TextProvider
from novel_workflow.providers.errors import (
    ProviderResponseError,
    public_provider_response_diagnostic,
)
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.providers.openai_image import OpenAICompatibleImageProvider
from novel_workflow.providers.phase32_contract import (
    Phase32CoverImageRequest,
    Phase32ImageProviderExecutionSnapshot,
    Phase32ProviderRequest,
    Phase32ProviderResponse,
    Phase32StageProviderBindingSnapshot,
    Phase32WritebackProviderRequest,
)
from novel_workflow.providers.usage import (
    ensure_phase32_image_pricing_ready,
    ensure_phase32_text_pricing_ready,
    provider_usage_snapshot,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest


TextProviderFactory = Callable[
    [Phase32StageProviderBindingSnapshot, str],
    TextProvider,
]
ImageProviderFactory = Callable[
    [Phase32ImageProviderExecutionSnapshot, str],
    ImageProvider,
]


_RETURNED_CONTRACT_FAILURES = {
    "empty_content",
    "json_parse_failed",
    "output_truncated",
    "provider_feature_conflict",
    "response_json_error",
    "response_shape_error",
    "structured_empty_content",
    "unsupported_assistant_prefill",
}


class FrozenPhase32ProviderGateway:
    """Execute one frozen Phase 32 request without graph or retry behavior."""

    def __init__(
        self,
        secret_resolver: Callable[[str], str | None],
        *,
        text_provider_factory: TextProviderFactory | None = None,
        image_provider_factory: ImageProviderFactory | None = None,
    ) -> None:
        self.secret_resolver = secret_resolver
        self.text_provider_factory = text_provider_factory or _build_text_provider
        self.image_provider_factory = image_provider_factory or _build_image_provider

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding: Phase32StageProviderBindingSnapshot,
    ) -> Phase32ProviderResponse:
        _validate_request_binding(request, binding)
        self.ensure_ready(binding)
        secret = self.secret_resolver(binding.execution.provider_config.secret_ref)
        if not isinstance(secret, str) or not secret.strip():
            raise ProviderResponseError(
                "authentication_failed",
                "Frozen Phase 32 Provider secret is unavailable",
            )
        provider = self.text_provider_factory(binding, secret.strip())
        try:
            payload = await provider.generate_strict_structured(
                request.rendered_prompt,
                task_name=request.transport_task_name,
                context={"idempotency_key": request.operation_key},
                schema=request.output_schema,
            )
        except ProviderResponseError as exc:
            if exc.code not in _RETURNED_CONTRACT_FAILURES:
                raise
            return Phase32ProviderResponse(
                payload={},
                usage=provider_usage_snapshot(provider),
                diagnostic=_public_diagnostic(provider, code=exc.code),
            )
        if not isinstance(payload, dict):
            return Phase32ProviderResponse(
                payload={},
                usage=provider_usage_snapshot(provider),
                diagnostic={"code": "response_shape_error"},
            )
        return Phase32ProviderResponse(
            payload=payload,
            usage=provider_usage_snapshot(provider),
            diagnostic=_public_diagnostic(provider),
        )

    def ensure_ready(self, binding: Phase32StageProviderBindingSnapshot) -> None:
        """Reject untraceable pricing before secret resolution or network IO."""

        ensure_phase32_text_pricing_ready(binding.execution.pricing_snapshot)

    async def generate_cover_image(
        self,
        request: Phase32CoverImageRequest,
        *,
        binding: Phase32ImageProviderExecutionSnapshot,
    ):
        _validate_image_request_binding(request, binding)
        ensure_phase32_image_pricing_ready(binding.pricing_snapshot)
        secret = self.secret_resolver(binding.provider_config.secret_ref)
        if not isinstance(secret, str) or not secret.strip():
            raise ProviderResponseError(
                "authentication_failed",
                "Frozen Phase 32 image Provider secret is unavailable",
            )
        provider = self.image_provider_factory(binding, secret.strip())
        return await provider.generate_cover(
            request.prompt,
            context={
                "idempotency_key": request.operation_key,
                "model": request.model_id,
                "size": request.size,
                "quality": request.quality,
                "timeout_seconds": binding.timeout_seconds,
            },
        )

    async def generate_writeback(
        self,
        request: Phase32WritebackProviderRequest,
        *,
        binding: Phase32StageProviderBindingSnapshot,
    ) -> Phase32ProviderResponse:
        _validate_writeback_request_binding(request, binding)
        self.ensure_ready(binding)
        secret = self.secret_resolver(binding.execution.provider_config.secret_ref)
        if not isinstance(secret, str) or not secret.strip():
            raise ProviderResponseError(
                "authentication_failed",
                "Frozen Phase 32 Provider secret is unavailable",
            )
        provider = self.text_provider_factory(binding, secret.strip())
        try:
            payload = await provider.generate_strict_structured(
                request.rendered_prompt,
                task_name="phase32.writeback.evidence",
                context={"idempotency_key": request.operation_key},
                schema=request.output_schema,
            )
        except ProviderResponseError as exc:
            if exc.code not in _RETURNED_CONTRACT_FAILURES:
                raise
            return Phase32ProviderResponse(
                payload={},
                usage=provider_usage_snapshot(provider),
                diagnostic=_public_diagnostic(provider, code=exc.code),
            )
        if not isinstance(payload, dict):
            return Phase32ProviderResponse(
                payload={},
                usage=provider_usage_snapshot(provider),
                diagnostic={"code": "response_shape_error"},
            )
        return Phase32ProviderResponse(
            payload=payload,
            usage=provider_usage_snapshot(provider),
            diagnostic=_public_diagnostic(provider),
        )


def _validate_request_binding(
    request: Phase32ProviderRequest,
    binding: Phase32StageProviderBindingSnapshot,
) -> None:
    digest = canonical_digest(binding.model_dump(mode="json"))
    if digest != request.provider_binding_digest:
        raise ValueError("Phase 32 request does not match its frozen Provider binding")
    if (
        request.creation_route_id != binding.creation_route_id
        or request.stage_id != binding.stage_id
        or request.provider_task_kind != binding.task.provider_task_kind
        or request.artifact_kind != binding.task.artifact_kind
        or request.provider_profile_id != binding.execution.provider_profile_id
        or request.provider_template_id != binding.execution.provider_template_id
        or request.model_id != binding.execution.model_id
        or request.transport_task_name != binding.task.transport_task_name
        or request.output_schema_digest != binding.task.output_schema_digest
    ):
        raise ValueError("Phase 32 request identity does not match its Provider binding")


def _build_text_provider(
    binding: Phase32StageProviderBindingSnapshot,
    secret: str,
) -> TextProvider:
    execution = binding.execution
    settings = execution.model_settings
    return OpenAICompatibleTextProvider(
        base_url=execution.provider_config.base_url,
        api_key=secret,
        model=execution.model_id,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
        timeout_seconds=settings.timeout_seconds,
        template_id=execution.provider_template_id,
        template=execution.provider_template,
    )


def _validate_image_request_binding(
    request: Phase32CoverImageRequest,
    binding: Phase32ImageProviderExecutionSnapshot,
) -> None:
    if canonical_digest(binding.model_dump(mode="json")) != request.provider_binding_digest:
        raise ValueError("Phase 32 image request does not match its frozen Provider binding")
    if (
        request.provider_profile_id != binding.provider_profile_id
        or request.provider_template_id != binding.provider_template_id
        or request.model_id != binding.model_id
        or request.size != binding.size
        or request.quality != binding.quality
        or request.candidate_index > binding.candidate_count
    ):
        raise ValueError("Phase 32 image request identity does not match its Provider binding")


def _validate_writeback_request_binding(
    request: Phase32WritebackProviderRequest,
    binding: Phase32StageProviderBindingSnapshot,
) -> None:
    if canonical_digest(binding.model_dump(mode="json")) != request.provider_binding_digest:
        raise ValueError("Writeback request does not match its frozen Provider binding")
    execution = binding.execution
    if (
        request.creation_route_id != binding.creation_route_id
        or request.stage_id != binding.stage_id
        or request.provider_profile_id != execution.provider_profile_id
        or request.provider_template_id != execution.provider_template_id
        or request.model_id != execution.model_id
    ):
        raise ValueError("Writeback request identity does not match its Provider binding")


def _build_image_provider(
    binding: Phase32ImageProviderExecutionSnapshot,
    secret: str,
) -> ImageProvider:
    return OpenAICompatibleImageProvider(
        base_url=binding.provider_config.base_url,
        api_key=secret,
        model=binding.model_id,
        timeout_seconds=binding.timeout_seconds,
        template_id=binding.provider_template_id,
        template=binding.provider_template,
    )


def _public_diagnostic(provider: Any, *, code: str = "") -> dict[str, Any]:
    details = getattr(provider, "last_response_diagnostic", None)
    filtered = public_provider_response_diagnostic(
        ProviderResponseError(
            code or "http_error",
            "",
            diagnostic_details=(details if isinstance(details, dict) else {}),
        )
    )
    if code:
        filtered["code"] = code
    return filtered


__all__ = ["FrozenPhase32ProviderGateway"]

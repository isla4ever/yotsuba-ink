from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from novel_workflow.providers.base import TextProvider
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.openai_request import ensure_structured_prompt
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.providers.phase32_gateway import FrozenPhase32ProviderGateway
from novel_workflow.providers.usage import (
    Phase32ProviderPricingSnapshot,
    Phase32PricingReadinessError,
    freeze_phase32_pricing_snapshot,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32DriverError, Phase32RouteDriver
from novel_workflow.runtime.graph.phase32_provider_input import (
    compile_phase32_provider_request,
)
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from tests.test_phase32_driver import _brief_payload
from tests.test_phase32_route_graph import _definition


class CapturingPhase32TextProvider(TextProvider):
    name = "phase32-capturing"

    def __init__(
        self,
        *,
        payload: dict[str, Any] | None = None,
        failure_code: str = "",
    ) -> None:
        self.payload = payload or _brief_payload()
        self.failure_code = failure_code
        self.calls: list[dict[str, Any]] = []
        self.last_usage = {
            "prompt_tokens": 120,
            "completion_tokens": 80,
            "total_tokens": 200,
        }
        self.last_response_diagnostic = {
            "finish_reason": "stop",
            "response_chars": 640,
            "raw_body": "must-not-leak",
        }

    async def generate_text(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
    ) -> str:
        raise NotImplementedError

    async def generate_strict_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "prompt": prompt,
                "task_name": task_name,
                "context": context,
                "schema": schema,
            }
        )
        if self.failure_code:
            raise ProviderResponseError(
                self.failure_code,
                "private Provider response must not be persisted",
                diagnostic_details=self.last_response_diagnostic,
            )
        return self.payload


def _binding_and_request() -> tuple[
    Phase32StageProviderBindingSnapshot,
    Phase32ProviderRequest,
]:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    stage = definition.stage("brief")
    frozen = next(
        item for item in definition.provider_bindings_by_stage if item.stage_id == "brief"
    )
    binding = Phase32StageProviderBindingSnapshot.model_validate(frozen.binding.payload)
    request = compile_phase32_provider_request(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=stage,
        binding=binding,
        binding_digest=frozen.binding.payload_digest,
        operation_key=f"{definition.run_id}:brief:1:{'0' * 16}",
        context={
            "inputs": definition.inputs.payload,
            "scale_profile": definition.scale_profile.payload,
            "upstream_artifacts": {},
            "stage_attempt": 1,
        },
        direction="",
    )
    return binding, request


@pytest.mark.asyncio
async def test_gateway_calls_one_provider_with_exact_frozen_input_and_keeps_secret_out() -> None:
    binding, request = _binding_and_request()
    provider = CapturingPhase32TextProvider()
    resolved_refs: list[str] = []
    factory_inputs: list[tuple[Phase32StageProviderBindingSnapshot, str]] = []

    def resolve_secret(secret_ref: str) -> str:
        resolved_refs.append(secret_ref)
        return "provider-secret-value"

    def factory(
        frozen_binding: Phase32StageProviderBindingSnapshot,
        secret: str,
    ) -> TextProvider:
        factory_inputs.append((frozen_binding, secret))
        return provider

    gateway = FrozenPhase32ProviderGateway(resolve_secret, text_provider_factory=factory)
    response = await gateway.generate(request, binding=binding)

    assert len(provider.calls) == 1
    assert provider.calls[0] == {
        "prompt": request.rendered_prompt,
        "task_name": request.transport_task_name,
        "context": {"idempotency_key": request.operation_key},
        "schema": request.output_schema,
    }
    assert resolved_refs == [binding.execution.provider_config.secret_ref]
    assert factory_inputs == [(binding, "provider-secret-value")]
    assert response.payload == _brief_payload()
    assert response.usage["total_tokens"] == 200
    serialized = json.dumps(
        {"request": request.model_dump(mode="json"), "response": response.model_dump(mode="json")},
        ensure_ascii=False,
    )
    assert "provider-secret-value" not in serialized
    assert "must-not-leak" not in serialized


@pytest.mark.asyncio
async def test_gateway_rejects_binding_digest_drift_before_provider_creation() -> None:
    binding, request = _binding_and_request()
    provider = CapturingPhase32TextProvider()
    factory_calls = 0

    def factory(_binding: Phase32StageProviderBindingSnapshot, _secret: str) -> TextProvider:
        nonlocal factory_calls
        factory_calls += 1
        return provider

    gateway = FrozenPhase32ProviderGateway(
        lambda _secret_ref: "provider-secret-value",
        text_provider_factory=factory,
    )
    drifted = binding.model_copy(update={"workflow_id": "workflow-drifted"})

    with pytest.raises(ValueError, match="frozen Provider binding"):
        await gateway.generate(request, binding=drifted)

    assert factory_calls == 0
    assert provider.calls == []


@pytest.mark.asyncio
async def test_gateway_rejects_unknown_pricing_before_secret_or_provider_creation() -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    stage = definition.stage("brief")
    binding, _ = _binding_and_request()
    unavailable = Phase32ProviderPricingSnapshot.model_validate(
        freeze_phase32_pricing_snapshot(
            provider_profile_id=binding.execution.provider_profile_id,
            provider_template_id=binding.execution.provider_template_id,
            model_id=binding.execution.model_id,
        )
    )
    blocked_binding = binding.model_copy(
        update={
            "execution": binding.execution.model_copy(
                update={"pricing_snapshot": unavailable}
            )
        }
    )
    blocked_request = compile_phase32_provider_request(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=stage,
        binding=blocked_binding,
        binding_digest=canonical_digest(blocked_binding.model_dump(mode="json")),
        operation_key=f"{definition.run_id}:brief:1:{'1' * 16}",
        context={
            "inputs": definition.inputs.payload,
            "scale_profile": definition.scale_profile.payload,
            "upstream_artifacts": {},
            "stage_attempt": 1,
        },
        direction="",
    )
    secret_calls = 0
    factory_calls = 0

    def resolve_secret(_secret_ref: str) -> str:
        nonlocal secret_calls
        secret_calls += 1
        return "provider-secret-value"

    def factory(_binding: Phase32StageProviderBindingSnapshot, _secret: str) -> TextProvider:
        nonlocal factory_calls
        factory_calls += 1
        return CapturingPhase32TextProvider()

    gateway = FrozenPhase32ProviderGateway(
        resolve_secret,
        text_provider_factory=factory,
    )

    with pytest.raises(Phase32PricingReadinessError) as exc:
        await gateway.generate(blocked_request, binding=blocked_binding)

    assert exc.value.code == "phase32_provider_pricing_not_ready"
    assert secret_calls == 0
    assert factory_calls == 0


@pytest.mark.asyncio
async def test_driver_runs_gateway_readiness_before_snapshot_or_receipt(
    tmp_path: Path,
) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)

    class BlockingGateway:
        calls = 0

        def ensure_ready(self, _binding: Phase32StageProviderBindingSnapshot) -> None:
            raise Phase32PricingReadinessError(("pricing_unavailable",))

        async def generate(self, request, *, binding):
            self.calls += 1
            raise AssertionError("readiness must block before Provider IO")

    gateway = BlockingGateway()
    driver = Phase32RouteDriver(Phase32ArtifactStore(tmp_path), gateway)

    with pytest.raises(Phase32PricingReadinessError):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )

    assert gateway.calls == 0
    assert driver.provider_inputs.list(definition.run_id) == []
    assert driver.provider_operations.list(definition.run_id) == []


def test_frozen_structured_prompt_is_idempotent() -> None:
    binding, request = _binding_and_request()
    from novel_workflow.providers.model_capabilities import resolve_request_policy

    policy = resolve_request_policy(
        binding.execution.provider_template,
        model=binding.execution.model_id,
        task_name=binding.task.transport_task_name,
    )
    second_pass = ensure_structured_prompt(
        request.rendered_prompt,
        task_name=request.transport_task_name,
        schema=request.output_schema,
        policy=policy,
    )

    assert second_pass == request.rendered_prompt


@pytest.mark.asyncio
async def test_returned_json_parse_failure_is_contract_rejected_without_retry(
    tmp_path: Path,
) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    provider = CapturingPhase32TextProvider(failure_code="json_parse_failed")
    gateway = FrozenPhase32ProviderGateway(
        lambda _secret_ref: "provider-secret-value",
        text_provider_factory=lambda _binding, _secret: provider,
    )
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path),
        gateway,
        provider_max_transport_attempts=1,
    )
    state = initial_route_run_state(definition)
    stage = definition.stage("brief")

    with pytest.raises(Phase32DriverError, match="Artifact payload"):
        await driver.generate_stage(definition=definition, state=state, stage=stage)

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"
    assert receipt.transport_attempts == 1
    assert receipt.diagnostic["code"] == "artifact_contract_rejected"
    assert receipt.diagnostic["provider_code"] == "json_parse_failed"
    assert "raw_body" not in receipt.diagnostic
    assert len(provider.calls) == 1

    with pytest.raises(Phase32DriverError, match="Provider contract was rejected"):
        await driver.generate_stage(definition=definition, state=state, stage=stage)

    assert len(provider.calls) == 1

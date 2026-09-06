from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_workflow.providers.frozen_contract import prompt_digest, schema_digest
from novel_workflow.storage.phase32_provider_input_store import (
    Phase32ProviderInputSnapshotConflict,
    Phase32ProviderInputStore,
)
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceiptConflict,
    Phase32ProviderOperationStore,
)


def _request(*, direction: str = "") -> dict[str, object]:
    rendered_prompt = "生成剧本样片 Brief，只返回 JSON 对象。"
    output_schema = {
        "type": "object",
        "properties": {"sample_type": {"type": "string"}},
        "required": ["sample_type"],
    }
    return {
        "operation_key": "run-1:brief:1:0000000000000000",
        "run_id": "run-1",
        "creation_route_id": "screenplay_sample",
        "route_revision": "r1",
        "stage_id": "brief",
        "provider_task_kind": "screenplay_brief",
        "artifact_kind": "screenplay_brief",
        "provider_profile_id": "fake",
        "provider_template_id": "fake-template",
        "model_id": "fake-model",
        "provider_binding_digest": "a" * 64,
        "transport_task_name": "brief",
        "rendered_prompt": rendered_prompt,
        "rendered_prompt_digest": prompt_digest(rendered_prompt),
        "output_schema": output_schema,
        "output_schema_digest": schema_digest(output_schema),
        "context": {"inputs": {"creative_intent": "档案调查"}, "stage_attempt": 1},
        "direction": direction,
    }


def test_phase32_input_snapshot_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    store = Phase32ProviderInputStore(tmp_path / "provider-inputs")
    request = _request()

    first = store.write(
        run_id="run-1",
        operation_key=request["operation_key"],
        stage_id="brief",
        request=request,
    )
    second = store.write(
        run_id="run-1",
        operation_key=request["operation_key"],
        stage_id="brief",
        request=dict(request),
    )

    assert second == first
    assert first.provider_input_ref.endswith(first.request_signature)
    assert store.read("run-1", first.provider_input_ref) == first
    assert len(store.list("run-1")) == 1
    assert first.request["rendered_prompt"] == request["rendered_prompt"]
    assert first.request["rendered_prompt_digest"] == request["rendered_prompt_digest"]
    assert first.request["output_schema"] == request["output_schema"]
    assert first.request["output_schema_digest"] == request["output_schema_digest"]

    path = tmp_path / "provider-inputs" / "run-1" / f"{first.provider_input_ref}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["request"]["direction"] = "篡改"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Phase32ProviderInputSnapshotConflict):
        store.read("run-1", first.provider_input_ref)


@pytest.mark.parametrize(
    "field",
    ("api_key", "authorization", "headers", "secret", "access_token"),
)
def test_phase32_input_snapshot_rejects_secret_material(tmp_path: Path, field: str) -> None:
    store = Phase32ProviderInputStore(tmp_path / "provider-inputs")
    request = _request()
    request[field] = "do-not-persist"

    with pytest.raises(ValueError, match="forbidden secret or header"):
        store.write(
            run_id="run-1",
            operation_key=request["operation_key"],
            stage_id="brief",
            request=request,
        )


def test_receipt_read_requires_a_matching_input_snapshot(tmp_path: Path) -> None:
    inputs = Phase32ProviderInputStore(tmp_path / "provider-inputs")
    request = _request()
    snapshot = inputs.write(
        run_id="run-1",
        operation_key=request["operation_key"],
        stage_id="brief",
        request=request,
    )
    operations = Phase32ProviderOperationStore(
        tmp_path / "provider-operations",
        provider_inputs=inputs,
    )
    pending = operations.begin(
        run_id="run-1",
        operation_key=request["operation_key"],
        stage_id="brief",
        request_signature=snapshot.request_signature,
        provider_input_ref=snapshot.provider_input_ref,
    )
    assert pending.provider_input_ref == snapshot.provider_input_ref

    path = tmp_path / "provider-inputs" / "run-1" / f"{snapshot.provider_input_ref}.json"
    path.unlink()
    with pytest.raises(Phase32ProviderOperationReceiptConflict, match="input snapshot"):
        operations.read("run-1", request["operation_key"])


def test_receipt_rejects_snapshot_from_a_different_request(tmp_path: Path) -> None:
    inputs = Phase32ProviderInputStore(tmp_path / "provider-inputs")
    first = _request()
    second = _request(direction="只强化证据链")
    first_snapshot = inputs.write(
        run_id="run-1",
        operation_key=first["operation_key"],
        stage_id="brief",
        request=first,
    )
    second_snapshot = inputs.write(
        run_id="run-1",
        operation_key=second["operation_key"],
        stage_id="brief",
        request=second,
    )
    operations = Phase32ProviderOperationStore(
        tmp_path / "provider-operations",
        provider_inputs=inputs,
    )
    operations.begin(
        run_id="run-1",
        operation_key=first["operation_key"],
        stage_id="brief",
        request_signature=first_snapshot.request_signature,
        provider_input_ref=first_snapshot.provider_input_ref,
    )

    with pytest.raises(Phase32ProviderOperationReceiptConflict, match="different frozen request"):
        operations.begin(
            run_id="run-1",
            operation_key=first["operation_key"],
            stage_id="brief",
            request_signature=second_snapshot.request_signature,
            provider_input_ref=second_snapshot.provider_input_ref,
        )

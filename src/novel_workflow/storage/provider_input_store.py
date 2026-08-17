from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class ProviderOutputContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["structured_json", "plain_text", "image"]
    json_schema_contract: dict[str, Any] | None = None
    schema_digest: str = ""
    structured_mode: str = ""
    plain_text_contract: str = ""
    image_contract: dict[str, Any] = Field(default_factory=dict)


class ProviderInputPayload(BaseModel):
    """The secret-free, model-visible input compiled before one Provider call."""

    model_config = ConfigDict(extra="forbid")

    stage_id: str = Field(min_length=1, max_length=120)
    task_name: str = Field(min_length=1, max_length=160)
    attempt: int = Field(ge=1)
    chapter_id: str = ""
    chapter_version_id: str = ""
    provider_binding: dict[str, Any]
    prompt_template_id: str
    prompt_digest: str
    rendered_prompt: str = Field(min_length=1)
    structured_context: dict[str, Any]
    output_contract: ProviderOutputContract

    @model_validator(mode="after")
    def reject_secret_material(self) -> "ProviderInputPayload":
        _assert_secret_free(self.provider_binding, ("provider_binding",))
        return self


class ProviderInputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    operation_key: str
    snapshot_ref: str = Field(pattern=r"^provider-input-[a-f0-9]{64}$")
    request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    input: ProviderInputPayload
    created_at: str


class ProviderInputStore:
    """Content-addressed Provider inputs kept outside LangGraph state."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def signature(
        self,
        *,
        run_id: str,
        operation_key: str,
        input: ProviderInputPayload,
    ) -> str:
        require_safe_id(run_id, label="run_id")
        if not operation_key.strip():
            raise ValueError("Provider operation key is required")
        return _signature(run_id, operation_key, input)

    def write(
        self,
        *,
        run_id: str,
        operation_key: str,
        input: ProviderInputPayload,
    ) -> ProviderInputRecord:
        signature = self.signature(
            run_id=run_id,
            operation_key=operation_key,
            input=input,
        )
        snapshot_ref = f"provider-input-{signature}"
        record = ProviderInputRecord(
            run_id=run_id,
            operation_key=operation_key,
            snapshot_ref=snapshot_ref,
            request_signature=signature,
            input=input,
            created_at=_now(),
        )
        path = self._path(run_id, snapshot_ref)
        with self._lock:
            if path.exists():
                existing = ProviderInputRecord.model_validate(read_json(path))
                _validate_identity(existing)
                if existing.model_copy(update={"created_at": record.created_at}) != record:
                    raise ValueError("Provider input snapshot is immutable")
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, snapshot_ref: str) -> ProviderInputRecord:
        record = ProviderInputRecord.model_validate(
            read_json(self._path(run_id, snapshot_ref))
        )
        _validate_identity(record)
        if record.run_id != run_id or record.snapshot_ref != snapshot_ref:
            raise ValueError("Provider input snapshot identity mismatch")
        return record

    def list(self, run_id: str) -> list[ProviderInputRecord]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id
        if not directory.exists():
            return []
        return sorted(
            (self.read(run_id, path.stem) for path in directory.glob("*.json")),
            key=lambda item: item.created_at,
        )

    def _path(self, run_id: str, snapshot_ref: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(snapshot_ref, label="snapshot_ref")
        return self.root / run_id / f"{snapshot_ref}.json"


def _signature(
    run_id: str,
    operation_key: str,
    input: ProviderInputPayload,
) -> str:
    encoded = json.dumps(
        {
            "run_id": run_id,
            "operation_key": operation_key,
            "input": input.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_identity(record: ProviderInputRecord) -> None:
    expected = _signature(record.run_id, record.operation_key, record.input)
    if record.request_signature != expected:
        raise ValueError("Provider input signature does not match its content")
    if record.snapshot_ref != f"provider-input-{expected}":
        raise ValueError("Provider input reference does not match its content")


def _assert_secret_free(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            if (
                normalized
                in {
                    "api_key",
                    "authorization",
                    "header",
                    "headers",
                    "secret",
                    "secret_ref",
                }
                or normalized.endswith("_header")
                or normalized.endswith("_headers")
            ):
                raise ValueError(
                    "Provider input snapshot contains forbidden secret or header field: "
                    f"{'.'.join((*path, key))}"
                )
            _assert_secret_free(item, (*path, key))
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_secret_free(item, (*path, str(index)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "ProviderInputPayload",
    "ProviderInputRecord",
    "ProviderInputStore",
    "ProviderOutputContract",
]

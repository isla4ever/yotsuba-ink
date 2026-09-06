from __future__ import annotations

import hashlib
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from novel_workflow.providers.base import GeneratedImage
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.storage.image_assets import inspect_image_asset


class CoverAssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    run_id: str
    operation_key: str
    candidate_index: int = Field(ge=1)
    generation_attempt: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    mime_type: str
    extension: str
    width: int = Field(ge=256)
    height: int = Field(ge=256)
    size_bytes: int = Field(gt=0)
    provider_asset_id: str = ""
    revised_prompt: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    created_at: str

    @field_validator("usage")
    @classmethod
    def validate_usage(cls, value: dict[str, int]) -> dict[str, int]:
        if any(
            not isinstance(key, str)
            or not key.strip()
            or isinstance(amount, bool)
            or not isinstance(amount, int)
            or amount < 0
            for key, amount in value.items()
        ):
            raise ValueError("Cover asset usage must contain non-negative integer values")
        return value


class CoverAssetStore:
    """Immutable cover bytes keyed by their content digest and Provider operation."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save(
        self,
        run_id: str,
        *,
        operation_key: str,
        candidate_index: int,
        generation_attempt: int,
        image: GeneratedImage,
        expected_ratio: float | None = None,
    ) -> CoverAssetRecord:
        require_safe_id(run_id, label="run_id")
        if candidate_index < 1:
            raise ValueError("Cover candidate index must be positive")
        if generation_attempt < 1:
            raise ValueError("Cover generation attempt must be positive")
        info = inspect_image_asset(image.content, image.mime_type)
        if expected_ratio and abs((info.width / info.height) - expected_ratio) > 0.04:
            raise ValueError("Cover asset aspect ratio does not match the frozen binding")
        digest = hashlib.sha256(image.content).hexdigest()
        asset_id = f"cover-{digest[:24]}"
        record = CoverAssetRecord(
            asset_id=asset_id,
            run_id=run_id,
            operation_key=operation_key,
            candidate_index=candidate_index,
            generation_attempt=generation_attempt,
            sha256=digest,
            mime_type=info.mime_type,
            extension=info.extension,
            width=info.width,
            height=info.height,
            size_bytes=len(image.content),
            provider_asset_id=image.provider_asset_id,
            revised_prompt=image.revised_prompt,
            usage={
                str(key): int(value)
                for key, value in image.usage.items()
                if isinstance(key, str)
                and key.strip()
                and not isinstance(value, bool)
                and isinstance(value, int)
                and value >= 0
            },
            created_at=_now(),
        )
        with self._lock:
            operation_path = self._operation_path(run_id, operation_key)
            if operation_path.exists():
                existing = CoverAssetRecord.model_validate(read_json(operation_path))
                if (
                    existing.sha256 != digest
                    or existing.candidate_index != candidate_index
                    or existing.generation_attempt != generation_attempt
                ):
                    raise ValueError("Cover operation is already bound to a different asset")
                self._validate_content(existing)
                return existing
            content_path = self._content_path(record)
            record_path = self._record_path(run_id, asset_id)
            if record_path.exists():
                existing = CoverAssetRecord.model_validate(read_json(record_path))
                if existing.sha256 != digest:
                    raise ValueError("Cover asset id collides with different content")
                self._validate_content(existing)
                atomic_write_json(operation_path, existing.model_dump(mode="json"))
                return existing
            if content_path.exists() and hashlib.sha256(content_path.read_bytes()).hexdigest() != digest:
                raise ValueError("Cover asset id collides with different content")
            if not content_path.exists():
                self._atomic_write_bytes(content_path, image.content)
            atomic_write_json(record_path, record.model_dump(mode="json"))
            atomic_write_json(operation_path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, asset_id: str) -> CoverAssetRecord:
        require_safe_id(run_id, label="run_id")
        require_safe_id(asset_id, label="asset_id")
        record = CoverAssetRecord.model_validate(read_json(self._record_path(run_id, asset_id)))
        self._validate_content(record)
        return record

    def find_by_operation(
        self,
        run_id: str,
        operation_key: str,
    ) -> CoverAssetRecord | None:
        """Recover bytes written before the Provider receipt transition completed."""

        require_safe_id(run_id, label="run_id")
        if not operation_key.strip():
            raise ValueError("Cover operation key is required")
        path = self._operation_path(run_id, operation_key)
        if not path.exists():
            return None
        record = CoverAssetRecord.model_validate(read_json(path))
        if record.run_id != run_id or record.operation_key != operation_key:
            raise ValueError("Cover operation receipt does not match its storage identity")
        self._validate_content(record)
        return record

    def content(self, run_id: str, asset_id: str) -> tuple[CoverAssetRecord, bytes]:
        record = self.read(run_id, asset_id)
        return record, self._content_path(record).read_bytes()

    def list(
        self,
        run_id: str,
        *,
        generation_attempt: int | None = None,
    ) -> list[CoverAssetRecord]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id / "records"
        if not directory.exists():
            return []
        records = [
            CoverAssetRecord.model_validate(read_json(path))
            for path in directory.glob("cover-*.json")
        ]
        if generation_attempt is not None:
            records = [
                record for record in records if record.generation_attempt == generation_attempt
            ]
        for record in records:
            self._validate_content(record)
        return sorted(records, key=lambda item: (item.candidate_index, item.asset_id))

    def copy_run(self, source_run_id: str, target_run_id: str) -> None:
        for record in self.list(source_run_id):
            _, content = self.content(source_run_id, record.asset_id)
            cloned = self.save(
                target_run_id,
                operation_key=record.operation_key.replace(source_run_id, target_run_id, 1),
                candidate_index=record.candidate_index,
                generation_attempt=record.generation_attempt,
                image=GeneratedImage(
                    content=content,
                    mime_type=record.mime_type,
                    provider_asset_id=record.provider_asset_id,
                    revised_prompt=record.revised_prompt,
                    usage=record.usage,
                ),
                expected_ratio=record.width / record.height,
            )
            if cloned.asset_id != record.asset_id:
                raise ValueError("Cover asset identity changed while creating branch")

    def _validate_content(self, record: CoverAssetRecord) -> None:
        content = self._content_path(record).read_bytes()
        if len(content) != record.size_bytes or hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError("Stored cover content does not match its immutable receipt")
        inspect_image_asset(content, record.mime_type)

    def _record_path(self, run_id: str, asset_id: str) -> Path:
        return self.root / run_id / "records" / f"{asset_id}.json"

    def _operation_path(self, run_id: str, operation_key: str) -> Path:
        digest = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()
        return self.root / run_id / "operations" / f"{digest}.json"

    def _content_path(self, record: CoverAssetRecord) -> Path:
        return self.root / record.run_id / "files" / f"{record.asset_id}.{record.extension}"

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            temp.write_bytes(content)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["CoverAssetRecord", "CoverAssetStore"]

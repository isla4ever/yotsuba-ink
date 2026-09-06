from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import (
    ChapterArtifact,
    ExportArtifact,
    ExportMetadata,
)
from novel_workflow.storage.artifact_store import ArtifactRecord
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.storage.cover_asset_store import CoverAssetRecord
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    BookDeliveryArtifact,
    ChapterArtifact as Phase32ChapterArtifact,
    ScreenplayDraftArtifact,
    ScriptDeliveryArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.storage.book_delivery_renderers import (
    BookDeliveryFormat,
    render_book_delivery,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactRecord
from novel_workflow.storage.script_delivery_renderers import (
    ScriptDeliveryFormat,
    render_script_delivery,
)


class ExportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: str
    run_id: str
    artifact_id: str
    artifact_signature: str = Field(min_length=64, max_length=64)
    format: Literal["md", "json", "zip"]
    chapter_version_ids: list[str]
    cover_asset_id: str = ""
    metadata: ExportMetadata
    filename: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: str


class ScriptDeliveryRecord(BaseModel):
    """Immutable file receipt for one Phase 32 screenplay delivery format."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    export_id: str
    run_id: str
    artifact_ref: str
    artifact_digest: str = Field(min_length=64, max_length=64)
    format: ScriptDeliveryFormat
    scene_refs: tuple[str, ...]
    scene_version_refs: tuple[str, ...]
    title: str
    author: str
    version_note: str
    filename: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: str


class BookDeliveryChapterReceipt(BaseModel):
    """Deterministic manifest row projected from one committed text version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=1)
    chapter_ref: str
    version_ref: str
    title: str
    unit_kind: Literal["section", "chapter"]
    volume_ref: str = ""
    character_count: int = Field(ge=1)


class BookDeliveryRecord(BaseModel):
    """Immutable file receipt for one Phase 32 novel delivery format."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    export_id: str
    run_id: str
    creation_route_id: Literal["short_novel", "long_novel"]
    artifact_ref: str
    artifact_digest: str = Field(min_length=64, max_length=64)
    format: BookDeliveryFormat
    chapter_refs: tuple[str, ...]
    chapter_version_refs: tuple[str, ...]
    chapter_manifest: tuple[BookDeliveryChapterReceipt, ...]
    volume_refs: tuple[str, ...]
    cover_asset_ref: str
    cover_sha256: str = Field(min_length=64, max_length=64)
    title: str
    author: str
    version_note: str
    filename: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: str


class ExportStore:
    """Immutable delivery files materialized from one committed Export Artifact."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def materialize(
        self,
        run_id: str,
        artifact_record: ArtifactRecord,
        chapters: list[ChapterArtifact],
        *,
        cover_asset: tuple[CoverAssetRecord, bytes] | None,
    ) -> ExportRecord:
        require_safe_id(run_id, label="run_id")
        if artifact_record.run_id != run_id or artifact_record.stage_id != "export":
            raise ValueError("Export materialization requires this Run's committed Export Artifact")
        artifact = ExportArtifact.model_validate(artifact_record.payload)
        versions = [chapter.version_id for chapter in chapters]
        if versions != artifact.chapter_version_ids:
            raise ValueError("Export chapter versions do not match the committed Artifact")
        if any(chapter.author_status != "accepted" for chapter in chapters):
            raise ValueError("Export only accepts committed chapter versions")
        if artifact.cover_asset_id:
            if cover_asset is None or cover_asset[0].asset_id != artifact.cover_asset_id:
                raise ValueError("Export cover bytes do not match the committed Artifact")
        elif cover_asset is not None:
            raise ValueError("Export received cover bytes without an Artifact reference")

        content, filename, media_type = _render_export(
            artifact,
            chapters,
            cover_asset=cover_asset,
        )
        digest = hashlib.sha256(content).hexdigest()
        export_id = f"export-{artifact_record.signature[:24]}"
        record = ExportRecord(
            export_id=export_id,
            run_id=run_id,
            artifact_id=artifact_record.artifact_id,
            artifact_signature=artifact_record.signature,
            format=artifact.format,
            chapter_version_ids=list(artifact.chapter_version_ids),
            cover_asset_id=artifact.cover_asset_id,
            metadata=artifact.metadata,
            filename=filename,
            media_type=media_type,
            size_bytes=len(content),
            sha256=digest,
            created_at=_now(),
        )
        with self._lock:
            record_path = self._record_path(run_id, export_id)
            if record_path.exists():
                existing = ExportRecord.model_validate(read_json(record_path))
                if existing != record.model_copy(update={"created_at": existing.created_at}):
                    raise ValueError("Export id was reused with different content")
                self._validate_content(existing)
                return existing
            self._atomic_write_bytes(self._content_path(run_id, export_id), content)
            atomic_write_json(record_path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, export_id: str) -> ExportRecord:
        record = ExportRecord.model_validate(read_json(self._record_path(run_id, export_id)))
        self._validate_content(record)
        return record

    def list(self, run_id: str) -> list[ExportRecord]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id / "records"
        if not directory.exists():
            return []
        records = [
            ExportRecord.model_validate(read_json(path))
            for path in directory.glob("*.json")
        ]
        return sorted(records, key=lambda item: (item.created_at, item.export_id), reverse=True)

    def content(self, run_id: str, export_id: str) -> tuple[ExportRecord, bytes]:
        record = self.read(run_id, export_id)
        return record, self._content_path(run_id, export_id).read_bytes()

    def materialize_script_delivery(
        self,
        run_id: str,
        artifact_record: Phase32ArtifactRecord,
        scene_records: list[Phase32ArtifactRecord],
    ) -> list[ScriptDeliveryRecord]:
        """Materialize every format frozen into one committed script delivery."""

        require_safe_id(run_id, label="run_id")
        if (
            artifact_record.run_id != run_id
            or artifact_record.creation_route_id != "screenplay_sample"
            or artifact_record.stage_id != "export"
            or artifact_record.artifact_kind != "script_delivery"
            or artifact_record.status != "committed"
        ):
            raise ValueError(
                "Script delivery materialization requires this Run's committed Export Artifact"
            )
        artifact = ScriptDeliveryArtifact.model_validate(artifact_record.payload)
        if tuple(record.artifact_ref for record in scene_records) != artifact.scene_version_refs:
            raise ValueError("Script delivery Scene versions are missing or out of frozen order")

        scenes: list[ScreenplayDraftArtifact] = []
        for scene_ref, version_ref, record in zip(
            artifact.scene_refs,
            artifact.scene_version_refs,
            scene_records,
            strict=True,
        ):
            if (
                record.run_id != run_id
                or record.creation_route_id != "screenplay_sample"
                or record.stage_id != "script"
                or record.artifact_kind != "screenplay_draft"
                or record.status != "committed"
                or record.artifact_ref != version_ref
            ):
                raise ValueError("Script delivery only accepts committed Scene versions")
            scene = ScreenplayDraftArtifact.model_validate(record.payload)
            if scene.scene_ref != scene_ref:
                raise ValueError("Script delivery Scene identity does not match its frozen order")
            scenes.append(scene)

        records: list[ScriptDeliveryRecord] = []
        for delivery_format in artifact.formats:
            content, filename, media_type = render_script_delivery(
                artifact,
                scenes,
                delivery_format,
            )
            export_id = f"script-export-{artifact_record.payload_digest[:20]}-{delivery_format}"
            record = ScriptDeliveryRecord(
                export_id=export_id,
                run_id=run_id,
                artifact_ref=artifact_record.artifact_ref,
                artifact_digest=artifact_record.payload_digest,
                format=delivery_format,
                scene_refs=artifact.scene_refs,
                scene_version_refs=artifact.scene_version_refs,
                title=artifact.title,
                author=artifact.author,
                version_note=artifact.version_note,
                filename=filename,
                media_type=media_type,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                created_at=_now(),
            )
            with self._lock:
                record_path = self._script_record_path(run_id, export_id)
                if record_path.exists():
                    existing = ScriptDeliveryRecord.model_validate(read_json(record_path))
                    if existing != record.model_copy(update={"created_at": existing.created_at}):
                        raise ValueError("Script delivery id was reused with different content")
                    self._validate_script_content(existing)
                    records.append(existing)
                    continue
                self._atomic_write_bytes(
                    self._script_content_path(run_id, export_id),
                    content,
                )
                atomic_write_json(record_path, record.model_dump(mode="json"))
            records.append(record)
        return records

    def read_script_delivery(self, run_id: str, export_id: str) -> ScriptDeliveryRecord:
        record = ScriptDeliveryRecord.model_validate(
            read_json(self._script_record_path(run_id, export_id))
        )
        if record.run_id != run_id or record.export_id != export_id:
            raise ValueError("Script delivery storage identity does not match its receipt")
        self._validate_script_content(record)
        return record

    def list_script_delivery(self, run_id: str) -> list[ScriptDeliveryRecord]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id / "script-records"
        if not directory.exists():
            return []
        records = [
            self.read_script_delivery(run_id, path.stem)
            for path in directory.glob("*.json")
        ]
        return sorted(records, key=lambda item: (item.created_at, item.export_id))

    def script_delivery_content(
        self,
        run_id: str,
        export_id: str,
    ) -> tuple[ScriptDeliveryRecord, bytes]:
        record = self.read_script_delivery(run_id, export_id)
        return record, self._script_content_path(run_id, export_id).read_bytes()

    def materialize_book_delivery(
        self,
        run_id: str,
        artifact_record: Phase32ArtifactRecord,
        chapter_records: list[Phase32ArtifactRecord],
        *,
        cover_asset: tuple[CoverAssetRecord, bytes],
    ) -> list[BookDeliveryRecord]:
        """Materialize every frozen novel format without invoking a Provider."""

        require_safe_id(run_id, label="run_id")
        if (
            artifact_record.run_id != run_id
            or artifact_record.creation_route_id not in {"short_novel", "long_novel"}
            or artifact_record.stage_id != "export"
            or artifact_record.artifact_kind != "book_delivery"
            or artifact_record.status != "committed"
        ):
            raise ValueError(
                "Book delivery materialization requires this Run's committed Export Artifact"
            )
        artifact = BookDeliveryArtifact.model_validate(artifact_record.payload)
        if tuple(record.artifact_ref for record in chapter_records) != artifact.chapter_version_refs:
            raise ValueError("Book delivery chapter versions are missing or out of frozen order")

        chapters: list[ShortProseUnitArtifact | Phase32ChapterArtifact] = []
        chapter_manifest: list[BookDeliveryChapterReceipt] = []
        expected_kind = (
            "short_prose_unit"
            if artifact_record.creation_route_id == "short_novel"
            else "chapter"
        )
        for ordinal, (chapter_ref, version_ref, record) in enumerate(
            zip(
                artifact.chapter_refs,
                artifact.chapter_version_refs,
                chapter_records,
                strict=True,
            ),
            start=1,
        ):
            if (
                record.run_id != run_id
                or record.creation_route_id != artifact_record.creation_route_id
                or record.stage_id != "text"
                or record.artifact_kind != expected_kind
                or record.status != "committed"
                or record.artifact_ref != version_ref
            ):
                raise ValueError("Book delivery only accepts committed text versions")
            if artifact_record.creation_route_id == "short_novel":
                chapter = ShortProseUnitArtifact.model_validate(record.payload)
                actual_ref = chapter.unit_ref
            else:
                chapter = Phase32ChapterArtifact.model_validate(record.payload)
                actual_ref = chapter.chapter_ref
                if chapter.volume_ref not in artifact.volume_refs:
                    raise ValueError("Book delivery chapter references an unknown frozen volume")
            if actual_ref != chapter_ref:
                raise ValueError("Book delivery chapter identity does not match its frozen order")
            chapters.append(chapter)
            chapter_manifest.append(
                BookDeliveryChapterReceipt(
                    ordinal=ordinal,
                    chapter_ref=chapter_ref,
                    version_ref=version_ref,
                    title=chapter.title,
                    unit_kind=(
                        chapter.unit_kind
                        if isinstance(chapter, ShortProseUnitArtifact)
                        else "chapter"
                    ),
                    volume_ref=(
                        chapter.volume_ref
                        if isinstance(chapter, Phase32ChapterArtifact)
                        else ""
                    ),
                    character_count=len("".join(chapter.content.split())),
                )
            )

        cover, cover_bytes = cover_asset
        if (
            cover.run_id != run_id
            or cover.asset_id != artifact.cover_asset_ref
            or len(cover_bytes) != cover.size_bytes
            or hashlib.sha256(cover_bytes).hexdigest() != cover.sha256
        ):
            raise ValueError("Book delivery cover bytes do not match the committed Artifact")

        records: list[BookDeliveryRecord] = []
        for delivery_format in artifact.formats:
            content, filename, media_type = render_book_delivery(
                artifact,
                chapters,
                cover_asset,
                delivery_format,
            )
            export_id = f"book-export-{artifact_record.payload_digest[:20]}-{delivery_format}"
            record = BookDeliveryRecord(
                export_id=export_id,
                run_id=run_id,
                creation_route_id=artifact_record.creation_route_id,
                artifact_ref=artifact_record.artifact_ref,
                artifact_digest=artifact_record.payload_digest,
                format=delivery_format,
                chapter_refs=artifact.chapter_refs,
                chapter_version_refs=artifact.chapter_version_refs,
                chapter_manifest=tuple(chapter_manifest),
                volume_refs=artifact.volume_refs,
                cover_asset_ref=artifact.cover_asset_ref,
                cover_sha256=cover.sha256,
                title=artifact.title,
                author=artifact.author,
                version_note=artifact.version_note,
                filename=filename,
                media_type=media_type,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                created_at=_now(),
            )
            with self._lock:
                record_path = self._book_record_path(run_id, export_id)
                if record_path.exists():
                    existing = BookDeliveryRecord.model_validate(read_json(record_path))
                    if existing != record.model_copy(update={"created_at": existing.created_at}):
                        raise ValueError("Book delivery id was reused with different content")
                    self._validate_book_content(existing)
                    records.append(existing)
                    continue
                self._atomic_write_bytes(self._book_content_path(run_id, export_id), content)
                atomic_write_json(record_path, record.model_dump(mode="json"))
            records.append(record)
        return records

    def read_book_delivery(self, run_id: str, export_id: str) -> BookDeliveryRecord:
        record = BookDeliveryRecord.model_validate(
            read_json(self._book_record_path(run_id, export_id))
        )
        if record.run_id != run_id or record.export_id != export_id:
            raise ValueError("Book delivery storage identity does not match its receipt")
        self._validate_book_content(record)
        return record

    def list_book_delivery(self, run_id: str) -> list[BookDeliveryRecord]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id / "book-records"
        if not directory.exists():
            return []
        records = [
            self.read_book_delivery(run_id, path.stem)
            for path in directory.glob("*.json")
        ]
        return sorted(records, key=lambda item: (item.created_at, item.export_id))

    def book_delivery_content(
        self,
        run_id: str,
        export_id: str,
    ) -> tuple[BookDeliveryRecord, bytes]:
        record = self.read_book_delivery(run_id, export_id)
        return record, self._book_content_path(run_id, export_id).read_bytes()

    def _validate_content(self, record: ExportRecord) -> None:
        content = self._content_path(record.run_id, record.export_id).read_bytes()
        if len(content) != record.size_bytes or hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError("Stored export content does not match its immutable receipt")

    def _validate_script_content(self, record: ScriptDeliveryRecord) -> None:
        content = self._script_content_path(record.run_id, record.export_id).read_bytes()
        if len(content) != record.size_bytes or hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError("Stored script delivery does not match its immutable receipt")

    def _validate_book_content(self, record: BookDeliveryRecord) -> None:
        content = self._book_content_path(record.run_id, record.export_id).read_bytes()
        if len(content) != record.size_bytes or hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError("Stored book delivery does not match its immutable receipt")

    def _record_path(self, run_id: str, export_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(export_id, label="export_id")
        return self.root / run_id / "records" / f"{export_id}.json"

    def _content_path(self, run_id: str, export_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(export_id, label="export_id")
        return self.root / run_id / "files" / f"{export_id}.bin"

    def _script_record_path(self, run_id: str, export_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(export_id, label="export_id")
        return self.root / run_id / "script-records" / f"{export_id}.json"

    def _script_content_path(self, run_id: str, export_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(export_id, label="export_id")
        return self.root / run_id / "script-files" / f"{export_id}.bin"

    def _book_record_path(self, run_id: str, export_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(export_id, label="export_id")
        return self.root / run_id / "book-records" / f"{export_id}.json"

    def _book_content_path(self, run_id: str, export_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(export_id, label="export_id")
        return self.root / run_id / "book-files" / f"{export_id}.bin"

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            temp.write_bytes(content)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def _render_export(
    artifact: ExportArtifact,
    chapters: list[ChapterArtifact],
    *,
    cover_asset: tuple[CoverAssetRecord, bytes] | None,
) -> tuple[bytes, str, str]:
    stem = _safe_filename(artifact.metadata.title)
    if artifact.format == "md":
        return _markdown(artifact, chapters), f"{stem}.md", "text/markdown; charset=utf-8"
    if artifact.format == "json":
        return _json_export(artifact, chapters), f"{stem}.json", "application/json"
    return (
        _zip_export(artifact, chapters, stem, cover_asset=cover_asset),
        f"{stem}.zip",
        "application/zip",
    )


def _markdown(artifact: ExportArtifact, chapters: list[ChapterArtifact]) -> bytes:
    sections = [f"# {artifact.metadata.title}"]
    if artifact.metadata.author:
        sections.append(f"作者：{artifact.metadata.author}")
    chapter_number = 0
    cursor = 0
    for volume_number, volume in enumerate(artifact.volumes, start=1):
        sections.append(f"## 第{volume_number}卷 {volume.title}")
        for chapter in chapters[cursor : cursor + volume.chapter_count]:
            chapter_number += 1
            sections.append(f"### 第{chapter_number}章 {chapter.title}\n\n{chapter.content}")
        cursor += volume.chapter_count
    return ("\n\n".join(sections).rstrip() + "\n").encode("utf-8")


def _json_export(artifact: ExportArtifact, chapters: list[ChapterArtifact]) -> bytes:
    payload = {
        "metadata": artifact.metadata.model_dump(mode="json"),
        "chapter_version_ids": artifact.chapter_version_ids,
        "cover_asset_id": artifact.cover_asset_id,
        "volumes": [volume.model_dump(mode="json") for volume in artifact.volumes],
        "chapters": [
            chapter.model_dump(mode="json", include={"chapter_id", "version_id", "title", "content"})
            for chapter in chapters
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _zip_export(
    artifact: ExportArtifact,
    chapters: list[ChapterArtifact],
    stem: str,
    *,
    cover_asset: tuple[CoverAssetRecord, bytes] | None,
) -> bytes:
    buffer = io.BytesIO()
    manifest = {
        "format": artifact.format,
        "metadata": artifact.metadata.model_dump(mode="json"),
        "chapter_version_ids": artifact.chapter_version_ids,
        "cover_asset_id": artifact.cover_asset_id,
        "volumes": [volume.model_dump(mode="json") for volume in artifact.volumes],
    }
    if cover_asset is not None:
        record, _ = cover_asset
        manifest["cover"] = {
            "asset_id": record.asset_id,
            "filename": f"cover.{record.extension}",
            "mime_type": record.mime_type,
            "sha256": record.sha256,
            "width": record.width,
            "height": record.height,
        }
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED) as archive:
        _write_zip_member(archive, f"{stem}.md", _markdown(artifact, chapters))
        if cover_asset is not None:
            record, content = cover_asset
            _write_zip_member(archive, f"cover.{record.extension}", content)
        _write_zip_member(
            archive,
            "manifest.json",
            (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
    return buffer.getvalue()


def _write_zip_member(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def _safe_filename(title: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "-", title).strip(" .-")
    return value[:120] or "yotsuba-ink-export"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "BookDeliveryChapterReceipt",
    "BookDeliveryRecord",
    "ExportRecord",
    "ExportStore",
    "ScriptDeliveryRecord",
]

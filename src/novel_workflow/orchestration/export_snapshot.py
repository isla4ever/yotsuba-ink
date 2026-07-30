from __future__ import annotations

import hashlib
import io
import mimetypes
import zipfile
from typing import Any

from novel_workflow.orchestration.export_delivery import effective_delivery_metadata, select_export_chapters
from novel_workflow.orchestration.recovery import artifact_signature


def freeze_export_selection(
    state: Any,
    artifact: dict[str, Any],
    *,
    package_format: str,
    chapter_ids: list[str] | None,
    metadata: dict[str, str] | None,
) -> tuple[dict[str, Any], str]:
    selected = select_export_chapters(artifact, chapter_ids)
    delivery_metadata = effective_delivery_metadata(artifact, metadata)
    source_artifact_digests = {
        key: artifact_signature(value)
        for key, value in sorted(state.artifacts.items())
        if isinstance(value, (dict, list))
    }
    snapshot = {
        "schema_version": 1,
        "format": package_format,
        "chapter_ids": [str(item["id"]) for item in selected],
        "chapters": [
            {
                "id": str(item["id"]),
                "title": str(item["title"]),
                "words": int(item.get("words") or len(str(item.get("content") or ""))),
                "content_sha256": hashlib.sha256(str(item.get("content") or "").encode("utf-8")).hexdigest(),
            }
            for item in selected
        ],
        "metadata": delivery_metadata,
        "cover_asset": dict(artifact.get("cover_asset") or {}),
        "validation": dict(artifact.get("validation") or {}),
        "source_artifact_digests": source_artifact_digests,
        "quality_digest": artifact_signature(state.quality_reports),
        "canon_digest": artifact_signature({
            "facts": state.canon_facts,
            "conflicts": state.canon_conflicts,
        }),
    }
    return snapshot, artifact_signature(snapshot)


def export_file_manifest(
    content: bytes,
    *,
    filename: str,
    media_type: str,
    package_format: str,
) -> list[dict[str, Any]]:
    entries = [_file_entry(filename, content, media_type=media_type, scope="package")]
    if package_format != "zip":
        return entries
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                payload = archive.read(info.filename)
                guessed_type = mimetypes.guess_type(info.filename)[0] or "application/octet-stream"
                entries.append(_file_entry(info.filename, payload, media_type=guessed_type, scope="archive"))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("导出 ZIP 文件清单校验失败") from exc
    return entries


def _file_entry(path: str, content: bytes, *, media_type: str, scope: str) -> dict[str, Any]:
    return {
        "path": path,
        "scope": scope,
        "media_type": media_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }

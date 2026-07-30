from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from novel_workflow.orchestration.export_delivery import (
    CoverAssetReader,
    ExportDeliveryError,
    ExportFormat,
    build_export_artifact,
    effective_delivery_metadata,
)


def build_export_preview(
    state: Any,
    *,
    package_format: ExportFormat,
    chapter_ids: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    cover_asset_reader: CoverAssetReader | None = None,
) -> tuple[bytes, str, str]:
    artifact = build_export_artifact(state, cover_asset_reader=cover_asset_reader)
    completed = [
        item for item in artifact["chapters"]
        if item.get("status") == "completed" and str(item.get("content") or "").strip()
    ]
    completed_by_id = {str(item["id"]): item for item in completed}
    requested = chapter_ids or list(completed_by_id)
    if len(requested) != len(set(requested)):
        raise ExportDeliveryError("预览章节不能重复")
    if not requested:
        raise ExportDeliveryError("至少完成一章正文后才能生成预览稿")
    if any(item_id not in completed_by_id for item_id in requested):
        raise ExportDeliveryError("预览稿只能包含已完成且正文非空的章节")
    selected = [completed_by_id[item_id] for item_id in requested]
    delivery_metadata = effective_delivery_metadata(artifact, metadata)
    filename_base = _safe_name(delivery_metadata["bundle_name"] or delivery_metadata["title"])
    if package_format == "md":
        return _markdown(selected, delivery_metadata), f"{filename_base}-preview.md", "text/markdown; charset=utf-8"
    if package_format == "json":
        payload = _preview_manifest(artifact, selected, delivery_metadata)
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), f"{filename_base}-preview.json", "application/json"
    return (
        _zip(state, artifact, selected, delivery_metadata, cover_asset_reader),
        f"{filename_base}-preview.zip",
        "application/zip",
    )


def _preview_manifest(
    artifact: dict[str, Any],
    chapters: list[dict[str, Any]],
    metadata: dict[str, str],
) -> dict[str, Any]:
    return {
        "delivery_state": "preview",
        "notice": "预览稿会随正文与封面变化，不是最终交付收据。",
        "metadata": metadata,
        "chapters": chapters,
        "final_delivery_gate": artifact["validation"],
        "cover_asset": artifact.get("cover_asset") or {},
    }


def _markdown(chapters: list[dict[str, Any]], metadata: dict[str, str]) -> bytes:
    body = [
        f"# {metadata['title']}（预览稿）",
        "",
        "> 本文件只包含当前已完成章节，会随创作继续变化，不代表最终交付完成。",
        "",
    ]
    if metadata["author"]:
        body.extend([f"作者：{metadata['author']}", ""])
    if metadata["version_note"]:
        body.extend([f"版本说明：{metadata['version_note']}", ""])
    for chapter in chapters:
        body.extend([f"## {chapter['title']}", "", chapter["content"], "", "---", ""])
    return "\n".join(body).encode("utf-8")


def _zip(
    state: Any,
    artifact: dict[str, Any],
    chapters: list[dict[str, Any]],
    metadata: dict[str, str],
    cover_asset_reader: CoverAssetReader | None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("PREVIEW.md", "# 预览稿\n\n该包会随创作变化，不是最终不可变交付包。\n")
        for index, chapter in enumerate(chapters, start=1):
            archive.writestr(f"chapters/{index:03d}-{_safe_name(chapter['title'])}.md", chapter["content"])
        archive.writestr(
            "preview-manifest.json",
            json.dumps(_preview_manifest(artifact, chapters, metadata), ensure_ascii=False, indent=2),
        )
        cover = artifact.get("cover_asset") if isinstance(artifact.get("cover_asset"), dict) else {}
        if cover and cover_asset_reader is not None:
            stored, content = cover_asset_reader(str(state.run_id), str(cover.get("asset_id") or ""))
            if stored.get("sha256") == cover.get("sha256"):
                archive.writestr(f"assets/cover.{_cover_extension(str(stored.get('mime_type') or ''))}", content)
    return buffer.getvalue()


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value).strip("_")
    return cleaned or "novel"


def _cover_extension(mime_type: str) -> str:
    return {"image/jpeg": "jpg", "image/webp": "webp"}.get(mime_type, "png")

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable
from typing import Any, Literal


ExportFormat = Literal["md", "json", "zip"]
CoverAssetReader = Callable[[str, str], tuple[dict[str, Any], bytes]]


class ExportDeliveryError(ValueError):
    pass


def build_export_artifact(state: Any, *, cover_asset_reader: CoverAssetReader | None = None) -> dict[str, Any]:
    chapters = _chapters(state)
    completed = [item for item in chapters if item.get("status") == "completed" and str(item.get("content") or "").strip()]
    cover = state.artifacts.get("cover") if isinstance(state.artifacts, dict) else None
    cover_asset = _selected_cover_asset(cover, run_id=str(state.run_id), asset_reader=cover_asset_reader)
    cover_ready = bool(cover_asset)
    quality_ready = _quality_ready(state)
    canon_ready = not any(item.get("status") == "pending" for item in state.canon_conflicts)
    chapters_ready = bool(completed) and len(completed) == len(chapters)
    output_kind = "zip" if len(completed) > 1 else "md"
    title = str(state.inputs.get("title") or "未命名小说")
    package_name = f"{title}-export.{output_kind}"
    validation = {
        "chapters": "ready" if chapters_ready else "blocked",
        "cover": "ready" if cover_ready else "pending",
        "quality": "ready" if quality_ready else "blocked",
        "canon": "ready" if canon_ready else "blocked",
    }
    ready = chapters_ready and cover_ready and quality_ready and canon_ready
    return {
        "manifest": _manifest(output_kind, cover_asset),
        "formats": ["md", "json", "zip"],
        "chapters": [
            {
                "id": str(item.get("id") or f"chapter-{index}"),
                "title": str(item.get("title") or f"第{index}章"),
                "words": int(item.get("words") or len(str(item.get("content") or ""))),
                "status": str(item.get("status") or "drafting"),
                "content": str(item.get("content") or ""),
            }
            for index, item in enumerate(chapters, start=1)
        ],
        "metadata": {
            "title": title,
            "quality_mode": str(state.inputs.get("quality_mode") or "balanced"),
            "artifact_keys": ",".join(state.artifacts.keys()),
        },
        "cover_asset": cover_asset or {},
        "validation": validation,
        "package_status": {"kind": output_kind, "name": package_name, "ready": ready},
    }


def build_export_package(
    state: Any,
    *,
    package_format: ExportFormat,
    chapter_ids: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    cover_asset_reader: CoverAssetReader | None = None,
    frozen_selection: dict[str, Any] | None = None,
    selection_digest: str = "",
) -> tuple[bytes, str, str]:
    artifact = build_export_artifact(state, cover_asset_reader=cover_asset_reader)
    if not artifact["package_status"]["ready"]:
        blocked = [key for key, value in artifact["validation"].items() if value == "blocked"]
        raise ExportDeliveryError(f"导出前置校验未通过：{', '.join(blocked)}")
    selected = select_export_chapters(artifact, chapter_ids)
    delivery_metadata = effective_delivery_metadata(artifact, metadata)
    title = delivery_metadata["title"]
    filename_base = _safe_name(delivery_metadata["bundle_name"] or title)
    if package_format == "md":
        return _markdown(selected, delivery_metadata, selection_digest), f"{filename_base}.md", "text/markdown; charset=utf-8"
    if package_format == "json":
        payload = {
            "export": {**artifact, "chapters": selected, "delivery_metadata": delivery_metadata},
            "frozen_selection": frozen_selection or {},
            "selection_digest": selection_digest,
            "artifacts": _source_artifacts(state),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), f"{filename_base}.json", "application/json"
    return _zip(
        state,
        selected,
        artifact,
        delivery_metadata,
        cover_asset_reader=cover_asset_reader,
        frozen_selection=frozen_selection,
        selection_digest=selection_digest,
    ), f"{filename_base}.zip", "application/zip"


def select_export_chapters(artifact: dict[str, Any], chapter_ids: list[str] | None) -> list[dict[str, Any]]:
    chapters = artifact["chapters"]
    requested_ids = chapter_ids or [item["id"] for item in chapters]
    if len(requested_ids) != len(set(requested_ids)):
        raise ExportDeliveryError("导出章节不能重复")
    chapters_by_id = {item["id"]: item for item in chapters}
    selected = [chapters_by_id[item_id] for item_id in requested_ids if item_id in chapters_by_id]
    if not selected:
        raise ExportDeliveryError("至少选择一章已完成正文")
    if len(selected) != len(requested_ids):
        raise ExportDeliveryError("选择的章节不属于当前运行")
    return selected


def _chapters(state: Any) -> list[dict[str, Any]]:
    artifact = state.artifacts.get("chapters") if isinstance(state.artifacts, dict) else None
    value = artifact.get("chapters") if isinstance(artifact, dict) else []
    return [item for item in value if isinstance(item, dict)]


def _selected_cover_asset(cover: Any, *, run_id: str, asset_reader: CoverAssetReader | None) -> dict[str, Any] | None:
    if not isinstance(cover, dict):
        return None
    selected = str(cover.get("selected_candidate_id") or "").strip()
    candidate = next((
        item for item in cover.get("candidates", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip() == selected
    ), None)
    if not selected or not isinstance(candidate, dict):
        return None
    required = (
        candidate.get("asset_status") == "ready"
        and candidate.get("asset_source") == "production"
        and bool(str(candidate.get("image_url") or "").strip())
        and bool(str(candidate.get("asset_id") or "").strip())
        and bool(str(candidate.get("sha256") or "").strip())
    )
    if not required:
        return None
    if asset_reader is None:
        return _cover_asset_metadata(candidate, selected)
    try:
        metadata, _ = asset_reader(run_id, str(candidate["asset_id"]))
    except (FileNotFoundError, ValueError):
        return None
    if metadata.get("sha256") != candidate.get("sha256"):
        return None
    for key in ("mime_type", "width", "height", "size_bytes"):
        if candidate.get(key) not in (None, "", 0) and candidate.get(key) != metadata.get(key):
            return None
    return _cover_asset_metadata(metadata, selected)


def _cover_asset_metadata(value: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "asset_id": str(value.get("asset_id") or ""),
        "sha256": str(value.get("sha256") or ""),
        "mime_type": str(value.get("mime_type") or ""),
        "width": int(value.get("width") or 0),
        "height": int(value.get("height") or 0),
        "size_bytes": int(value.get("size_bytes") or 0),
        "image_url": str(value.get("image_url") or ""),
    }


def _quality_ready(state: Any) -> bool:
    reports = [item for item in state.quality_reports if isinstance(item, dict)]
    if not reports:
        return False
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for report in reports:
        key = (
            str(report.get("node_id") or ""),
            str(report.get("chapter_id") or report.get("chapter") or ""),
        )
        latest[key] = report
    return all(bool(item.get("passed", True)) for item in latest.values())


def _manifest(output_kind: str, cover_asset: dict[str, Any] | None) -> list[dict[str, str]]:
    cover_name = f"assets/cover.{_cover_extension(str((cover_asset or {}).get('mime_type') or ''))}"
    return [
        {"name": "story-brief.json", "format": "json", "status": "ready"},
        {"name": "summary.json", "format": "json", "status": "ready"},
        {"name": "chapters.md" if output_kind == "md" else "chapters.zip", "format": output_kind, "status": "ready"},
        {"name": cover_name, "format": _cover_extension(str((cover_asset or {}).get("mime_type") or "")), "status": "ready" if cover_asset else "pending"},
    ]


def _markdown(chapters: list[dict[str, Any]], metadata: dict[str, str], selection_digest: str = "") -> bytes:
    body = [f"<!-- novel-workflow-selection:{selection_digest} -->", ""] if selection_digest else []
    body.extend([f"# {metadata['title']}", ""])
    if metadata["author"]:
        body.extend([f"作者：{metadata['author']}", ""])
    if metadata["version_note"]:
        body.extend([f"版本说明：{metadata['version_note']}", ""])
    for chapter in chapters:
        body.extend([f"## {chapter['title']}", "", chapter["content"], "", "---", ""])
    return "\n".join(body).encode("utf-8")


def _zip(
    state: Any,
    chapters: list[dict[str, Any]],
    artifact: dict[str, Any],
    metadata: dict[str, str],
    *,
    cover_asset_reader: CoverAssetReader | None,
    frozen_selection: dict[str, Any] | None,
    selection_digest: str,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, chapter in enumerate(chapters, start=1):
            archive.writestr(f"chapters/{index:03d}-{_safe_name(chapter['title'])}.md", chapter["content"])
        manifest = {key: value for key, value in artifact.items() if key != "chapters"}
        manifest["delivery_metadata"] = metadata
        manifest["frozen_selection"] = frozen_selection or {}
        manifest["selection_digest"] = selection_digest
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, value in _source_artifacts(state).items():
            archive.writestr(name, json.dumps(value, ensure_ascii=False, indent=2))
        readme = [f"# {metadata['title']}", ""]
        if metadata["author"]:
            readme.extend([f"作者：{metadata['author']}", ""])
        if metadata["version_note"]:
            readme.extend([f"版本说明：{metadata['version_note']}", ""])
        readme.append("本文件由 Yotsuba Ink 交付校验后生成。")
        archive.writestr("README.md", "\n".join(readme) + "\n")
        cover_asset = artifact.get("cover_asset") if isinstance(artifact.get("cover_asset"), dict) else {}
        if cover_asset and cover_asset_reader is not None:
            stored, cover_content = cover_asset_reader(str(state.run_id), str(cover_asset.get("asset_id") or ""))
            if stored.get("sha256") != cover_asset.get("sha256"):
                raise ExportDeliveryError("封面资产在导出期间发生变化")
            extension = _cover_extension(str(stored.get("mime_type") or ""))
            archive.writestr(f"assets/cover.{extension}", cover_content)
    return buffer.getvalue()


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value).strip("_")
    return cleaned or "chapter"


def effective_delivery_metadata(artifact: dict[str, Any], metadata: dict[str, str] | None) -> dict[str, str]:
    requested = metadata or {}
    source = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    title = str(requested.get("title") or source.get("title") or "未命名小说").strip()
    return {
        "title": title,
        "author": str(requested.get("author") or "").strip(),
        "version_note": str(requested.get("version_note") or "").strip(),
        "bundle_name": str(requested.get("bundle_name") or title).strip(),
    }


def _cover_extension(mime_type: str) -> str:
    return {"image/jpeg": "jpg", "image/webp": "webp"}.get(mime_type, "png")


def _source_artifacts(state: Any) -> dict[str, Any]:
    source_names = {
        "info_recommend": "story-brief.json",
        "summary": "summary.json",
        "outline": "outline.json",
        "detail_outline": "detail-outline.json",
        "cover": "cover.json",
    }
    return {
        filename: state.artifacts[key]
        for key, filename in source_names.items()
        if isinstance(state.artifacts.get(key), (dict, list))
    }

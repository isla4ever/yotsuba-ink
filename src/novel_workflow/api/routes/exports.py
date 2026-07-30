from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response

from novel_workflow.orchestration.export_delivery import ExportDeliveryError, build_export_artifact, build_export_package
from novel_workflow.orchestration.export_preview import build_export_preview
from novel_workflow.orchestration.recovery import artifact_signature
from novel_workflow.orchestration.export_snapshot import export_file_manifest, freeze_export_selection
from novel_workflow.workflows.schemas import ExportPackageRequest, NovelRunState


router = APIRouter(prefix="/api/runs", tags=["exports"])


@router.post("/{run_id}/export-preview")
async def export_preview(request: Request, run_id: str, payload: ExportPackageRequest) -> Response:
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    state = NovelRunState.model_validate(stored.get("state") or {})
    try:
        content, filename, media_type = build_export_preview(
            state,
            package_format=payload.format,
            chapter_ids=list(payload.chapter_ids),
            metadata=payload.metadata.model_dump(),
            cover_asset_reader=request.app.state.run_store.read_cover_asset,
        )
    except ExportDeliveryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f"attachment; filename=novel-preview.{payload.format}; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
            "X-Export-Mode": "preview",
            "X-Preview-Sha256": hashlib.sha256(content).hexdigest(),
        },
    )


@router.post("/{run_id}/export-package")
async def export_package(request: Request, run_id: str, payload: ExportPackageRequest) -> Response:
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    request_id = payload.request_id.strip() or f"export-request-{uuid4().hex}"
    export_metadata = payload.metadata.model_dump()
    request_digest = _request_digest(payload.format, payload.chapter_ids, export_metadata)
    source_revision = int(stored.get("state_revision") or 0)
    source_state = stored.get("state") or {}
    source_state_digest = artifact_signature(source_state)
    existing_request = request.app.state.run_store.find_export_request(run_id, request_id)
    if existing_request:
        existing, existing_digest = existing_request
        if existing_digest != request_digest:
            raise HTTPException(status_code=409, detail="同一 request_id 不能复用不同的导出参数")
        try:
            receipt, content = request.app.state.run_store.read_export(run_id, str(existing.get("export_id") or ""))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail="导出收据存在但文件已丢失，请重新发起导出") from exc
        return _download_response(receipt, content)
    state = NovelRunState.model_validate(stored.get("state") or {})
    artifact = build_export_artifact(state, cover_asset_reader=request.app.state.run_store.read_cover_asset)
    receipt_metadata = _effective_export_metadata(artifact, export_metadata)
    frozen_chapter_ids = list(payload.chapter_ids) or [
        str(item.get("id") or "")
        for item in artifact.get("chapters", [])
        if isinstance(item, dict) and item.get("id")
    ]
    try:
        selection_snapshot, selection_digest = freeze_export_selection(
            state,
            artifact,
            package_format=payload.format,
            chapter_ids=frozen_chapter_ids,
            metadata=receipt_metadata,
        )
        content, filename, media_type = build_export_package(
            state,
            package_format=payload.format,
            chapter_ids=frozen_chapter_ids,
            metadata=receipt_metadata,
            cover_asset_reader=request.app.state.run_store.read_cover_asset,
            frozen_selection=selection_snapshot,
            selection_digest=selection_digest,
        )
    except ExportDeliveryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    source_snapshot = next(
        (
            item
            for item in reversed(stored.get("snapshots") or [])
            if item.get("restorable") and item.get("state_digest") == source_state_digest
        ),
        None,
    )
    receipt = {
        "export_id": f"export-{uuid4().hex}",
        "run_id": run_id,
        "request_id": request_id,
        "request_digest": request_digest,
        "schema_version": 1,
        "version": 0,
        "snapshot_id": str(source_snapshot.get("snapshot_id") if source_snapshot else f"state-revision-{source_revision}"),
        "artifact_signature": artifact_signature(artifact),
        "selection_digest": selection_digest,
        "selection_snapshot": selection_snapshot,
        "source_state_revision": source_revision,
        "source_state_digest": source_state_digest,
        "format": payload.format,
        "chapter_ids": frozen_chapter_ids,
        "metadata": receipt_metadata,
        "filename": filename,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "files": export_file_manifest(
            content,
            filename=filename,
            media_type=media_type,
            package_format=payload.format,
        ),
        "cover_asset": dict(artifact.get("cover_asset") or {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        saved = request.app.state.run_store.save_export(
            run_id,
            receipt,
            content,
            expected_revision=source_revision,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if saved.get("export_id") != receipt.get("export_id"):
        try:
            saved, content = request.app.state.run_store.read_export(run_id, str(saved.get("export_id") or ""))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail="导出收据存在但文件已丢失，请重新发起导出") from exc
    return _download_response(saved, content, media_type=media_type)


def _request_digest(package_format: str, chapter_ids: list[str], metadata: dict[str, str]) -> str:
    payload = json.dumps(
        {"format": package_format, "chapter_ids": chapter_ids, "metadata": metadata},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _effective_export_metadata(artifact: dict[str, object], metadata: dict[str, str]) -> dict[str, str]:
    artifact_metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    title = str(metadata.get("title") or artifact_metadata.get("title") or "未命名小说").strip()
    bundle_name = str(metadata.get("bundle_name") or title).strip()
    for suffix in (".md", ".json", ".zip"):
        if bundle_name.lower().endswith(suffix):
            bundle_name = bundle_name[: -len(suffix)]
            break
    return {
        "title": title,
        "author": str(metadata.get("author") or "").strip(),
        "version_note": str(metadata.get("version_note") or "").strip(),
        "bundle_name": bundle_name,
    }


def _download_response(receipt: dict[str, object], content: bytes, *, media_type: str | None = None) -> Response:
    filename = str(receipt.get("filename") or "novel-export.bin")
    package_format = str(receipt.get("format") or "bin")
    disposition = f"attachment; filename=novel-export.{package_format}; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=content,
        media_type=media_type or {"md": "text/markdown; charset=utf-8", "json": "application/json", "zip": "application/zip"}.get(package_format, "application/octet-stream"),
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Disposition": disposition,
            "ETag": f'"{receipt.get("sha256") or ""}"',
            "X-Content-Type-Options": "nosniff",
            "X-Export-Id": str(receipt.get("export_id") or ""),
            "X-Export-Version": str(receipt.get("version") or ""),
            "X-Source-Snapshot-Id": str(receipt.get("snapshot_id") or ""),
            "X-Artifact-Signature": str(receipt.get("artifact_signature") or ""),
            "X-Selection-Digest": str(receipt.get("selection_digest") or ""),
            "X-Export-Sha256": str(receipt.get("sha256") or ""),
        },
    )

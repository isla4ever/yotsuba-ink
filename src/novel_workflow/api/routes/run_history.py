from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from novel_workflow.workflows.history_schemas import SnapshotRestoreRequest


router = APIRouter(prefix="/api/runs", tags=["run-history"])


@router.get("/history")
async def list_run_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str = Query(default="", max_length=240),
    project_id: str = Query(default="", max_length=160),
    status: str = Query(default="", max_length=64),
) -> dict[str, object]:
    try:
        items, next_cursor = request.app.state.run_store.list_history(
            limit=limit,
            cursor=cursor,
            project_id=project_id,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items, "next_cursor": next_cursor}


@router.get("/{run_id}/snapshots")
async def list_run_snapshots(request: Request, run_id: str) -> dict[str, object]:
    try:
        stored = request.app.state.run_store.read(run_id)
        items = request.app.state.run_store.list_snapshots(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    latest = next((item for item in items if item.get("restorable")), None)
    return {
        "run_id": run_id,
        "state_revision": int(stored.get("state_revision") or 0),
        "items": items,
        "latest_restorable_snapshot_id": latest.get("snapshot_id") if latest else "",
    }


@router.get("/{run_id}/snapshots/{snapshot_id}")
async def get_run_snapshot(request: Request, run_id: str, snapshot_id: str) -> dict[str, object]:
    try:
        payload = request.app.state.run_store.load_snapshot(run_id, snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown snapshot: {snapshot_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snapshot = payload.get("snapshot") if isinstance(payload, dict) else payload
    if not isinstance(snapshot, dict):
        raise HTTPException(status_code=409, detail="快照格式无效")
    state = payload.get("state") if isinstance(payload, dict) else {}
    return {
        "run_id": run_id,
        "snapshot": snapshot,
        "preview": {
            "current_stage": {
                "id": str((state or {}).get("current_stage_id") or ""),
                "label": str((state or {}).get("current_stage_label") or ""),
                "type": str((state or {}).get("current_stage_type") or ""),
            },
            "artifact_keys": list(((state or {}).get("artifacts") or {}).keys()),
            "completed_stage_ids": list((state or {}).get("completed_stage_ids") or []),
        },
    }


@router.post("/{run_id}/restore-snapshot")
async def restore_run_snapshot(request: Request, run_id: str, payload: SnapshotRestoreRequest) -> dict[str, object]:
    try:
        result = request.app.state.run_store.restore_snapshot(
            run_id,
            payload.snapshot_id,
            request_id=payload.request_id,
            expected_revision=payload.expected_revision,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run or snapshot: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.get("/{run_id}/exports")
async def list_run_exports(request: Request, run_id: str) -> dict[str, object]:
    try:
        items = request.app.state.run_store.list_exports(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run_id, "items": items}


@router.get("/{run_id}/exports/{export_id}")
async def download_run_export(request: Request, run_id: str, export_id: str):
    try:
        receipt, content = request.app.state.run_store.read_export(run_id, export_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown export: {export_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    media_types = {"md": "text/markdown; charset=utf-8", "json": "application/json", "zip": "application/zip"}
    filename = str(receipt.get("filename") or f"novel-export.{receipt.get('format', 'bin')}")
    return Response(
        content=content,
        media_type=media_types.get(str(receipt.get("format") or ""), "application/octet-stream"),
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Disposition": f"attachment; filename=novel-export.{receipt.get('format', 'bin')}; filename*=UTF-8''{quote(filename)}",
            "ETag": f'"{receipt.get("sha256") or ""}"',
            "X-Content-Type-Options": "nosniff",
            "X-Export-Id": str(receipt.get("export_id") or export_id),
            "X-Export-Version": str(receipt.get("version") or ""),
            "X-Source-Snapshot-Id": str(receipt.get("snapshot_id") or ""),
            "X-Artifact-Signature": str(receipt.get("artifact_signature") or ""),
            "X-Selection-Digest": str(receipt.get("selection_digest") or ""),
            "X-Export-Sha256": str(receipt.get("sha256") or ""),
        },
    )

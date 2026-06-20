from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException


def run_state_or_404(app: FastAPI, run_id: str) -> dict[str, Any]:
    try:
        stored = app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    return stored.get("state") or {}

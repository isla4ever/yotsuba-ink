from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ArchivedRunReadOnlyError(RuntimeError):
    code = "archived_run_read_only"


class LegacyRunViewer:
    """Read legacy Run JSON without importing production runtime or writers."""

    _RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")

    def __init__(self, root: Path) -> None:
        self.root = root

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*/run.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            items.append(self._summary(payload, path.parent.name))
        return items

    def read(self, run_id: str) -> dict[str, Any]:
        path = self._path(run_id)
        if not path.exists():
            raise FileNotFoundError(run_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "archive": self._summary(payload, run_id),
            "raw": payload,
            "capabilities": {
                "execute": False,
                "resume": False,
                "decide": False,
                "branch": False,
                "stream": False,
                "writeback": False,
                "provider": False,
            },
        }

    def reject_mutation(self, run_id: str) -> None:
        if self._path(run_id).exists():
            raise ArchivedRunReadOnlyError(f"Archived run is read-only: {run_id}")

    def _path(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not self._RUN_ID.fullmatch(run_id):
            raise ValueError("Invalid run_id")
        return self.root / run_id / "run.json"

    @staticmethod
    def _summary(payload: dict[str, Any], fallback_run_id: str) -> dict[str, Any]:
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        return {
            "run_id": str(payload.get("run_id") or fallback_run_id),
            "project_id": str(payload.get("project_id") or ""),
            "status": "archived_read_only",
            "legacy_runtime_phase": str(state.get("runtime_phase") or ""),
            "created_at": str(payload.get("created_at") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
        }

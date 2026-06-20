from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            items.append(self.read(path.stem))
        return items

    def read(self, item_id: str) -> dict[str, Any]:
        path = self._path(item_id)
        if not path.exists():
            raise FileNotFoundError(item_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._path(item_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def delete(self, item_id: str) -> None:
        path = self._path(item_id)
        if path.exists():
            path.unlink()

    def _path(self, item_id: str) -> Path:
        safe = item_id.replace("/", "-").replace("\\", "-").strip() or "default"
        return self.root / f"{safe}.json"

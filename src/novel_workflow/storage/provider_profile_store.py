from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProviderProfileStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_profiles (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM provider_profiles ORDER BY id").fetchall()
        return [json.loads(str(row[0])) for row in rows]

    def read(self, item_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM provider_profiles WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(item_id)
        return json.loads(str(row[0]))

    def write(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(data, ensure_ascii=False)
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_profiles (id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
                """,
                (item_id, payload, updated_at),
            )
        return data

    def write_many(self, items: dict[str, dict[str, Any]]) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        rows = [
            (item_id, json.dumps(data, ensure_ascii=False), updated_at)
            for item_id, data in items.items()
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO provider_profiles (id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
                """,
                rows,
            )

    def delete(self, item_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM provider_profiles WHERE id = ?", (item_id,))

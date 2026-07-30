from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class ProviderSecretStore:
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
                CREATE TABLE IF NOT EXISTS provider_secrets (
                    provider_id TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def set_api_key(self, provider_id: str, api_key: str) -> None:
        value = api_key.strip()
        if not provider_id.strip():
            raise ValueError("provider_id is required")
        if not value:
            raise ValueError("api_key is required")
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_secrets (provider_id, api_key, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET api_key = excluded.api_key, updated_at = excluded.updated_at
                """,
                (provider_id, value, updated_at),
            )

    def get_api_key(self, provider_id: str) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT api_key FROM provider_secrets WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
        return str(row[0]) if row else None

    def has_api_key(self, provider_id: str) -> bool:
        return self.get_api_key(provider_id) is not None

    def delete_api_key(self, provider_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM provider_secrets WHERE provider_id = ?", (provider_id,))

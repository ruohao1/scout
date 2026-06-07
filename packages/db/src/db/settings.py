from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import database_url


class AppSettingsRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def list(self) -> dict[str, Any]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {str(row["key"]): row["value"] for row in rows}

    def get(self, key: str) -> Any | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute("SELECT value FROM app_settings WHERE key = %(key)s", {"key": key}).fetchone()
        return row["value"] if row is not None else None

    def set(self, key: str, value: Any) -> dict[str, Any]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%(key)s, %(value)s, now())
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    updated_at = now()
                RETURNING key, value, updated_at
                """,
                {"key": key, "value": Jsonb(value)},
            ).fetchone()
        if row is None:
            raise RuntimeError("App setting upsert did not return a row")
        return dict(row)

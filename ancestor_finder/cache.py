"""SQLite cache so a record or model answer is never fetched or paid for twice."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("cache/ancestor_finder.sqlite")


def key_for(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Cache:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS kv ("
            " namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,"
            " created REAL NOT NULL, PRIMARY KEY (namespace, key))"
        )
        self.db.commit()

    def get(self, namespace: str, key: str) -> Any | None:
        row = self.db.execute(
            "SELECT value FROM kv WHERE namespace = ? AND key = ?", (namespace, key)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, namespace: str, key: str, value: Any) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO kv (namespace, key, value, created) VALUES (?, ?, ?, ?)",
            (namespace, key, json.dumps(value, ensure_ascii=False), time.time()),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

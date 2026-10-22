"""SQLite tabanlı basit anahtar-değer önbelleği (TTL destekli)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DAY = 24 * 3600


class Cache:
    def __init__(self, path: str = ":memory:") -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                " ns TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, expires_at REAL NOT NULL,"
                " PRIMARY KEY (ns, key))"
            )
            self._conn.commit()

    def get(self, ns: str, key: str) -> Any | None:
        with self._lock:
            row = self._conn.execute("SELECT value, expires_at FROM kv WHERE ns = ? AND key = ?", (ns, key)).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if expires_at < time.time():
                self._conn.execute("DELETE FROM kv WHERE ns = ? AND key = ?", (ns, key))
                self._conn.commit()
                return None
        return json.loads(value)

    def set(self, ns: str, key: str, value: Any, ttl: float = DAY) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO kv (ns, key, value, expires_at) VALUES (?, ?, ?, ?)",
                (ns, key, payload, time.time() + ttl),
            )
            self._conn.commit()

    def purge_expired(self) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM kv WHERE expires_at < ?", (time.time(),))
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()

"""IP başına kayan pencereli basit hız sınırlayıcı (ücretsiz kotaları korur)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request


class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        self.limit = limit
        self.window = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "anon"

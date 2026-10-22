"""Nominatim ile adres → koordinat. Kullanım kuralı: en fazla 1 istek/sn, açıklayıcı User-Agent."""

from __future__ import annotations

import asyncio
import time

import httpx

from app.cache.store import DAY, Cache
from app.models import GeoArea


class NominatimService:
    def __init__(self, client: httpx.AsyncClient, cache: Cache, base_url: str, min_interval: float = 1.0) -> None:
        self._client = client
        self._cache = cache
        self._url = base_url.rstrip("/") + "/search"
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def _throttle(self) -> None:
        async with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()

    async def geocode(self, query: str) -> GeoArea | None:
        key = " ".join(query.casefold().split())
        cached = self._cache.get("nominatim", key)
        if cached is not None:
            return GeoArea.model_validate(cached) if cached else None

        await self._throttle()
        res = await self._client.get(
            self._url,
            params={"q": query, "format": "jsonv2", "limit": 1, "accept-language": "tr"},
            timeout=15,
        )
        res.raise_for_status()
        results = res.json()
        if not results:
            self._cache.set("nominatim", key, {}, ttl=DAY)
            return None

        hit = results[0]
        bbox = hit.get("boundingbox")
        area = GeoArea(
            name=hit.get("name") or query,
            lat=float(hit["lat"]),
            lon=float(hit["lon"]),
            bbox=(float(bbox[0]), float(bbox[2]), float(bbox[1]), float(bbox[3])) if bbox else None,
        )
        self._cache.set("nominatim", key, area.model_dump(), ttl=30 * DAY)
        return area

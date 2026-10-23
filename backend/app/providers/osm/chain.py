"""Mekan kaynaklarını sırayla dener (Overpass → Nominatim). Düşen kaynak bir süre atlanır."""

from __future__ import annotations

import logging
import math
import time
from typing import Protocol

import httpx

from app.models import Place
from app.providers.osm.overpass import OverpassError

log = logging.getLogger(__name__)


class PlaceProvider(Protocol):
    async def fetch(self, lat: float, lon: float, radius_m: int, interests: list[str]) -> list[Place]: ...


class PlaceSourceChain:
    def __init__(self, sources: list[PlaceProvider], cooldown_s: float = 300.0) -> None:
        self._sources = sources
        self._cooldown = cooldown_s
        self._failed_at: dict[int, float] = {}

    async def fetch(self, lat: float, lon: float, radius_m: int, interests: list[str]) -> list[Place]:
        last_error: Exception | None = None
        for i, source in enumerate(self._sources):
            is_last = i == len(self._sources) - 1
            if not is_last and time.monotonic() - self._failed_at.get(i, -math.inf) < self._cooldown:
                continue  # yakın zamanda düştü; zaman aşımını tekrar beklemeyelim
            try:
                places = await source.fetch(lat, lon, radius_m, interests)
            except (OverpassError, httpx.HTTPError, ValueError) as exc:
                log.warning("Mekan kaynağı %s başarısız: %s", type(source).__name__, exc)
                self._failed_at[i] = time.monotonic()
                last_error = exc
                continue
            if places:
                return places
        raise OverpassError(str(last_error or "hiçbir mekan kaynağı sonuç vermedi"))

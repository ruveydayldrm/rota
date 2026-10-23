"""Nominatim ile adres → koordinat. Kullanım kuralı: en fazla 1 istek/sn, açıklayıcı User-Agent."""

from __future__ import annotations

import asyncio
import math
import time

import httpx

from app.cache.store import DAY, Cache
from app.models import GeoArea, Place
from app.providers.osm.overpass import KEEP_TAGS, classify

# Overpass erişilemezken kullanılan kategori aramaları (Nominatim "özel ifadeler").
BASE_QUERIES = ("museum", "castle", "monument", "attraction")
INTEREST_QUERIES: dict[str, tuple[str, ...]] = {
    "tarih": ("mosque", "castle", "monument", "ruins", "archaeological site"),
    "muze": ("museum", "gallery"),
    "dini": ("mosque", "church"),
    "mimari": ("mosque", "church", "palace"),
    "park": ("park",),
    "doga": ("park", "nature reserve"),
    "manzara": ("viewpoint",),
    "sanat": ("gallery", "theatre"),
    "alisveris": ("marketplace", "bazaar"),
}
FOOD_QUERIES = ("restaurant", "cafe")
MAX_QUERIES = 9
RELIGION_BY_QUERY = {"mosque": "muslim", "church": "christian"}
ALLOWED = {
    "tourism": None,
    "historic": None,
    "leisure": {"park", "garden", "nature_reserve"},
    "amenity": {"place_of_worship", "restaurant", "cafe", "marketplace", "theatre", "arts_centre"},
}


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

    async def fetch(self, lat: float, lon: float, radius_m: int, interests: list[str]) -> list[Place]:
        """Overpass yedeği: yarıçap kutusu içinde kategori aramalarıyla gerçek mekanları toplar."""
        interests = sorted(set(interests))
        key = f"{lat:.3f},{lon:.3f},{radius_m},{','.join(interests)}"
        cached = self._cache.get("nominatim_places", key)
        if cached is not None:
            return [Place.model_validate(p) for p in cached]

        queries: list[str] = []
        for q in [*BASE_QUERIES, *(q for i in interests for q in INTEREST_QUERIES.get(i, ())), *FOOD_QUERIES]:
            if q not in queries:
                queries.append(q)
        queries = [q for q in queries if q not in FOOD_QUERIES][: MAX_QUERIES - 2] + list(FOOD_QUERIES)

        dlat = radius_m / 111_000
        dlon = radius_m / (111_000 * max(math.cos(math.radians(lat)), 0.1))
        viewbox = f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}"

        places: dict[str, Place] = {}
        for query in queries:
            await self._throttle()
            res = await self._client.get(
                self._url,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 40,
                    "extratags": 1,
                    "bounded": 1,
                    "viewbox": viewbox,
                    "accept-language": "tr",
                },
                timeout=15,
            )
            res.raise_for_status()
            for hit in res.json():
                place = self._to_place(hit, query)
                if place is not None:
                    places.setdefault(place.id, place)

        result = list(places.values())
        self._cache.set("nominatim_places", key, [p.model_dump() for p in result], ttl=7 * DAY)
        return result

    @staticmethod
    def _to_place(hit: dict, query: str) -> Place | None:
        name = (hit.get("name") or "").strip()
        category, kind = hit.get("category"), hit.get("type")
        if not name or category not in ALLOWED:
            return None
        allowed_kinds = ALLOWED[category]
        if allowed_kinds is not None and kind not in allowed_kinds:
            return None
        extra = hit.get("extratags") or {}
        tags = {k: v for k, v in extra.items() if k in KEEP_TAGS}
        tags[category] = kind
        if query in RELIGION_BY_QUERY:
            tags.setdefault("religion", RELIGION_BY_QUERY[query])
        return Place(
            id=f"{hit['osm_type'][0]}{hit['osm_id']}",
            name=name,
            lat=round(float(hit["lat"]), 6),
            lon=round(float(hit["lon"]), 6),
            category=classify(tags),
            tags=tags,
            tag_count=len(extra) + 1,
            importance=round(float(hit.get("importance") or 0), 4),
            source="nominatim",
        )

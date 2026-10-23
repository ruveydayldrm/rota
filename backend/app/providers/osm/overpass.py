"""Overpass API (OpenStreetMap) ile gerçek mekanları çeker."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import httpx

from app.cache.store import DAY, Cache
from app.models import Place

log = logging.getLogger(__name__)

# Her zaman sorgulanan turistik temel katman.
BASE_FILTERS = (
    '["tourism"="attraction"]',
    '["tourism"="museum"]',
    '["tourism"="viewpoint"]',
)

INTEREST_FILTERS: dict[str, tuple[str, ...]] = {
    "tarih": (
        '["historic"~"^(monument|memorial|castle|ruins|archaeological_site|fort|city_gate|palace|tomb|citywalls)$"]',
    ),
    "muze": ('["tourism"~"^(museum|gallery)$"]',),
    "dini": ('["amenity"="place_of_worship"]["wikidata"]', '["amenity"="place_of_worship"]["historic"]'),
    "mimari": ('["amenity"="place_of_worship"]["wikidata"]', '["historic"~"^(building|palace|castle)$"]'),
    "park": ('["leisure"~"^(park|garden)$"]',),
    "doga": ('["leisure"="nature_reserve"]', '["natural"~"^(peak|valley|cliff|beach|cave_entrance)$"]'),
    "manzara": ('["tourism"="viewpoint"]',),
    "sanat": ('["tourism"~"^(gallery|artwork)$"]["wikidata"]', '["amenity"~"^(theatre|arts_centre)$"]'),
    "alisveris": ('["amenity"="marketplace"]', '["historic"="bazaar"]'),
    "yemek": (),
    "kahve": (),
}

FOOD_FILTERS = ('["amenity"="restaurant"]', '["amenity"="cafe"]')

# Önbellekte taşınan etiketler; geri kalanlar yalnızca sayılır.
KEEP_TAGS = {
    "wikidata",
    "wikipedia",
    "historic",
    "tourism",
    "amenity",
    "religion",
    "cuisine",
    "heritage",
    "opening_hours",
    "website",
    "name:en",
    "leisure",
    "natural",
}


class OverpassError(Exception):
    pass


def build_query(lat: float, lon: float, radius_m: int, interests: Iterable[str]) -> str:
    around = f"(around:{radius_m},{lat:.5f},{lon:.5f})"
    filters: set[str] = set(BASE_FILTERS)
    for interest in interests:
        filters.update(INTEREST_FILTERS.get(interest, ()))
    sights = "".join(f'nwr{f}["name"]{around};' for f in sorted(filters))
    food = "".join(f'nwr{f}["name"]{around};' for f in FOOD_FILTERS)
    return f"[out:json][timeout:25];({sights})->.s;.s out tags center 400;({food})->.f;.f out tags center 150;"


def classify(tags: dict[str, str]) -> str:
    amenity = tags.get("amenity")
    tourism = tags.get("tourism")
    if amenity == "restaurant":
        return "restoran"
    if amenity == "cafe":
        return "kafe"
    if tourism in ("museum", "gallery"):
        return "muze"
    if amenity == "place_of_worship":
        religion = tags.get("religion")
        if religion == "muslim":
            return "cami"
        if religion == "christian":
            return "kilise"
        return "dini"
    if tourism == "viewpoint":
        return "manzara"
    if tags.get("leisure") in ("park", "garden"):
        return "park"
    if tags.get("leisure") == "nature_reserve" or tags.get("natural"):
        return "doga"
    if amenity == "marketplace" or tags.get("historic") == "bazaar":
        return "carsi"
    if tags.get("historic"):
        return "tarih"
    if tourism == "artwork" or amenity in ("theatre", "arts_centre"):
        return "sanat"
    return "turizm"


def parse_elements(elements: list[dict[str, Any]]) -> list[Place]:
    places: dict[str, Place] = {}
    for el in elements:
        tags: dict[str, str] = el.get("tags") or {}
        name = tags.get("name:tr") or tags.get("name")
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if not name or lat is None or lon is None:
            continue
        pid = f"{el['type'][0]}{el['id']}"
        places[pid] = Place(
            id=pid,
            name=name.strip(),
            lat=round(float(lat), 6),
            lon=round(float(lon), 6),
            category=classify(tags),
            tags={k: v for k, v in tags.items() if k in KEEP_TAGS},
            tag_count=len(tags),
        )
    return list(places.values())


class OverpassService:
    def __init__(self, client: httpx.AsyncClient, cache: Cache, urls: list[str]) -> None:
        self._client = client
        self._cache = cache
        self._urls = urls

    async def fetch(self, lat: float, lon: float, radius_m: int, interests: Iterable[str]) -> list[Place]:
        interests = sorted(set(interests))
        key = f"{lat:.3f},{lon:.3f},{radius_m},{','.join(interests)}"
        cached = self._cache.get("overpass", key)
        if cached is not None:
            return [Place.model_validate(p) for p in cached]

        query = build_query(lat, lon, radius_m, interests)
        last_error: Exception | None = None
        for url in self._urls:
            try:
                res = await self._client.post(url, data={"data": query}, timeout=10)
                if res.status_code != 200:
                    raise OverpassError(f"HTTP {res.status_code}")
                places = parse_elements(res.json().get("elements", []))
                self._cache.set("overpass", key, [p.model_dump() for p in places], ttl=7 * DAY)
                return places
            except (httpx.HTTPError, OverpassError, ValueError) as exc:
                log.warning("Overpass %s başarısız: %s", url, exc)
                last_error = exc
        raise OverpassError(str(last_error))

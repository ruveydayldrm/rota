"""Rota hesaplama: OSRM → OpenRouteService → düz çizgi tahmini."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.cache.store import DAY, Cache
from app.geo import Point, haversine_km
from app.models import Mode, Route

log = logging.getLogger(__name__)

SPEED_KMH: dict[str, float] = {"yuruyus": 4.5, "arac": 30.0}
DETOUR = 1.3  # kuş uçuşu → gerçek yol için kaba katsayı


class RoutingError(Exception):
    pass


class RoutingProvider(Protocol):
    name: str

    async def route(self, points: list[Point], mode: Mode) -> Route: ...


def _round_geometry(coords: list[list[float]]) -> list[list[float]]:
    return [[round(x, 5), round(y, 5)] for x, y in coords]


class OSRMProvider:
    name = "osrm"

    def __init__(self, client: httpx.AsyncClient, foot_url: str, car_url: str) -> None:
        self._client = client
        self._urls = {"yuruyus": foot_url.rstrip("/"), "arac": car_url.rstrip("/")}

    async def route(self, points: list[Point], mode: Mode) -> Route:
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
        url = f"{self._urls[mode]}/route/v1/driving/{coords}"
        try:
            res = await self._client.get(url, params={"overview": "full", "geometries": "geojson"}, timeout=20)
            data = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingError(f"osrm: {exc}") from exc
        if res.status_code != 200 or data.get("code") != "Ok" or not data.get("routes"):
            raise RoutingError(f"osrm: {res.status_code} {data.get('code')}")
        best = data["routes"][0]
        return Route(
            geometry=_round_geometry(best["geometry"]["coordinates"]),
            distance_km=round(best["distance"] / 1000, 2),
            duration_min=round(best["duration"] / 60, 1),
            mode=mode,
            source="osrm",
            legs_min=[round(leg["duration"] / 60, 1) for leg in best.get("legs", [])],
        )


class ORSProvider:
    name = "ors"
    URL = "https://api.openrouteservice.org/v2/directions/{profile}/geojson"
    PROFILES = {"yuruyus": "foot-walking", "arac": "driving-car"}

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self._client = client
        self._key = api_key

    async def route(self, points: list[Point], mode: Mode) -> Route:
        try:
            res = await self._client.post(
                self.URL.format(profile=self.PROFILES[mode]),
                json={"coordinates": [[lon, lat] for lat, lon in points]},
                headers={"Authorization": self._key},
                timeout=20,
            )
            if res.status_code != 200:
                raise RoutingError(f"ors: HTTP {res.status_code}")
            feature = res.json()["features"][0]
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise RoutingError(f"ors: {exc}") from exc
        props = feature["properties"]
        summary = props.get("summary", {})
        return Route(
            geometry=_round_geometry(feature["geometry"]["coordinates"]),
            distance_km=round(summary.get("distance", 0) / 1000, 2),
            duration_min=round(summary.get("duration", 0) / 60, 1),
            mode=mode,
            source="ors",
            legs_min=[round(s.get("duration", 0) / 60, 1) for s in props.get("segments", [])],
        )


def straight_route(points: list[Point], mode: Mode) -> Route:
    """Son çare: duraklar arası düz çizgi ve ortalama hıza göre tahmini süre."""
    legs_km = [haversine_km(a, b) * DETOUR for a, b in zip(points, points[1:])]
    legs_min = [round(km / SPEED_KMH[mode] * 60, 1) for km in legs_km]
    return Route(
        geometry=[[round(lon, 5), round(lat, 5)] for lat, lon in points],
        distance_km=round(sum(legs_km), 2),
        duration_min=round(sum(legs_min), 1),
        mode=mode,
        source="straight",
        legs_min=legs_min,
    )


class RoutingService:
    def __init__(self, providers: list[RoutingProvider], cache: Cache) -> None:
        self._providers = providers
        self._cache = cache

    async def route(self, points: list[Point], mode: Mode) -> Route:
        if len(points) < 2:
            return straight_route(points, mode)
        key = mode + ":" + ";".join(f"{lat:.5f},{lon:.5f}" for lat, lon in points)
        cached = self._cache.get("route", key)
        if cached is not None:
            return Route.model_validate(cached)
        for provider in self._providers:
            try:
                route = await provider.route(points, mode)
                if len(route.legs_min) != len(points) - 1:
                    route.legs_min = straight_route(points, mode).legs_min
                self._cache.set("route", key, route.model_dump(), ttl=7 * DAY)
                return route
            except RoutingError as exc:
                log.warning("Rota sağlayıcısı %s başarısız: %s", provider.name, exc)
        return straight_route(points, mode)

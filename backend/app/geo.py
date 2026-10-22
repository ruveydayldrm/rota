"""Coğrafi yardımcılar: mesafe ve en yakın komşu sıralaması."""

from __future__ import annotations

import math
from collections.abc import Sequence

EARTH_RADIUS_KM = 6371.0088
Point = tuple[float, float]  # (lat, lon)


def haversine_km(a: Point, b: Point) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def path_length_km(points: Sequence[Point]) -> float:
    return sum(haversine_km(a, b) for a, b in zip(points, points[1:]))


def nearest_neighbor_order(points: Sequence[Point], start: int = 0) -> list[int]:
    """`start` noktasından başlayarak her adımda en yakın ziyaret edilmemiş noktaya gider."""
    if not points:
        return []
    remaining = set(range(len(points))) - {start}
    order = [start]
    while remaining:
        last = points[order[-1]]
        nxt = min(remaining, key=lambda i: (haversine_km(last, points[i]), i))
        order.append(nxt)
        remaining.remove(nxt)
    return order

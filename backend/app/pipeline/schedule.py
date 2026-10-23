"""Durak sıralama ve saat planlama. frontend/src/lib/schedule.ts ile aynı kuralları kullanır."""

from __future__ import annotations

import math
from typing import Protocol, TypeVar

from app.geo import haversine_km, nearest_neighbor_order
from app.providers.routing.router import DETOUR, SPEED_KMH

FOOD = frozenset({"restoran", "kafe"})
VISIT_MIN: dict[str, int] = {
    "muze": 75,
    "cami": 35,
    "kilise": 35,
    "dini": 35,
    "tarih": 45,
    "park": 40,
    "doga": 60,
    "manzara": 25,
    "restoran": 60,
    "kafe": 30,
    "carsi": 50,
    "sanat": 45,
    "turizm": 45,
}
DEFAULT_VISIT = 45
DEFAULT_START = 9 * 60
LUNCH = 12 * 60 + 30
DINNER = 19 * 60
COFFEE = 16 * 60


class Located(Protocol):
    id: str
    lat: float
    lon: float
    category: str


T = TypeVar("T", bound=Located)


def visit_min(category: str) -> int:
    return VISIT_MIN.get(category, DEFAULT_VISIT)


def round5(minutes: float) -> int:
    return int(math.floor(minutes / 5 + 0.5) * 5)


def parse_hhmm(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    try:
        h, m = (int(x) for x in value.split(":", 1))
    except ValueError:
        return None
    if not (0 <= h < 24 and 0 <= m < 60):
        return None
    return h * 60 + m


def fmt_hhmm(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def estimate_leg_min(a: Located, b: Located, mode: str) -> float:
    km = haversine_km((a.lat, a.lon), (b.lat, b.lon)) * DETOUR
    return km / SPEED_KMH[mode] * 60


def _clock_after(seq: list[T], mode: str, start: int) -> float:
    t = float(start)
    for i, p in enumerate(seq):
        t += visit_min(p.category)
        if i + 1 < len(seq):
            t += estimate_leg_min(p, seq[i + 1], mode)
    return t


def order_stops(items: list[T], mode: str, start: int = DEFAULT_START, anchor_id: str | None = None) -> list[T]:
    """Gezilecek yerleri en yakın komşu ile sıralar, yemek duraklarını uygun saate yerleştirir."""
    sights = [p for p in items if p.category not in FOOD]
    food = [p for p in items if p.category in FOOD]
    if not sights:
        return list(items)

    start_idx = next((i for i, p in enumerate(sights) if p.id == anchor_id), None)
    if start_idx is None:
        # Başlangıç yoksa merkezden en uzak noktadan başla: rota zikzak yerine tek yönde süpürür.
        clat = sum(p.lat for p in sights) / len(sights)
        clon = sum(p.lon for p in sights) / len(sights)
        start_idx = max(range(len(sights)), key=lambda i: haversine_km((clat, clon), (sights[i].lat, sights[i].lon)))
    route = [sights[i] for i in nearest_neighbor_order([(p.lat, p.lon) for p in sights], start_idx)]

    restaurants = 0
    for f in sorted(food, key=lambda p: 0 if p.category == "restoran" else 1):
        if f.category == "restoran":
            target = LUNCH if restaurants == 0 else DINNER
            restaurants += 1
        else:
            target = COFFEE
        best = min(
            range(1, len(route) + 1),
            key=lambda pos: (abs(_clock_after(route[:pos], mode, start) - target), pos),
        )
        route.insert(best, f)
    return route


def schedule_times(items: list[T], legs_min: list[float], start: int = DEFAULT_START) -> list[str]:
    """Her durağa varış saatini, ziyaret süreleri ve yol süreleriyle hesaplar (5 dk'ya yuvarlı)."""
    t = float(start)
    times: list[str] = []
    for i, p in enumerate(items):
        times.append(fmt_hhmm(round5(t)))
        t += visit_min(p.category)
        if i < len(legs_min):
            t += legs_min[i]
    return times

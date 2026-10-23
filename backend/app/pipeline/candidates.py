"""Aday mekanların önemlilik puanı ve LLM'e gidecek kısa liste."""

from __future__ import annotations

from app.geo import haversine_km
from app.models import Intent, Place
from app.pipeline.schedule import FOOD

POOL_SIZE = 40
SHORTLIST_SIZE = 25

INTEREST_CATEGORIES: dict[str, set[str]] = {
    "tarih": {"tarih", "muze", "cami", "kilise", "dini", "turizm"},
    "muze": {"muze"},
    "dini": {"cami", "kilise", "dini"},
    "mimari": {"cami", "kilise", "tarih", "turizm"},
    "park": {"park"},
    "doga": {"doga", "park", "manzara"},
    "manzara": {"manzara"},
    "yemek": {"restoran"},
    "kahve": {"kafe"},
    "sanat": {"sanat", "muze"},
    "alisveris": {"carsi"},
}


def importance(place: Place, center: tuple[float, float], radius_km: float, interests: list[str]) -> float:
    tags = place.tags
    score = 0.0
    if "wikidata" in tags:
        score += 3
    if "wikipedia" in tags:
        score += 3
    if "heritage" in tags:
        score += 1.5
    if "name:en" in tags:
        score += 0.5
    score += min(place.tag_count, 20) * 0.15
    score += place.importance * 12
    if place.category in FOOD:
        score += 0.5 * sum(k in tags for k in ("cuisine", "opening_hours", "website"))
        # Yemek yerinde ünden çok yakınlık önemli: merkezden uzak olan ek ceza alır.
        score -= 2.0 * min(haversine_km(center, (place.lat, place.lon)) / max(radius_km, 0.1), 1.5)
    if any(place.category in INTEREST_CATEGORIES.get(i, set()) for i in interests):
        score += 1.5
    distance = haversine_km(center, (place.lat, place.lon))
    score -= 1.0 * min(distance / max(radius_km, 0.1), 1.5)
    return round(score, 3)


def rank_pool(places: list[Place], center: tuple[float, float], radius_km: float, intent: Intent) -> list[Place]:
    """Puanlar, isim tekrarlarını eler ve en iyi ~40 mekanı (gezilecek + yemek) döndürür."""
    scored = [p.model_copy(update={"score": importance(p, center, radius_km, list(intent.ilgi))}) for p in places]
    best_by_name: dict[str, Place] = {}
    for p in sorted(scored, key=lambda x: -x.score):
        best_by_name.setdefault(p.name.casefold(), p)
    unique = list(best_by_name.values())

    food_n = 12 if ({"yemek", "kahve"} & set(intent.ilgi)) else 8
    sights = [p for p in unique if p.category not in FOOD][: POOL_SIZE - food_n]
    # Restoran ve kafe ayrı kotalarla: biri diğerini havuzdan tamamen silmesin.
    restaurants = [p for p in unique if p.category == "restoran"][: (food_n + 1) // 2]
    cafes = [p for p in unique if p.category == "kafe"][: food_n - len(restaurants)]
    return sights + restaurants + cafes


def shortlist(pool: list[Place], must_include: set[str] | None = None, size: int = SHORTLIST_SIZE) -> list[Place]:
    """LLM'e gidecek en iyi 25 aday: ~20 gezilecek yer + 5 yemek, artı korunması gereken duraklar."""
    must_include = must_include or set()
    sights = sorted((p for p in pool if p.category not in FOOD), key=lambda p: -p.score)
    restaurants = sorted((p for p in pool if p.category == "restoran"), key=lambda p: -p.score)
    cafes = sorted((p for p in pool if p.category == "kafe"), key=lambda p: -p.score)
    food = restaurants[:3] + cafes[: 5 - len(restaurants[:3])]
    chosen = sights[: size - len(food)] + food
    ids = {p.id for p in chosen}
    chosen += [p for p in pool if p.id in must_include and p.id not in ids]
    return chosen

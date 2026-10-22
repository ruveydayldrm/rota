"""Testlerde hiçbir dış servise gidilmez: tüm sağlayıcılar burada sahtelenir."""

from __future__ import annotations

import os
from typing import Any

os.environ["CACHE_PATH"] = ":memory:"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""

import pytest

from app.cache.store import Cache
from app.geo import Point
from app.models import GeoArea, Mode, Place, WikiInfo
from app.pipeline.orchestrator import Pipeline
from app.providers.llm.base import LLMProvider, LLMRateLimited
from app.providers.llm.fallback import FallbackLLM
from app.providers.routing.router import straight_route

SULTANAHMET = (41.0054, 28.9768)


def make_place(pid: str, name: str, lat: float, lon: float, category: str, **tags: str) -> Place:
    return Place(id=pid, name=name, lat=lat, lon=lon, category=category, tags=tags, tag_count=len(tags) + 3)


PLACES = [
    make_place("w1", "Ayasofya", 41.0086, 28.9802, "cami", wikidata="Q12506"),
    make_place("w2", "Sultanahmet Camii", 41.0054, 28.9768, "cami", wikidata="Q36412"),
    make_place("n3", "Yerebatan Sarnıcı", 41.0084, 28.9779, "tarih", wikidata="Q215089"),
    make_place("r4", "Topkapı Sarayı", 41.0115, 28.9834, "muze", wikidata="Q170495"),
    make_place("w5", "Kapalıçarşı", 41.0107, 28.9680, "carsi", wikidata="Q190945"),
    make_place("w6", "Süleymaniye Camii", 41.0162, 28.9639, "cami", wikidata="Q190130"),
    make_place("n7", "Gülhane Parkı", 41.0129, 28.9813, "park"),
    make_place("n8", "Tarihi Sultanahmet Köftecisi", 41.0082, 28.9761, "restoran", cuisine="turkish"),
    make_place("n9", "Hafız Mustafa", 41.0115, 28.9762, "kafe", cuisine="dessert"),
]


class ScriptedLLM(LLMProvider):
    """Sırayla önceden yazılmış yanıtları döndürür ve aldığı istekleri kaydeder."""

    def __init__(self, responses: list[dict[str, Any] | Exception], name: str = "scripted") -> None:
        self.name = name
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    async def generate_json(self, *, system: str, user: str, schema: dict[str, Any], temperature: float = 0.2):
        self.calls.append({"system": system, "user": user})
        if not self.responses:
            raise LLMRateLimited("yanıt kalmadı")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeGeocoder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def geocode(self, query: str) -> GeoArea | None:
        self.queries.append(query)
        if "atlantis" in query.casefold():
            return None
        return GeoArea(name=query, lat=SULTANAHMET[0], lon=SULTANAHMET[1])


class FakePlaces:
    def __init__(self, places: list[Place] | None = None) -> None:
        self.places = places if places is not None else PLACES
        self.calls = 0

    async def fetch(self, lat: float, lon: float, radius_m: int, interests: list[str]) -> list[Place]:
        self.calls += 1
        return list(self.places)


class FakeRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[list[Point], Mode]] = []

    async def route(self, points: list[Point], mode: Mode):
        self.calls.append((points, mode))
        return straight_route(points, mode)


class FakeWiki:
    async def enrich(self, places: list[Place]) -> dict[str, WikiInfo]:
        return {p.id: WikiInfo(extract=f"{p.name} hakkında kısa bilgi.") for p in places if "wikidata" in p.tags}


INTENT_ISTANBUL = {
    "sehir": "İstanbul",
    "ilce": None,
    "ilgi": ["tarih", "mimari"],
    "sure": "1_gun",
    "mod": "yuruyus",
    "baslangic_saati": "09:00",
    "ozel_istekler": [],
    "soru": None,
    "tur": "yeni",
    "yalnizca_mod": False,
}

SELECTION_OK = {
    "secilen": [
        {"id": "r4", "saat": "09:00", "ipucu": "Harem için ayrı bilet al."},
        {"id": "w1", "saat": "11:00", "ipucu": "Sabah erken git."},
        {"id": "n3", "saat": "12:00", "ipucu": "Serin, ceket al."},
        {"id": "n8", "saat": "12:45", "ipucu": "Öğle kalabalığından önce git."},
        {"id": "w2", "saat": "14:00", "ipucu": "Namaz vakitlerine dikkat."},
        {"id": "w5", "saat": "15:30", "ipucu": "Pazarlık yap."},
        {"id": "n999999", "saat": "16:00", "ipucu": "Uydurma bir mekan."},
    ],
    "giris": "Tarihi yarımadada yürüyerek geçen dolu bir gün.",
    "kapanis": "İstersen araçla da hesaplayabilirim.",
}


@pytest.fixture
def cache() -> Cache:
    return Cache(":memory:")


def make_pipeline(llm_responses: list[Any], cache: Cache, places: list[Place] | None = None):
    llm = ScriptedLLM(llm_responses)
    deps = {
        "geocoder": FakeGeocoder(),
        "places": FakePlaces(places),
        "router": FakeRouter(),
        "wiki": FakeWiki(),
    }
    pipeline = Pipeline(llm=FallbackLLM([llm]), cache=cache, text_delay=0, **deps)
    return pipeline, llm, deps


async def collect(pipeline: Pipeline, request) -> list[tuple[str, dict[str, Any]]]:
    return [event async for event in pipeline.run(request)]

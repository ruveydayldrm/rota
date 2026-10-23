"""AI hattının tamamı: her adım frontend'e ayrı bir SSE olayı olarak akar."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.cache.store import DAY, Cache
from app.geo import Point
from app.models import (
    ChatRequest,
    GeoArea,
    Intent,
    IntentParse,
    Mode,
    Place,
    Route,
    Stop,
    Trip,
    TripRecord,
    WikiInfo,
)
from app.pipeline.candidates import rank_pool, shortlist
from app.pipeline.intent import parse_intent
from app.pipeline.rules import rule_parse
from app.pipeline.schedule import DEFAULT_START, estimate_leg_min, order_stops, parse_hhmm, schedule_times
from app.pipeline.select import select_stops
from app.providers.llm.base import LLMUnavailable
from app.providers.llm.fallback import FallbackLLM
from app.providers.osm.overpass import OverpassError

log = logging.getLogger(__name__)

Event = tuple[str, dict[str, Any]]

BUSY_MESSAGE = "Şu an çok yoğunuz, birkaç saniye sonra tekrar dene."
GENERIC_MESSAGE = "Bir şeyler ters gitti. Birkaç saniye sonra tekrar dener misin?"
TRIP_TTL = DAY

# Nominatim'in bölge adlarını tek bir noktaya oturtamadığı yerler için arama ipucu.
GEOCODE_ALIASES = {"kapadokya": "Göreme, Nevşehir", "cappadocia": "Göreme, Nevşehir"}


class UserFacingError(Exception):
    """Kullanıcıya olduğu gibi gösterilebilecek hata."""


class Geocoder(Protocol):
    async def geocode(self, query: str) -> GeoArea | None: ...


class PlaceSource(Protocol):
    async def fetch(self, lat: float, lon: float, radius_m: int, interests: list[str]) -> list[Place]: ...


class Router(Protocol):
    async def route(self, points: list[Point], mode: Mode) -> Route: ...


class WikiSource(Protocol):
    async def enrich(self, places: list[Place]) -> dict[str, WikiInfo]: ...


def norm(text: str) -> str:
    """Türkçe kurallarıyla küçük harfe çevirip boşlukları sadeleştirir (İ→i, I→ı)."""
    return " ".join(text.replace("İ", "i").replace("I", "ı").lower().split())


def intent_key(intent: Intent) -> str:
    return json.dumps(
        {
            "s": norm(intent.sehir),
            "i": norm(intent.ilce or ""),
            "g": sorted(intent.ilgi),
            "d": intent.sure,
            "m": intent.mod,
            "t": intent.baslangic_saati,
            "o": sorted(norm(x) for x in intent.ozel_istekler),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def search_radius_m(intent: Intent) -> int:
    if intent.mod == "arac":
        return 15000
    return 1800 if intent.sure == "yarim_gun" else 2500


def dump(items: list[Stop]) -> list[dict[str, Any]]:
    return [s.model_dump(mode="json") for s in items]


class Pipeline:
    def __init__(
        self,
        *,
        llm: FallbackLLM,
        geocoder: Geocoder,
        places: PlaceSource,
        router: Router,
        wiki: WikiSource,
        cache: Cache,
        text_delay: float = 0.018,
    ) -> None:
        self.llm = llm
        self.geocoder = geocoder
        self.places = places
        self.router = router
        self.wiki = wiki
        self.cache = cache
        self.text_delay = text_delay

    # --- Genel giriş noktaları -----------------------------------------------

    async def run(self, req: ChatRequest) -> AsyncIterator[Event]:
        try:
            async for event in self._run(req):
                yield event
        except UserFacingError as exc:
            yield "error", {"message": str(exc)}
        except LLMUnavailable:
            yield "error", {"message": BUSY_MESSAGE}
        except Exception:
            log.exception("Hat beklenmedik şekilde durdu")
            yield "error", {"message": GENERIC_MESSAGE}

    def load_trip(self, trip_id: str | None) -> TripRecord | None:
        if not trip_id:
            return None
        data = self.cache.get("trip", trip_id)
        return TripRecord.model_validate(data) if data else None

    async def remode(self, record: TripRecord, mode: Mode) -> TripRecord:
        """Aynı durakları başka bir ulaşım şekliyle yeniden hesaplar."""
        trip = record.trip
        intent = trip.intent.model_copy(update={"mod": mode})
        route = await self.router.route([(s.lat, s.lon) for s in trip.stops], mode)
        stops = self._retime(trip.stops, route, intent)
        new = TripRecord(
            trip=trip.model_copy(update={"id": self._new_id(), "intent": intent, "stops": stops, "route": route}),
            candidates=record.candidates,
        )
        self._save(new, by_intent=False)
        return new

    # --- Hat -----------------------------------------------------------------

    async def _run(self, req: ChatRequest) -> AsyncIterator[Event]:
        prev = self.load_trip(req.trip_id)
        previous_intent = prev.trip.intent if prev else req.context

        # 1) Niyet
        parse, intent_source = await self._parse(req.message, previous_intent)
        intent = parse.to_intent()
        if intent is None:
            yield "intent_parsed", {"intent": None, "source": intent_source}
            async for ev in self._text(parse.soru or "Hangi şehir için rota kuralım?", "intro"):
                yield ev
            yield "done", {"trip": None}
            return
        yield "intent_parsed", {"intent": intent.model_dump(mode="json"), "source": intent_source}

        editing = prev is not None and parse.tur == "duzenle" and norm(prev.trip.intent.sehir) == norm(intent.sehir)
        if editing and parse.yalnizca_mod and prev is not None:
            async for ev in self._remode_events(prev, intent.mod):
                yield ev
            return

        if not editing:
            cached = self._cached_trip(intent)
            if cached is not None:
                async for ev in self._replay(cached):
                    yield ev
                return

        # 2-3) Konum ve gerçek aday mekanlar
        center, pool = await self._candidates(intent, prev.candidates if editing and prev else [])
        nominatim_share = sum(p.source == "nominatim" for p in pool) / len(pool)
        places_source = "Nominatim" if nominatim_share > 0.5 else "Overpass"
        yield "places_found", {"count": len(pool), "source": places_source}

        # 4) LLM seçimi (yalnızca aday ID'leri) ve coğrafi sıralama
        current = prev.trip.stops if editing and prev else None
        keep = {s.id for s in current} if current else set()
        center_pt = (center[1], center[0])
        result = await select_stops(self.llm, intent, shortlist(pool, keep), req.message, center_pt, current)

        start = parse_hhmm(intent.baslangic_saati) or DEFAULT_START
        ordered = order_stops(result.places, intent.mod, start, result.anchor_id)
        known_wiki = {s.id: s.wiki for s in current or [] if s.wiki}
        legs = [estimate_leg_min(a, b, intent.mod) for a, b in zip(ordered, ordered[1:])]
        stops = [
            Stop.from_place(p, tip=result.tips.get(p.id, ""), time=t, wiki=known_wiki.get(p.id))
            for p, t in zip(ordered, schedule_times(ordered, legs, start))
        ]
        stops_source = "LLM" if result.used_llm else "kurallar"
        yield "stops_selected", {"stops": dump(stops), "source": stops_source}

        # 5) Rota (+ arka planda Wikipedia)
        wiki_task = asyncio.create_task(self.wiki.enrich([p for p in ordered if p.id not in known_wiki]))
        route = await self.router.route([(s.lat, s.lon) for s in stops], intent.mod)
        stops = self._retime(stops, route, intent)
        yield (
            "route_ready",
            {"route": route.model_dump(mode="json"), "stops": dump(stops), "city": intent.sehir, "center": center},
        )

        # 6) Akan metin
        async for ev in self._text(result.intro, "intro"):
            yield ev
        async for ev in self._text(result.outro, "outro"):
            yield ev

        try:
            wiki = await asyncio.wait_for(wiki_task, timeout=12)
        except Exception:  # Wikipedia olmadan da rota eksiksizdir
            wiki = {}
        stops = [s.model_copy(update={"wiki": wiki.get(s.id) or s.wiki}) for s in stops]

        trip = Trip(
            id=self._new_id(),
            city=intent.sehir,
            center=center,
            intent=intent,
            stops=stops,
            route=route,
            intro=result.intro,
            outro=result.outro,
            candidates_count=len(pool),
            sources={"intent": intent_source, "places": places_source, "stops": stops_source},
        )
        self._save(TripRecord(trip=trip, candidates=pool), by_intent=not editing)
        yield "done", {"trip": trip.model_dump(mode="json")}

    async def _parse(self, message: str, previous: Intent | None) -> tuple[IntentParse, str]:
        if previous is None:
            cached = self.cache.get("intent", norm(message))
            if cached:
                return IntentParse.model_validate(cached), "LLM"
        try:
            parse = await parse_intent(self.llm, message, previous)
        except LLMUnavailable:
            log.info("LLM yok; kural tabanlı niyet çıkarma kullanılıyor")
            return rule_parse(message, previous), "kurallar"  # LLM gelince daha iyisi üretilsin diye önbelleğe alınmaz
        if previous is None:
            self.cache.set("intent", norm(message), parse.model_dump(mode="json"), ttl=7 * DAY)
        return parse, "LLM"

    async def _candidates(self, intent: Intent, previous: list[Place]) -> tuple[list[float], list[Place]]:
        query = GEOCODE_ALIASES.get(norm(intent.sehir), intent.sehir)
        if intent.ilce:
            query = f"{intent.ilce}, {query}"
        area = await self.geocoder.geocode(query)
        if area is None:
            raise UserFacingError(f"“{intent.sehir}” yerini haritada bulamadım. Yazımını kontrol eder misin?")

        radius = search_radius_m(intent)
        try:
            raw = await self.places.fetch(area.lat, area.lon, radius, list(intent.ilgi))
        except OverpassError as exc:
            raise UserFacingError(BUSY_MESSAGE) from exc

        pool = rank_pool(raw, (area.lat, area.lon), radius / 1000, intent)
        ids = {p.id for p in pool}
        pool += [p for p in previous if p.id not in ids]
        if len(pool) < 3:
            raise UserFacingError("Bu bölgede yeterince mekan bulamadım. Biraz daha geniş bir yer dener misin?")
        return [round(area.lon, 5), round(area.lat, 5)], pool

    def _retime(self, stops: list[Stop], route: Route, intent: Intent) -> list[Stop]:
        start = parse_hhmm(intent.baslangic_saati) or DEFAULT_START
        legs = route.legs_min
        if len(legs) != len(stops) - 1:
            legs = [estimate_leg_min(a, b, route.mode) for a, b in zip(stops, stops[1:])]
        times = schedule_times(stops, legs, start)
        return [s.model_copy(update={"time": t}) for s, t in zip(stops, times)]

    async def _remode_events(self, prev: TripRecord, mode: Mode) -> AsyncIterator[Event]:
        yield "places_found", {"count": prev.trip.candidates_count, "source": prev.trip.sources.get("places")}
        yield "stops_selected", {"stops": dump(prev.trip.stops), "source": prev.trip.sources.get("stops")}
        record = await self.remode(prev, mode)
        trip = record.trip
        yield (
            "route_ready",
            {
                "route": trip.route.model_dump(mode="json"),
                "stops": dump(trip.stops),
                "city": trip.city,
                "center": trip.center,
            },
        )
        how = "araçla" if mode == "arac" else "yürüyerek"
        async for ev in self._text(f"Tamam, aynı durakları {how} gezilecek şekilde yeniden hesapladım.", "intro"):
            yield ev
        async for ev in self._text("Başka bir değişiklik istersen yazman yeterli.", "outro"):
            yield ev
        yield "done", {"trip": trip.model_dump(mode="json")}

    def _cached_trip(self, intent: Intent) -> TripRecord | None:
        trip_id = self.cache.get("trip_by_intent", intent_key(intent))
        return self.load_trip(trip_id) if trip_id else None

    async def _replay(self, record: TripRecord) -> AsyncIterator[Event]:
        trip = record.trip
        yield "places_found", {"count": trip.candidates_count, "source": trip.sources.get("places")}
        yield "stops_selected", {"stops": dump(trip.stops), "source": trip.sources.get("stops")}
        yield (
            "route_ready",
            {
                "route": trip.route.model_dump(mode="json"),
                "stops": dump(trip.stops),
                "city": trip.city,
                "center": trip.center,
            },
        )
        async for ev in self._text(trip.intro, "intro"):
            yield ev
        async for ev in self._text(trip.outro, "outro"):
            yield ev
        yield "done", {"trip": trip.model_dump(mode="json")}

    async def _text(self, text: str, part: str) -> AsyncIterator[Event]:
        for chunk in re.findall(r"\S+\s*", text):
            yield "text_delta", {"text": chunk, "part": part}
            if self.text_delay:
                await asyncio.sleep(self.text_delay)

    def _save(self, record: TripRecord, *, by_intent: bool) -> None:
        self.cache.set("trip", record.trip.id, record.model_dump(mode="json"), ttl=TRIP_TTL)
        if by_intent:
            self.cache.set("trip_by_intent", intent_key(record.trip.intent), record.trip.id, ttl=TRIP_TTL)

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex[:12]

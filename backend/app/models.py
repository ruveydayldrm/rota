"""Rota'nın tüm veri modelleri.

LLM'den gelen her çıktı burada tanımlı modellerle doğrulanır; doğrulanamayan
çıktı sisteme hiç girmez.
"""

from __future__ import annotations

import re
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator

Mode = Literal["yuruyus", "arac"]
Duration = Literal["yarim_gun", "1_gun", "2_gun"]
Interest = Literal[
    "tarih",
    "muze",
    "dini",
    "mimari",
    "park",
    "doga",
    "manzara",
    "yemek",
    "kahve",
    "sanat",
    "alisveris",
]
INTERESTS: tuple[str, ...] = get_args(Interest)
DURATIONS: tuple[str, ...] = get_args(Duration)
MODES: tuple[str, ...] = get_args(Mode)

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def clean_interests(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["tarih"]
    seen: list[str] = []
    for item in value:
        key = str(item).strip().lower()
        if key in INTERESTS and key not in seen:
            seen.append(key)
    return seen[:6] or ["tarih"]


def clean_time(value: Any) -> str | None:
    if isinstance(value, str) and _HHMM.match(value.strip()):
        return value.strip()
    return None


def clean_wishes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(x).strip()[:120] for x in value if str(x).strip()]
    return items[:6]


class Intent(BaseModel):
    """Kullanıcı isteğinin yapılandırılmış hali."""

    sehir: str = Field(min_length=1, max_length=80)
    ilce: str | None = Field(default=None, max_length=80)
    ilgi: list[Interest] = Field(default_factory=lambda: ["tarih"])
    sure: Duration = "1_gun"
    mod: Mode = "yuruyus"
    baslangic_saati: str | None = None
    ozel_istekler: list[str] = Field(default_factory=list)

    @field_validator("sehir", mode="before")
    @classmethod
    def _sehir(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("ilce", mode="before")
    @classmethod
    def _ilce(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("ilgi", mode="before")
    @classmethod
    def _ilgi(cls, v: Any) -> list[str]:
        return clean_interests(v)

    @field_validator("baslangic_saati", mode="before")
    @classmethod
    def _saat(cls, v: Any) -> str | None:
        return clean_time(v)

    @field_validator("ozel_istekler", mode="before")
    @classmethod
    def _istekler(cls, v: Any) -> list[str]:
        return clean_wishes(v)


class IntentParse(BaseModel):
    """Niyet çıkarma adımında LLM'in döndürdüğü ham yapı."""

    sehir: str | None = None
    ilce: str | None = None
    ilgi: list[str] = Field(default_factory=list)
    sure: Duration = "1_gun"
    mod: Mode = "yuruyus"
    baslangic_saati: str | None = None
    ozel_istekler: list[str] = Field(default_factory=list)
    soru: str | None = Field(default=None, max_length=300)
    tur: Literal["yeni", "duzenle"] = "yeni"
    yalnizca_mod: bool = False

    @field_validator("sure", mode="before")
    @classmethod
    def _sure(cls, v: Any) -> Any:
        return v if v in DURATIONS else "1_gun"

    @field_validator("mod", mode="before")
    @classmethod
    def _mod(cls, v: Any) -> Any:
        return v if v in MODES else "yuruyus"

    @field_validator("tur", mode="before")
    @classmethod
    def _tur(cls, v: Any) -> Any:
        return v if v in ("yeni", "duzenle") else "yeni"

    def to_intent(self) -> Intent | None:
        if not self.sehir or not self.sehir.strip():
            return None
        return Intent(
            sehir=self.sehir,
            ilce=self.ilce,
            ilgi=self.ilgi,  # type: ignore[arg-type]
            sure=self.sure,
            mod=self.mod,
            baslangic_saati=self.baslangic_saati,
            ozel_istekler=self.ozel_istekler,
        )


class Place(BaseModel):
    """OpenStreetMap'ten gelen gerçek bir mekan. Kimlik: n123 / w456 / r789."""

    id: str
    name: str
    lat: float
    lon: float
    category: str
    tags: dict[str, str] = Field(default_factory=dict)
    tag_count: int = 0
    importance: float = 0.0  # Nominatim'in Wikipedia tabanlı ünlülük ölçüsü (0-1); Overpass'ta yok
    score: float = 0.0
    source: Literal["overpass", "nominatim"] = "overpass"


class WikiInfo(BaseModel):
    extract: str | None = None
    image: str | None = None
    url: str | None = None


class Stop(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    category: str
    time: str = ""
    tip: str = ""
    wiki: WikiInfo | None = None

    @classmethod
    def from_place(cls, place: Place, *, tip: str, time: str = "", wiki: WikiInfo | None = None) -> Stop:
        return cls(
            id=place.id,
            name=place.name,
            lat=place.lat,
            lon=place.lon,
            category=place.category,
            tip=tip,
            time=time,
            wiki=wiki,
        )


class Route(BaseModel):
    geometry: list[list[float]]  # [lon, lat] çiftleri
    distance_km: float
    duration_min: float
    mode: Mode
    source: Literal["osrm", "ors", "straight"]
    legs_min: list[float] = Field(default_factory=list)


class Trip(BaseModel):
    id: str
    city: str
    center: list[float]  # [lon, lat]
    intent: Intent
    stops: list[Stop]
    route: Route
    intro: str = ""
    outro: str = ""
    candidates_count: int = 0
    # Her adımı gerçekte hangi kaynağın yaptığı: {"intent": "LLM"|"kurallar", "places": ..., "stops": ...}
    sources: dict[str, str] = Field(default_factory=dict)


class TripRecord(BaseModel):
    """Sunucuda saklanan rota; takip mesajları yalnızca bu güvenilir kayıt üzerinden çalışır."""

    trip: Trip
    candidates: list[Place] = Field(default_factory=list)


class GeoArea(BaseModel):
    name: str
    lat: float
    lon: float
    bbox: tuple[float, float, float, float] | None = None  # güney, batı, kuzey, doğu


# --- LLM seçim çıktısı -------------------------------------------------------


class Pick(BaseModel):
    id: str
    saat: str = ""
    ipucu: str = ""

    @field_validator("ipucu", mode="before")
    @classmethod
    def _ipucu(cls, v: Any) -> str:
        return str(v or "").strip()[:180]


class Selection(BaseModel):
    secilen: list[Pick] = Field(default_factory=list)
    giris: str = ""
    kapanis: str = ""

    @field_validator("giris", "kapanis", mode="before")
    @classmethod
    def _metin(cls, v: Any) -> str:
        return str(v or "").strip()[:420]


# --- API istekleri -----------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    trip_id: str | None = Field(default=None, max_length=40)
    context: Intent | None = None


class RouteRequest(BaseModel):
    trip_id: str = Field(min_length=1, max_length=40)
    mode: Mode

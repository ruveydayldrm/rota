"""Demo modu verisini GERÇEK servislerden üretir.

Her durak Nominatim (ya da Overpass) ile gerçek bir OSM kaydına oturtulur, Wikipedia özeti ve
Commons fotoğrafı eklenir, yürüyüş ve araç için OSRM yol geometrileri hesaplanır.
Çıktı: frontend/src/lib/demo/data/<şehir>.json

Kullanım (backend klasöründen):  python scripts/build_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cache.store import Cache  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.geo import haversine_km  # noqa: E402
from app.models import Intent, Place  # noqa: E402
from app.pipeline.candidates import rank_pool  # noqa: E402
from app.pipeline.orchestrator import search_radius_m  # noqa: E402
from app.providers.osm.overpass import OverpassService  # noqa: E402
from app.providers.routing.router import OSRMProvider, RoutingError  # noqa: E402
from app.providers.wiki.wikipedia import WikiService  # noqa: E402

OUT = ROOT.parent / "frontend" / "src" / "lib" / "demo" / "data"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"

CITIES: list[dict[str, Any]] = [
    {
        "key": "istanbul",
        "city": "İstanbul",
        "suffix": "İstanbul",
        "keywords": ["istanbul", "sultanahmet", "eminönü", "galata", "beyoğlu"],
        "intent": {
            "sehir": "İstanbul",
            "ilgi": ["tarih", "mimari"],
            "sure": "1_gun",
            "mod": "yuruyus",
            "baslangic_saati": "09:00",
            "ozel_istekler": [],
        },
        "intro": "Tarihi yarımadada, birbirine yürüme mesafesindeki saray, cami ve sarnıçlarla dolu bir gün "
        "kurdum. Sabah erken başlarsan kalabalıkların önüne geçersin.",
        "outro": "Gün batımını Haliç'in karşı yakasında karşılıyorsun. İstersen öğle yemeğini değiştirebilir "
        "ya da rotayı araçla yeniden hesaplayabilirim.",
        "stops": [
            (
                "Topkapı Sarayı",
                41.0115,
                28.9834,
                "muze",
                "Harem için ayrı bilet gerekir; açılışta girersen avlular sakin olur.",
            ),
            (
                "Ayasofya",
                41.0086,
                28.9802,
                "cami",
                "Ziyaretçi girişi yan kapıdan; namaz vakitlerinde kısa aralar verilir.",
            ),
            ("Yerebatan Sarnıcı", 41.0084, 28.9779, "tarih", "İçerisi serin ve loş; Medusa başlarını sona bırak."),
            (
                "Tarihi Sultanahmet Köftecisi",
                41.0082,
                28.9761,
                "restoran",
                "Menü kısa ve net: köfte, piyaz, irmik helvası. Öğleden önce kuyruk kısadır.",
            ),
            (
                "Sultanahmet Camii",
                41.0054,
                28.9768,
                "cami",
                "Avludan gir; omuz ve dizlerin kapalı olsun, ayakkabılar poşete.",
            ),
            ("Kapalıçarşı", 41.0107, 28.9680, "carsi", "Nuruosmaniye Kapısı'ndan gir; pazarlık beklenir."),
            (
                "Süleymaniye Camii",
                41.0162,
                28.9639,
                "cami",
                "Arka bahçedeki teras Haliç'e bakan en güzel noktalardan biri.",
            ),
            (
                "Galata Kulesi",
                41.0256,
                28.9742,
                "tarih",
                "Gün batımına yakın çık; köprüden yürüyerek yaklaşık 20 dakika.",
            ),
        ],
        "lunch_alt": (
            "Pudding Shop",
            41.0089,
            28.9765,
            "restoran",
            "1957'den beri yolcuların buluşma noktası; yemekler vitrinden seçilir.",
        ),
    },
    {
        "key": "kapadokya",
        "city": "Kapadokya",
        "suffix": "Nevşehir",
        "keywords": ["kapadokya", "göreme", "nevşehir", "ürgüp", "uçhisar", "avanos", "cappadocia"],
        "intent": {
            "sehir": "Kapadokya",
            "ilgi": ["tarih", "manzara", "doga"],
            "sure": "1_gun",
            "mod": "arac",
            "baslangic_saati": "08:30",
            "ozel_istekler": ["gün batımı"],
        },
        "intro": "Peribacaları, kaya kiliseleri ve vadiler arasında, gün batımında biten bir araç rotası "
        "hazırladım. Duraklar arası sürüşler kısa; çoğu zamanı yürüyerek keşfe ayırabilirsin.",
        "outro": "Son durakta güneşi vadilerin üzerinde batırıyorsun. Bir vadiyi çıkarmamı ya da öğle "
        "yemeğini değiştirmemi istersen söylemen yeterli.",
        "stops": [
            (
                "Göreme Açık Hava Müzesi",
                38.6397,
                34.8458,
                "muze",
                "Karanlık Kilise ayrı biletli; tur otobüsleri gelmeden, açılışta gir.",
            ),
            ("Paşabağı", 38.6732, 34.8532, "doga", "Üç başlı peribacaları burada; patika kısa ve düz."),
            ("Zelve Açık Hava Müzesi", 38.6726, 34.8648, "muze", "Tüneller dar ve yer yer dik; rahat ayakkabı giy."),
            (
                "Usta'nın Yeri",
                38.71873,
                34.84667,
                "restoran",
                "Avanos'ta, Kızılırmak'a yakın öğle molası; çömlek atölyeleri birkaç adım ötede.",
            ),
            ("Devrent Vadisi", 38.6546, 34.8960, "doga", "Hayvan şekilli kayaları bul; yol kenarına park etmek kolay."),
            (
                "Uçhisar Kalesi",
                38.6304,
                34.8051,
                "tarih",
                "Basamaklar dik ama zirvedeki manzara Erciyes'e kadar uzanır.",
            ),
            (
                "Güvercinlik Vadisi",
                38.6340,
                34.8155,
                "manzara",
                "Seyir terasından vadinin tamamını görürsün; kısa bir mola yeter.",
            ),
            (
                "Kızılçukur Vadisi",
                38.65099,
                34.85359,
                "manzara",
                "Gün batımından 30 dakika önce orada ol; kırmızı kayalar son ışıkta parlar.",
            ),
        ],
        "lunch_alt": (
            "Kale Terasse",
            38.64259,
            34.82955,
            "restoran",
            "Göreme merkezde, kasabaya bakan terasta öğle yemeği.",
        ),
    },
    {
        "key": "mardin",
        "city": "Mardin",
        "suffix": "Mardin",
        "keywords": ["mardin", "midyat", "artuklu"],
        "intent": {
            "sehir": "Mardin",
            "ilgi": ["tarih", "mimari", "manzara"],
            "sure": "1_gun",
            "mod": "yuruyus",
            "baslangic_saati": "09:00",
            "ozel_istekler": ["taş sokaklar"],
        },
        "intro": "Taş sokaklarda, medreseler ve kiliseler arasında Mezopotamya ovasına bakarak geçen bir "
        "yürüyüş günü hazırladım. Yokuşlar dik; acele etme.",
        "outro": "Günü bir medrese terasında, ovanın üzerine çöken akşamla bitiriyorsun. İstersen bir durağı "
        "çıkarabilir ya da rotayı araçla hesaplayabilirim.",
        "stops": [
            (
                "Kasımiye Medresesi",
                37.3071,
                40.7249,
                "tarih",
                "Şehrin biraz aşağısında; avludaki havuz sessizliğiyle meşhur.",
            ),
            ("Kırklar Kilisesi", 37.3108, 40.7316, "kilise", "Hâlâ ibadete açık; sessiz ol, fotoğraf için izin iste."),
            (
                "Mardin Müzesi",
                37.3121,
                40.7338,
                "muze",
                "Eski Süryani Katolik Patrikhanesi binasında; avlusu serin bir mola.",
            ),
            ("Mardin Ulu Camii", 37.3114, 40.7362, "cami", "Yivli minaresini çarşının içinden de görebilirsin."),
            (
                "Cercis Murat Konağı",
                37.3133,
                40.7418,
                "restoran",
                "Mardin mutfağını tadım menüsüyle dene; teras için rezervasyon yap.",
            ),
            ("Şehidiye Camii", 37.3127, 40.7395, "cami", "İnce minaresi şehrin simgelerinden; avluya gölgede otur."),
            (
                "Tellallar Çarşısı",
                37.31334,
                40.74107,
                "carsi",
                "Tarihi çarşıda bıttım sabunu ve el yapımı bakır kaplara bak.",
            ),
            (
                "Zinciriye Medresesi",
                37.3141,
                40.7308,
                "tarih",
                "Terasından ovaya gün batımı; kapanış saatini kontrol et.",
            ),
        ],
        "lunch_alt": (
            "Bağdadi Restaurant",
            37.31367,
            40.73631,
            "restoran",
            "Çarşıya birkaç adım; yerel yemeklerle hızlı bir öğle molası.",
        ),
    },
]


class Resolver:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.used: set[str] = set()

    async def nominatim(self, name: str, suffix: str, lat: float, lon: float, max_km: float) -> Place | None:
        for query in (f"{name}, {suffix}", name):
            await asyncio.sleep(1.1)  # Nominatim kullanım kuralı: en fazla 1 istek/sn
            res = await self.client.get(
                NOMINATIM,
                params={"q": query, "format": "jsonv2", "limit": 8, "extratags": 1, "accept-language": "tr"},
            )
            for hit in res.json():
                hlat, hlon = float(hit["lat"]), float(hit["lon"])
                if haversine_km((lat, lon), (hlat, hlon)) > max_km:
                    continue
                pid = f"{hit['osm_type'][0]}{hit['osm_id']}"
                tags = {k: v for k, v in (hit.get("extratags") or {}).items() if k in ("wikidata", "wikipedia")}
                return Place(id=pid, name=name, lat=round(hlat, 6), lon=round(hlon, 6), category="", tags=tags)
        return None

    async def resolve(self, spec: tuple, suffix: str, max_km: float) -> tuple[dict[str, Any], Place]:
        name, lat, lon, category, tip = spec
        place = await self.nominatim(name, suffix, lat, lon, max_km)
        if place is None:
            raise SystemExit(f"{name} OSM'de doğrulanamadı; demo verisine uydurma mekan girmez.")
        self.used.add(place.id)
        stop = {
            "id": place.id,
            "name": place.name,
            "lat": place.lat,
            "lon": place.lon,
            "category": category,
            "tip": tip,
        }
        print(f"  ✓ {place.name:<38} {place.id:<14} {'wiki' if place.tags else ''}")
        return stop, place


async def build_city(cfg: dict[str, Any], client: httpx.AsyncClient, cache: Cache) -> dict[str, Any]:
    print(f"\n== {cfg['city']}")
    resolver = Resolver(client)
    max_km = 3.0 if cfg["intent"]["mod"] == "arac" else 1.2
    stops, places = [], []
    for spec in cfg["stops"]:
        stop, place = await resolver.resolve(spec, cfg["suffix"], max_km)
        stops.append(stop)
        places.append(place)
    alt_stop, alt_place = await resolver.resolve(cfg["lunch_alt"], cfg["suffix"], max_km)

    wiki = WikiService(client, cache, concurrency=2)
    infos = await wiki.enrich(places + [alt_place])
    for s in stops + [alt_stop]:
        info = infos.get(s["id"])
        s["wiki"] = info.model_dump() if info else None

    intent = Intent.model_validate(cfg["intent"])
    center_lat = sum(s["lat"] for s in stops) / len(stops)
    center_lon = sum(s["lon"] for s in stops) / len(stops)
    try:
        raw = await OverpassService(client, cache, [OVERPASS]).fetch(
            center_lat, center_lon, search_radius_m(intent), list(intent.ilgi)
        )
        candidates = len(rank_pool(raw, (center_lat, center_lon), search_radius_m(intent) / 1000, intent))
    except Exception as exc:  # demo sayısı için kritik değil
        print("  ! aday sayısı alınamadı:", exc)
        candidates = 32
    print(f"  aday havuzu: {candidates}")

    lunch_idx = next(i for i, s in enumerate(stops) if s["category"] == "restoran")
    pairs = {(a["id"], b["id"]) for a, b in zip(stops, stops[1:])}
    pairs |= {(a["id"], c["id"]) for a, c in zip(stops, stops[2:])}
    if lunch_idx > 0:
        pairs.add((stops[lunch_idx - 1]["id"], alt_stop["id"]))
    if lunch_idx + 1 < len(stops):
        pairs.add((alt_stop["id"], stops[lunch_idx + 1]["id"]))
    by_id = {s["id"]: s for s in stops + [alt_stop]}

    settings = get_settings()
    osrm = OSRMProvider(client, settings.osrm_foot_url, settings.osrm_car_url)
    legs: dict[str, dict[str, Any]] = {"yuruyus": {}, "arac": {}}
    for mode in ("yuruyus", "arac"):
        for a, b in sorted(pairs):
            pa, pb = by_id[a], by_id[b]
            try:
                route = await osrm.route([(pa["lat"], pa["lon"]), (pb["lat"], pb["lon"])], mode)  # type: ignore[arg-type]
            except RoutingError as exc:
                print(f"  ! {mode} {a}>{b}: {exc}")
                continue
            legs[mode][f"{a}>{b}"] = {"g": route.geometry, "km": route.distance_km, "min": route.duration_min}
            await asyncio.sleep(0.4)
        print(f"  {mode}: {len(legs[mode])}/{len(pairs)} bacak")

    return {
        "key": cfg["key"],
        "city": cfg["city"],
        "center": [round(center_lon, 5), round(center_lat, 5)],
        "keywords": cfg["keywords"],
        "intent": intent.model_dump(),
        "start": intent.baslangic_saati or "09:00",
        "candidates_count": candidates,
        "intro": cfg["intro"],
        "outro": cfg["outro"],
        "stops": stops,
        "lunch_alt": alt_stop,
        "legs": legs,
    }


async def main() -> None:
    settings = get_settings()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = Cache(":memory:")
    async with httpx.AsyncClient(headers={"User-Agent": settings.user_agent}, timeout=40) as client:
        for cfg in CITIES:
            data = await build_city(cfg, client, cache)
            path = OUT / f"{cfg['key']}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"  → {path.name} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())

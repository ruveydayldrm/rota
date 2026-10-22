import httpx
import respx

from app.cache.store import Cache
from app.models import Place
from app.providers.osm.nominatim import NominatimService
from app.providers.osm.overpass import OverpassService, build_query, classify, parse_elements
from app.providers.routing.router import OSRMProvider, RoutingService
from app.providers.wiki.wikipedia import WikiService, shorten

OVERPASS = "https://overpass.test/api/interpreter"
OSRM_FOOT = "https://osrm.test/foot"


def test_classify():
    assert classify({"amenity": "place_of_worship", "religion": "muslim"}) == "cami"
    assert classify({"tourism": "museum"}) == "muze"
    assert classify({"amenity": "restaurant"}) == "restoran"
    assert classify({"historic": "castle"}) == "tarih"
    assert classify({"tourism": "attraction"}) == "turizm"


def test_query_uses_radius_and_interests():
    q = build_query(41.0, 29.0, 2500, ["manzara", "park"])
    assert "(around:2500,41.00000,29.00000)" in q
    assert '["tourism"="viewpoint"]' in q and '["leisure"~"^(park|garden)$"]' in q
    assert '["amenity"="restaurant"]' in q


def test_parse_elements_handles_ways_and_skips_nameless():
    places = parse_elements(
        [
            {
                "type": "way",
                "id": 5,
                "center": {"lat": 41.0, "lon": 29.0},
                "tags": {"name": "Ayasofya", "wikidata": "Q1"},
            },
            {"type": "node", "id": 6, "lat": 41.1, "lon": 29.1, "tags": {"amenity": "cafe"}},
        ]
    )
    assert [p.id for p in places] == ["w5"]
    assert places[0].tags == {"wikidata": "Q1"}


@respx.mock
async def test_overpass_is_cached():
    route = respx.post(OVERPASS).mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 41.0,
                        "lon": 29.0,
                        "tags": {"name": "Galata Kulesi", "tourism": "attraction"},
                    },
                ]
            },
        )
    )
    cache = Cache()
    async with httpx.AsyncClient() as client:
        service = OverpassService(client, cache, [OVERPASS])
        first = await service.fetch(41.0, 29.0, 2500, ["tarih"])
        second = await service.fetch(41.0, 29.0, 2500, ["tarih"])
    assert route.call_count == 1
    assert first == second and first[0].name == "Galata Kulesi"


@respx.mock
async def test_nominatim_uses_cache_and_user_agent():
    route = respx.get("https://nominatim.test/search").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"lat": "37.31", "lon": "40.73", "name": "Mardin", "boundingbox": ["37.2", "37.4", "40.6", "40.9"]},
            ],
        )
    )
    async with httpx.AsyncClient(headers={"User-Agent": "Rota/test"}) as client:
        service = NominatimService(client, Cache(), "https://nominatim.test", min_interval=0)
        area = await service.geocode("Mardin")
        again = await service.geocode("mardin")
    assert route.call_count == 1
    assert area == again and area is not None
    assert area.bbox == (37.2, 40.6, 37.4, 40.9)
    assert route.calls.last.request.headers["user-agent"] == "Rota/test"


@respx.mock
async def test_routing_falls_back_to_straight_line():
    respx.get(url__startswith=OSRM_FOOT).mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as client:
        service = RoutingService([OSRMProvider(client, OSRM_FOOT, "https://osrm.test/car")], Cache())
        route = await service.route([(41.0, 29.0), (41.01, 29.01), (41.02, 29.0)], "yuruyus")
    assert route.source == "straight"
    assert len(route.geometry) == 3 and len(route.legs_min) == 2
    assert route.distance_km > 0


@respx.mock
async def test_osrm_success():
    respx.get(url__startswith=OSRM_FOOT).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 1500,
                        "duration": 1200,
                        "geometry": {"coordinates": [[29.0, 41.0], [29.01, 41.01]]},
                        "legs": [{"duration": 1200}],
                    }
                ],
            },
        )
    )
    async with httpx.AsyncClient() as client:
        route = await OSRMProvider(client, OSRM_FOOT, "x").route([(41.0, 29.0), (41.01, 29.01)], "yuruyus")
    assert (route.source, route.distance_km, route.duration_min, route.legs_min) == ("osrm", 1.5, 20.0, [20.0])


@respx.mock
async def test_wiki_lookup_via_wikidata():
    respx.get("https://www.wikidata.org/w/api.php").mock(
        return_value=httpx.Response(
            200,
            json={
                "entities": {
                    "Q12506": {
                        "sitelinks": {"trwiki": {"title": "Ayasofya"}},
                        "claims": {"P18": [{"mainsnak": {"datavalue": {"value": "Hagia Sophia.jpg"}}}]},
                    }
                }
            },
        )
    )
    respx.get("https://tr.wikipedia.org/api/rest_v1/page/summary/Ayasofya").mock(
        return_value=httpx.Response(
            200,
            json={
                "extract": "Ayasofya, İstanbul'da bir camidir.",
                "content_urls": {"desktop": {"page": "https://tr.wikipedia.org/wiki/Ayasofya"}},
            },
        )
    )
    place = Place(id="w1", name="Ayasofya", lat=41.0, lon=28.98, category="cami", tags={"wikidata": "Q12506"})
    async with httpx.AsyncClient() as client:
        info = await WikiService(client, Cache()).lookup(place)
    assert info is not None
    assert info.extract == "Ayasofya, İstanbul'da bir camidir."
    assert info.image and "Hagia_Sophia.jpg" in info.image
    assert info.url == "https://tr.wikipedia.org/wiki/Ayasofya"


def test_shorten_cuts_at_sentence():
    text = "Birinci cümle burada. " * 30
    out = shorten(text, 60)
    assert out is not None and out.endswith(".") and len(out) <= 60

import httpx
import pytest
import respx

from app.cache.store import Cache
from app.models import Intent, Stop
from app.pipeline.rules import find_city, rule_parse
from app.pipeline.select import deterministic_selection, mentioned
from app.providers.osm.chain import PlaceSourceChain
from app.providers.osm.nominatim import NominatimService
from app.providers.osm.overpass import OverpassError

from .conftest import PLACES


@pytest.mark.parametrize(
    ("message", "city"),
    [
        ("ankara", "Ankara"),
        ("İzmir'de kahve ve deniz", "İzmir"),
        ("Safranbolu'da yarım gün", "Safranbolu"),
        ("ISPARTA", "Isparta"),
        ("Eskişehirde bir gün", "Eskişehir"),
    ],
)
def test_find_city(message, city):
    assert find_city(message) == city


def test_rule_parse_extracts_fields():
    parse = rule_parse("Kapadokya'da gün batımına kadar araçla, 08:30'da başla")
    intent = parse.to_intent()
    assert intent is not None
    assert (intent.sehir, intent.mod, intent.baslangic_saati) == ("Kapadokya", "arac", "08:30")
    assert "manzara" in intent.ilgi and intent.ozel_istekler == ["gün batımı"]


def test_rule_parse_unknown_short_message_is_tried_as_place():
    assert rule_parse("Hasankeyf").sehir == "Hasankeyf"
    assert rule_parse("Şile'de").sehir == "Şile"


def test_rule_parse_asks_when_no_city():
    parse = rule_parse("bana güzel bir gezi planı yapar mısın lütfen")
    assert parse.sehir is None and parse.soru


def test_rule_parse_follow_up_mode_only():
    previous = Intent(sehir="Mardin", ilgi=["tarih"])
    parse = rule_parse("araçla olsun", previous)
    assert (parse.sehir, parse.tur, parse.yalnizca_mod, parse.mod) == ("Mardin", "duzenle", True, "arac")
    assert rule_parse("Ulu Cami olmasın, araçla", previous).yalnizca_mod is False


def test_mentioned_ignores_generic_words_and_suffixes():
    low = "topkapı'yı çıkar"
    assert mentioned("Topkapı Sarayı", low)
    assert not mentioned("Sultanahmet Camii", "camii olmasın")


def test_deterministic_selection_is_diverse_and_handles_lunch_swap():
    intent = Intent(sehir="İstanbul")
    result = deterministic_selection(PLACES, intent, None)
    cats = [p.category for p in result.places]
    assert all(cats.count(c) <= 3 for c in cats)
    current = [Stop.from_place(p, tip="") for p in result.places]
    swapped = deterministic_selection(
        PLACES + [PLACES[7].model_copy(update={"id": "n10", "name": "Pudding Shop"})],
        intent,
        current,
        "öğle yemeğini değiştir",
    )
    assert "n10" in [p.id for p in swapped.places] and "n8" not in [p.id for p in swapped.places]


class Failing:
    calls = 0

    async def fetch(self, *args):
        Failing.calls += 1
        raise OverpassError("504")


class Working:
    async def fetch(self, *args):
        return PLACES


async def test_chain_falls_back_and_skips_recently_failed_source():
    Failing.calls = 0
    chain = PlaceSourceChain([Failing(), Working()])
    assert await chain.fetch(41.0, 29.0, 2500, ["tarih"]) == PLACES
    assert await chain.fetch(41.0, 29.0, 2500, ["tarih"]) == PLACES
    assert Failing.calls == 1


async def test_chain_raises_when_everything_fails():
    with pytest.raises(OverpassError):
        await PlaceSourceChain([Failing(), Failing()], cooldown_s=0).fetch(41.0, 29.0, 2500, [])


@respx.mock
async def test_nominatim_places_filters_and_classifies():
    respx.get("https://nominatim.test/search").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "osm_type": "way",
                    "osm_id": 1,
                    "name": "Anadolu Medeniyetleri Müzesi",
                    "category": "tourism",
                    "type": "museum",
                    "lat": "39.938",
                    "lon": "32.862",
                    "extratags": {"wikidata": "Q1"},
                },
                {
                    "osm_type": "node",
                    "osm_id": 2,
                    "name": "Future Mosque",
                    "category": "natural",
                    "type": "wood",
                    "lat": "39.9",
                    "lon": "32.8",
                },
                {
                    "osm_type": "node",
                    "osm_id": 3,
                    "name": "",
                    "category": "tourism",
                    "type": "museum",
                    "lat": "39.9",
                    "lon": "32.8",
                },
            ],
        )
    )
    async with httpx.AsyncClient() as client:
        service = NominatimService(client, Cache(), "https://nominatim.test", min_interval=0)
        places = await service.fetch(39.92, 32.85, 2500, ["dini"])
    assert [p.id for p in places] == ["w1"]
    assert places[0].category == "muze" and places[0].tags["wikidata"] == "Q1"

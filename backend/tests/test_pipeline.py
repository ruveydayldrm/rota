from app.models import ChatRequest

from .conftest import INTENT_ISTANBUL, PLACES, SELECTION_OK, collect, make_pipeline

REAL_IDS = {p.id for p in PLACES}


async def test_full_pipeline_emits_events_in_order(cache):
    pipeline, llm, deps = make_pipeline([INTENT_ISTANBUL, SELECTION_OK], cache)
    events = await collect(pipeline, ChatRequest(message="İstanbul'da tarih dolu bir gün"))
    names = [e for e, _ in events]

    assert names[:4] == ["intent_parsed", "places_found", "stops_selected", "route_ready"]
    assert names[-1] == "done"
    assert "text_delta" in names and "error" not in names

    trip = events[-1][1]["trip"]
    ids = [s["id"] for s in trip["stops"]]
    assert "n999999" not in ids
    assert set(ids) <= REAL_IDS
    assert ids[0] == "r4"
    assert trip["intro"].startswith("Tarihi yarımadada")
    assert trip["stops"][0]["wiki"]["extract"]
    assert len(llm.calls) == 2


async def test_same_request_is_served_from_cache_without_llm(cache):
    pipeline, llm, deps = make_pipeline([INTENT_ISTANBUL, SELECTION_OK], cache)
    first = await collect(pipeline, ChatRequest(message="İstanbul'da tarih dolu bir gün"))
    second = await collect(pipeline, ChatRequest(message="  istanbul'da TARİH dolu bir gün "))
    assert len(llm.calls) == 2
    assert deps["places"].calls == 1
    assert second[-1][1]["trip"]["id"] == first[-1][1]["trip"]["id"]


async def test_unclear_city_asks_a_question(cache):
    question = {**INTENT_ISTANBUL, "sehir": None, "soru": "Hangi şehirde gezmek istersin?"}
    pipeline, _, _ = make_pipeline([question], cache)
    events = await collect(pipeline, ChatRequest(message="güzel bir gün planla"))
    assert events[0] == ("intent_parsed", {"intent": None, "source": "LLM"})
    text = "".join(d["text"] for e, d in events if e == "text_delta")
    assert text == "Hangi şehirde gezmek istersin?"
    assert events[-1] == ("done", {"trip": None})


async def test_unknown_place_gives_human_error(cache):
    pipeline, _, _ = make_pipeline([{**INTENT_ISTANBUL, "sehir": "Atlantis"}], cache)
    events = await collect(pipeline, ChatRequest(message="Atlantis'te bir gün"))
    assert events[-1][0] == "error"
    assert "Atlantis" in events[-1][1]["message"]


async def test_without_llm_rules_still_build_a_real_route(cache):
    pipeline, _, deps = make_pipeline([], cache)
    events = await collect(pipeline, ChatRequest(message="Ankara'da müze ve tarih, yarım gün"))
    assert events[0][1]["intent"]["sehir"] == "Ankara"
    assert events[0][1]["source"] == "kurallar"
    assert dict(events)["stops_selected"]["source"] == "kurallar"
    assert events[0][1]["intent"]["sure"] == "yarim_gun"
    trip = events[-1][1]["trip"]
    assert trip and set(s["id"] for s in trip["stops"]) <= REAL_IDS
    assert deps["geocoder"].queries == ["Ankara"]


async def test_without_llm_follow_up_removes_named_stop(cache):
    pipeline, _, _ = make_pipeline([], cache)
    first = (await collect(pipeline, ChatRequest(message="İstanbul'da bir gün")))[-1][1]["trip"]
    target = next(s for s in first["stops"] if s["name"] == "Ayasofya")
    events = await collect(pipeline, ChatRequest(message="Ayasofya olmasın", trip_id=first["id"]))
    ids = [s["id"] for s in events[-1][1]["trip"]["stops"]]
    assert target["id"] not in ids and len(ids) == len(first["stops"]) - 1


async def test_mode_only_follow_up_reuses_stops(cache):
    edit = {**INTENT_ISTANBUL, "mod": "arac", "tur": "duzenle", "yalnizca_mod": True}
    pipeline, llm, deps = make_pipeline([INTENT_ISTANBUL, SELECTION_OK, edit], cache)
    first = (await collect(pipeline, ChatRequest(message="İstanbul tarih")))[-1][1]["trip"]
    events = await collect(pipeline, ChatRequest(message="araçla olsun", trip_id=first["id"]))
    trip = events[-1][1]["trip"]
    assert [s["id"] for s in trip["stops"]] == [s["id"] for s in first["stops"]]
    assert trip["route"]["mode"] == "arac"
    assert trip["id"] != first["id"]
    assert len(llm.calls) == 3
    assert "ÖNCEKİ NİYET" in llm.calls[2]["user"]


async def test_edit_follow_up_removes_a_stop(cache):
    edit = {**INTENT_ISTANBUL, "tur": "duzenle"}
    without_topkapi = {**SELECTION_OK, "secilen": [p for p in SELECTION_OK["secilen"] if p["id"] != "r4"]}
    pipeline, llm, _ = make_pipeline([INTENT_ISTANBUL, SELECTION_OK, edit, without_topkapi], cache)
    first = (await collect(pipeline, ChatRequest(message="İstanbul tarih")))[-1][1]["trip"]
    events = await collect(pipeline, ChatRequest(message="Topkapı'yı çıkar", trip_id=first["id"]))
    ids = [s["id"] for s in events[-1][1]["trip"]["stops"]]
    assert "r4" not in ids
    assert "MEVCUT ROTA" in llm.calls[3]["user"]

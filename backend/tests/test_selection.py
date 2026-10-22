from app.models import Intent, Pick
from app.pipeline.select import select_stops, validate_picks
from app.providers.llm.fallback import FallbackLLM

from .conftest import PLACES, SELECTION_OK, SULTANAHMET, ScriptedLLM

BY_ID = {p.id: p for p in PLACES}
INTENT = Intent(sehir="İstanbul", ilgi=["tarih"])


def test_hallucinated_ids_are_dropped():
    picks = [Pick(id="w1"), Pick(id="n999999"), Pick(id=" n3 "), Pick(id="w1"), Pick(id="Galata Kulesi")]
    valid = validate_picks(picks, BY_ID, max_n=8)
    assert [p.id for p in valid] == ["w1", "n3"]


def test_picks_are_capped():
    picks = [Pick(id=p.id) for p in PLACES]
    assert len(validate_picks(picks, BY_ID, max_n=5)) == 5


async def test_selection_keeps_only_real_candidates():
    llm = ScriptedLLM([SELECTION_OK])
    result = await select_stops(FallbackLLM([llm]), INTENT, PLACES, "tarih dolu bir gün", SULTANAHMET)
    ids = [p.id for p in result.places]
    assert "n999999" not in ids
    assert set(ids) <= set(BY_ID)
    assert result.used_llm
    assert result.anchor_id == "r4"


async def test_selection_prompt_contains_only_candidate_ids():
    llm = ScriptedLLM([SELECTION_OK])
    await select_stops(FallbackLLM([llm]), INTENT, PLACES, "tarih", SULTANAHMET)
    prompt = llm.calls[0]["user"]
    for place in PLACES:
        assert place.id in prompt
    assert "<mesaj>" in prompt
    assert "YALNIZCA ADAYLAR" in llm.calls[0]["system"]


async def test_all_fake_ids_fall_back_to_rule_based_selection():
    fake = {
        "secilen": [{"id": "x1", "saat": "09:00", "ipucu": "?"}, {"id": "x2", "saat": "10:00", "ipucu": "?"}],
        "giris": "",
        "kapanis": "",
    }
    result = await select_stops(FallbackLLM([ScriptedLLM([fake])]), INTENT, PLACES, "tarih", SULTANAHMET)
    assert not result.used_llm
    assert len(result.places) >= 3
    assert all(p.id in BY_ID for p in result.places)
    assert any(p.category == "restoran" for p in result.places)


async def test_no_llm_available_still_returns_real_places():
    result = await select_stops(FallbackLLM([]), INTENT, PLACES, "tarih", SULTANAHMET)
    assert not result.used_llm
    assert all(p.id in BY_ID for p in result.places)

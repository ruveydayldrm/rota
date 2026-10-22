import httpx
import pytest
import respx

from app.models import IntentParse
from app.pipeline.intent import INTENT_SCHEMA
from app.providers.llm.base import LLMError, LLMRateLimited, LLMUnavailable
from app.providers.llm.fallback import FallbackLLM
from app.providers.llm.gemini import GEMINI_URL, GeminiProvider
from app.providers.llm.openai_compat import GROQ_BASE_URL, groq_provider

from .conftest import INTENT_ISTANBUL, ScriptedLLM

GEMINI = GEMINI_URL.format(model="gemini-test")
GROQ = GROQ_BASE_URL + "/chat/completions"


async def generate(llm: FallbackLLM) -> IntentParse:
    return await llm.generate_model(system="s", user="u", schema=INTENT_SCHEMA, model=IntentParse)


async def test_falls_back_when_first_provider_is_rate_limited():
    first = ScriptedLLM([LLMRateLimited("429")], name="gemini")
    second = ScriptedLLM([INTENT_ISTANBUL], name="groq")
    result = await generate(FallbackLLM([first, second]))
    assert result.sehir == "İstanbul"
    assert len(first.calls) == 1 and len(second.calls) == 1


async def test_falls_back_on_schema_violation():
    first = ScriptedLLM([{"sehir": 42, "ilgi": "hepsi"}], name="gemini")
    second = ScriptedLLM([INTENT_ISTANBUL], name="groq")
    assert (await generate(FallbackLLM([first, second]))).sehir == "İstanbul"


async def test_raises_when_every_provider_fails():
    llm = FallbackLLM([ScriptedLLM([LLMError("x")]), ScriptedLLM([LLMRateLimited("y")])])
    with pytest.raises(LLMUnavailable):
        await generate(llm)


@respx.mock
async def test_gemini_429_triggers_groq_over_http():
    respx.post(GEMINI).mock(return_value=httpx.Response(429, json={"error": {"code": 429}}))
    groq_route = respx.post(GROQ).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"sehir": "Mardin", "ilgi": ["tarih"], "sure": "yarim_gun",'
                            ' "mod": "yuruyus", "ozel_istekler": [], "tur": "yeni",'
                            ' "yalnizca_mod": false}'
                        }
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        llm = FallbackLLM([GeminiProvider(client, "k", "gemini-test"), groq_provider(client, "k", "llama")])
        result = await generate(llm)
    assert result.sehir == "Mardin"
    assert groq_route.called
    sent = groq_route.calls.last.request
    assert sent.headers["authorization"] == "Bearer k"


@respx.mock
async def test_gemini_parses_json_and_sends_system_separately():
    route = respx.post(GEMINI).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": '```json\n{"sehir": "İzmir"}\n```'}]}}]}
        )
    )
    async with httpx.AsyncClient() as client:
        data = await GeminiProvider(client, "k", "gemini-test").generate_json(system="SYS", user="USR", schema={})
    assert data == {"sehir": "İzmir"}
    body = route.calls.last.request.content.decode()
    assert '"systemInstruction"' in body and "SYS" in body
    assert route.calls.last.request.headers["x-goog-api-key"] == "k"
    assert "key=" not in str(route.calls.last.request.url)

"""Google Gemini (AI Studio ücretsiz anahtarı) sağlayıcısı."""

from __future__ import annotations

from typing import Any

import httpx

from .base import LLMError, LLMProvider, LLMRateLimited, parse_json_object

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_DROP_KEYS = {"additionalProperties", "title", "$schema", "default"}


def to_gemini_schema(schema: Any) -> Any:
    """Standart JSON şemasını Gemini'nin OpenAPI alt kümesine çevirir."""
    if isinstance(schema, list):
        return [to_gemini_schema(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _DROP_KEYS:
            continue
        if key == "type":
            types = value if isinstance(value, list) else [value]
            concrete = [t for t in types if t != "null"]
            out["type"] = (concrete[0] if concrete else "string").upper()
            if "null" in types:
                out["nullable"] = True
        elif key == "properties":
            out[key] = {name: to_gemini_schema(sub) for name, sub in value.items()}
        else:
            out[key] = to_gemini_schema(value)
    return out


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str) -> None:
        self._client = client
        self._key = api_key
        self._model = model

    async def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "responseSchema": to_gemini_schema(schema),
            },
        }
        try:
            res = await self._client.post(
                GEMINI_URL.format(model=self._model),
                json=body,
                headers={"x-goog-api-key": self._key},
                timeout=40,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"gemini bağlantı hatası: {exc}") from exc
        if res.status_code == 429:
            raise LLMRateLimited("gemini kotası doldu")
        if res.status_code >= 400:
            raise LLMError(f"gemini HTTP {res.status_code}")
        try:
            parts = res.json()["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("gemini boş yanıt döndü") from exc
        return parse_json_object("".join(p.get("text", "") for p in parts))

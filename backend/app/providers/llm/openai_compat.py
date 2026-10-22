"""OpenAI uyumlu sohbet API'leri (Groq ve benzerleri) için sağlayıcı."""

from __future__ import annotations

import json
from typing import Any

import httpx

from .base import LLMError, LLMProvider, LLMRateLimited, parse_json_object

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, client: httpx.AsyncClient, *, name: str, base_url: str, api_key: str, model: str) -> None:
        self.name = name
        self._client = client
        self._url = base_url.rstrip("/") + "/chat/completions"
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
        system_with_schema = (
            f"{system}\n\nYanıtın yalnızca şu JSON şemasına uyan tek bir JSON nesnesi olmalı:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            res = await self._client.post(
                self._url,
                json=body,
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=40,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name} bağlantı hatası: {exc}") from exc
        if res.status_code == 429:
            raise LLMRateLimited(f"{self.name} kotası doldu")
        if res.status_code >= 400:
            raise LLMError(f"{self.name} HTTP {res.status_code}")
        try:
            content = res.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"{self.name} boş yanıt döndü") from exc
        return parse_json_object(content or "")


def groq_provider(client: httpx.AsyncClient, api_key: str, model: str) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(client, name="groq", base_url=GROQ_BASE_URL, api_key=api_key, model=model)

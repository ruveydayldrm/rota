"""Tüm LLM sağlayıcılarının uyduğu ortak arayüz."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


class LLMError(Exception):
    """Sağlayıcı geçerli bir yanıt veremedi."""


class LLMRateLimited(LLMError):
    """Sağlayıcının kotası doldu (HTTP 429)."""


class LLMUnavailable(LLMError):
    """Hiçbir sağlayıcı yanıt veremedi."""


class LLMProvider(ABC):
    name: str = "llm"

    @abstractmethod
    async def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Sistem talimatı ve kullanıcı içeriği ayrı tutularak şemaya uyan bir JSON nesnesi döndürür."""


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = _FENCE.sub("", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(f"JSON çözümlenemedi: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("JSON nesnesi bekleniyordu")
    return data

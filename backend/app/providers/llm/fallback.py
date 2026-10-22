"""Sağlayıcıları sırayla deneyen yedekli LLM istemcisi (Gemini → Groq → ...)."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .base import LLMError, LLMProvider, LLMUnavailable

log = logging.getLogger(__name__)
M = TypeVar("M", bound=BaseModel)


class FallbackLLM:
    def __init__(self, providers: list[LLMProvider]) -> None:
        self.providers = providers

    async def generate_model(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        model: type[M],
        temperature: float = 0.2,
    ) -> M:
        """Her sağlayıcıyı sırayla dener; kota, hata ya da şemaya uymayan çıktıda bir sonrakine geçer."""
        errors: list[str] = []
        for provider in self.providers:
            try:
                data = await provider.generate_json(system=system, user=user, schema=schema, temperature=temperature)
                return model.model_validate(data)
            except LLMError as exc:
                log.warning("LLM %s başarısız: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
            except ValidationError as exc:
                log.warning("LLM %s şemaya uymayan çıktı döndürdü: %s", provider.name, exc.error_count())
                errors.append(f"{provider.name}: şema hatası")
        raise LLMUnavailable("; ".join(errors) or "yapılandırılmış LLM sağlayıcısı yok")

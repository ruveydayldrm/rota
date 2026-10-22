from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ratelimit import RateLimiter
from app.api.routes import router
from app.cache.store import Cache
from app.config import Settings, get_settings
from app.pipeline.orchestrator import Pipeline
from app.providers.llm.base import LLMProvider
from app.providers.llm.fallback import FallbackLLM
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.openai_compat import groq_provider
from app.providers.osm.nominatim import NominatimService
from app.providers.osm.overpass import OverpassService
from app.providers.routing.router import ORSProvider, OSRMProvider, RoutingProvider, RoutingService
from app.providers.wiki.wikipedia import WikiService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rota")


def build_pipeline(settings: Settings, client: httpx.AsyncClient, cache: Cache) -> Pipeline:
    llms: list[LLMProvider] = []
    if settings.gemini_api_key:
        llms.append(GeminiProvider(client, settings.gemini_api_key, settings.gemini_model))
    if settings.groq_api_key:
        llms.append(groq_provider(client, settings.groq_api_key, settings.groq_model))
    if not llms:
        log.warning("Hiç LLM anahtarı yok: GEMINI_API_KEY veya GROQ_API_KEY tanımlayın.")

    routers: list[RoutingProvider] = [OSRMProvider(client, settings.osrm_foot_url, settings.osrm_car_url)]
    if settings.ors_api_key:
        routers.append(ORSProvider(client, settings.ors_api_key))

    return Pipeline(
        llm=FallbackLLM(llms),
        geocoder=NominatimService(client, cache, settings.nominatim_url),
        places=OverpassService(client, cache, settings.overpass_list),
        router=RoutingService(routers, cache),
        wiki=WikiService(client, cache),
        cache=cache,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client = httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent},
        timeout=settings.http_timeout,
        follow_redirects=True,
    )
    cache = Cache(settings.cache_path)
    cache.purge_expired()
    app.state.pipeline = build_pipeline(settings, client, cache)
    app.state.chat_limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.route_limiter = RateLimiter(settings.rate_limit_per_minute * 3)
    try:
        yield
    finally:
        await client.aclose()
        cache.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Rota API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    return app


app = create_app()

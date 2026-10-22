"""OSM'deki wikidata / wikipedia etiketinden Wikipedia özeti ve Commons fotoğrafı."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote

import httpx

from app.cache.store import DAY, Cache
from app.models import Place, WikiInfo

log = logging.getLogger(__name__)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SUMMARY_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
COMMONS_FILE = "https://commons.wikimedia.org/wiki/Special:FilePath/{file}?width=480"


def shorten(text: str | None, limit: int = 300) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for sentence in sentences:
        if len(out) + len(sentence) + 1 > limit:
            break
        out = f"{out} {sentence}".strip()
    return out or text[: limit - 1].rstrip() + "…"


class WikiService:
    def __init__(self, client: httpx.AsyncClient, cache: Cache, concurrency: int = 4) -> None:
        self._client = client
        self._cache = cache
        self._sem = asyncio.Semaphore(concurrency)

    async def enrich(self, places: list[Place]) -> dict[str, WikiInfo]:
        async def one(place: Place) -> tuple[str, WikiInfo | None]:
            async with self._sem:
                return place.id, await self.lookup(place)

        results = await asyncio.gather(*(one(p) for p in places))
        return {pid: info for pid, info in results if info}

    async def lookup(self, place: Place) -> WikiInfo | None:
        key = place.tags.get("wikidata") or place.tags.get("wikipedia")
        if not key:
            return None
        cached = self._cache.get("wiki", key)
        if cached is not None:
            return WikiInfo.model_validate(cached) if cached else None
        try:
            info = await self._fetch(place.tags)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.info("Wikipedia bilgisi alınamadı (%s): %s", key, exc)
            return None
        self._cache.set("wiki", key, info.model_dump() if info else {}, ttl=30 * DAY)
        return info

    async def _fetch(self, tags: dict[str, str]) -> WikiInfo | None:
        lang: str | None = None
        title: str | None = None
        image_file: str | None = None

        wp = tags.get("wikipedia")
        if wp and ":" in wp:
            lang, title = wp.split(":", 1)

        qid = tags.get("wikidata")
        if qid and re.fullmatch(r"Q\d+", qid):
            res = await self._client.get(
                WIKIDATA_API,
                params={
                    "action": "wbgetentities",
                    "ids": qid,
                    "props": "sitelinks|claims",
                    "sitefilter": "trwiki|enwiki",
                    "format": "json",
                },
                timeout=12,
            )
            entity = res.json().get("entities", {}).get(qid, {})
            links = entity.get("sitelinks", {})
            if "trwiki" in links:
                lang, title = "tr", links["trwiki"]["title"]
            elif not title and "enwiki" in links:
                lang, title = "en", links["enwiki"]["title"]
            p18 = entity.get("claims", {}).get("P18") or []
            if p18:
                image_file = p18[0].get("mainsnak", {}).get("datavalue", {}).get("value")

        commons = COMMONS_FILE.format(file=quote(image_file.replace(" ", "_"))) if image_file else None
        if not title or not lang:
            return WikiInfo(image=commons) if commons else None

        res = await self._client.get(
            SUMMARY_URL.format(lang=lang, title=quote(title.replace(" ", "_"), safe="")),
            timeout=12,
        )
        if res.status_code != 200:
            return WikiInfo(image=commons) if commons else None
        data = res.json()
        return WikiInfo(
            extract=shorten(data.get("extract")),
            image=(data.get("thumbnail") or {}).get("source") or commons,
            url=((data.get("content_urls") or {}).get("desktop") or {}).get("page"),
        )

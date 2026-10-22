from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.ratelimit import client_ip
from app.models import ChatRequest, RouteRequest, Trip
from app.pipeline.orchestrator import BUSY_MESSAGE, Pipeline

router = APIRouter()


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    pipeline: Pipeline = request.app.state.pipeline
    return {"ok": True, "llm": [p.name for p in pipeline.llm.providers]}


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    if not request.app.state.chat_limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail=BUSY_MESSAGE)
    pipeline: Pipeline = request.app.state.pipeline

    async def stream() -> AsyncIterator[str]:
        async for event, data in pipeline.run(body):
            yield format_sse(event, data)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/route", response_model=Trip)
async def reroute(body: RouteRequest, request: Request) -> Trip:
    if not request.app.state.route_limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail=BUSY_MESSAGE)
    pipeline: Pipeline = request.app.state.pipeline
    record = pipeline.load_trip(body.trip_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Bu rota artık önbellekte yok; isteğini yeniden yazar mısın?")
    updated = await pipeline.remode(record, body.mode)
    return updated.trip

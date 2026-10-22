from fastapi.testclient import TestClient

from app.api.ratelimit import RateLimiter
from app.main import create_app

from .conftest import INTENT_ISTANBUL, SELECTION_OK, make_pipeline


def make_client(cache, limit: int = 5) -> TestClient:
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    pipeline, _, _ = make_pipeline([INTENT_ISTANBUL, SELECTION_OK], cache)
    app.state.pipeline = pipeline
    app.state.chat_limiter = RateLimiter(limit)
    app.state.route_limiter = RateLimiter(limit)
    return client


def test_chat_streams_server_sent_events(cache):
    client = make_client(cache)
    res = client.post("/api/chat", json={"message": "İstanbul'da tarih dolu bir gün"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert "event: intent_parsed\ndata: " in res.text
    assert res.text.index("event: route_ready") < res.text.index("event: done")
    assert "İstanbul" in res.text  # ensure_ascii=False


def test_rate_limit_returns_429_with_human_message(cache):
    client = make_client(cache, limit=1)
    assert client.post("/api/chat", json={"message": "İstanbul"}).status_code == 200
    res = client.post("/api/chat", json={"message": "İstanbul"})
    assert res.status_code == 429
    assert "yoğunuz" in res.json()["detail"]


def test_route_endpoint_recomputes_mode(cache):
    client = make_client(cache)
    body = client.post("/api/chat", json={"message": "İstanbul"}).text
    trip_id = body.split('"trip": {"id": "')[1].split('"')[0]
    res = client.post("/api/route", json={"trip_id": trip_id, "mode": "arac"})
    assert res.status_code == 200
    assert res.json()["route"]["mode"] == "arac"
    assert client.post("/api/route", json={"trip_id": "yok", "mode": "arac"}).status_code == 404


def test_validation_rejects_huge_message(cache):
    client = make_client(cache)
    assert client.post("/api/chat", json={"message": "x" * 501}).status_code == 422

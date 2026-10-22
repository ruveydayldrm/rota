import time

from app.cache.store import Cache


def test_set_get_roundtrip_with_unicode(cache: Cache):
    cache.set("wiki", "Q1", {"extract": "Ayasofya, İstanbul'da…"})
    assert cache.get("wiki", "Q1") == {"extract": "Ayasofya, İstanbul'da…"}


def test_namespaces_are_isolated(cache: Cache):
    cache.set("a", "k", 1)
    assert cache.get("b", "k") is None


def test_expired_values_disappear(cache: Cache, monkeypatch):
    cache.set("route", "k", [1, 2], ttl=10)
    real = time.time()
    monkeypatch.setattr(time, "time", lambda: real + 11)
    assert cache.get("route", "k") is None


def test_purge_expired(cache: Cache, monkeypatch):
    cache.set("x", "old", 1, ttl=1)
    cache.set("x", "new", 2, ttl=1000)
    real = time.time()
    monkeypatch.setattr(time, "time", lambda: real + 5)
    assert cache.purge_expired() == 1
    assert cache.get("x", "new") == 2


def test_file_cache_persists(tmp_path):
    path = str(tmp_path / "sub" / "c.sqlite3")
    first = Cache(path)
    first.set("n", "k", {"v": 1})
    first.close()
    assert Cache(path).get("n", "k") == {"v": 1}

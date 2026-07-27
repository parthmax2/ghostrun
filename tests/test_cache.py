from pathlib import Path

from gentest.cache import Cache, CachedResponse, request_key


def test_request_key_stable_across_key_order():
    a = b'{"model":"gpt-4o","prompt":"hi"}'
    b = b'{"prompt":"hi","model":"gpt-4o"}'
    assert request_key("POST", "https://api.openai.com/v1/chat", a) == \
           request_key("POST", "https://api.openai.com/v1/chat", b)


def test_request_key_changes_with_body():
    a = b'{"prompt":"hi"}'
    b = b'{"prompt":"bye"}'
    assert request_key("POST", "u", a) != request_key("POST", "u", b)


def test_cache_roundtrip(tmp_path: Path):
    cache = Cache(tmp_path)
    resp = CachedResponse(200, {"content-type": "application/json"}, b'{"ok":true}')
    key = request_key("POST", "https://api.openai.com/v1/chat", b'{"prompt":"hi"}')
    assert not cache.has(key)
    cache.put(key, "POST", "https://api.openai.com/v1/chat", b'{"prompt":"hi"}', resp)
    assert cache.has(key)
    got = cache.get(key)
    assert got.status_code == 200
    assert got.body == b'{"ok":true}'

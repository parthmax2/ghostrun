"""Secrets must never reach the cache — the README encourages committing it."""

import json

import pytest

from gentest.cache import Cache, CachedResponse, request_key
from gentest.redact import MASK, redact_headers, redact_value


def test_sensitive_headers_masked():
    out = redact_headers({
        "Authorization": "Bearer sk-secret",
        "Set-Cookie": "session=abc",
        "Content-Type": "application/json",
    })
    assert out["Authorization"] == MASK
    assert out["Set-Cookie"] == MASK
    assert out["Content-Type"] == "application/json"  # harmless header kept


@pytest.mark.parametrize("key", [
    "api_key", "openai_api_key", "X-Api-Key", "access_token",
    "refresh_token", "password", "client_secret", "private_key",
])
def test_sensitive_body_keys_masked(key):
    assert redact_value({key: "supersecret"})[key] == MASK


def test_nested_and_listed_secrets_masked():
    out = redact_value({"a": [{"api_key": "x"}, {"ok": "keep"}], "b": {"token": "y"}})
    assert out["a"][0]["api_key"] == MASK
    assert out["a"][1]["ok"] == "keep"
    assert out["b"]["token"] == MASK


@pytest.mark.parametrize("secret", [
    "sk-abcdefghijklmnopqrstuvwxyz123456",
    "sk-ant-abcdefghijklmnopqrstuvwxyz12",
    "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
    "AKIAIOSFODNN7EXAMPLE",
])
def test_secret_values_in_free_text_masked(secret):
    out = redact_value({"prompt": f"my key is {secret} ok"})
    assert secret not in out["prompt"]
    assert MASK in out["prompt"]


def test_ordinary_content_untouched():
    text = "Where is my refund? It's been three weeks!"
    assert redact_value({"prompt": text})["prompt"] == text


def test_cache_file_has_no_secrets(tmp_path):
    cache = Cache(tmp_path)
    body = json.dumps({
        "model": "gpt-4o-mini",
        "api_key": "sk-abcdefghijklmnopqrstuvwxyz123456",
        "messages": [{"role": "user", "content": "hi"}],
    }).encode()
    key = request_key("POST", "https://api.openai.com/v1/chat", body)
    resp = CachedResponse(200, {"Authorization": "Bearer sk-leak"}, b'{"ok":true}')
    cache.put(key, "POST", "https://api.openai.com/v1/chat", body, resp)

    on_disk = (tmp_path / f"{key}.json").read_text(encoding="utf-8")
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in on_disk
    assert "sk-leak" not in on_disk
    assert MASK in on_disk


def test_redaction_does_not_break_replay(tmp_path):
    """Redaction touches only what's written for humans, never the replayed body
    or the cache key."""
    cache = Cache(tmp_path)
    body = json.dumps({"api_key": "sk-abcdefghijklmnopqrstuvwxyz123456"}).encode()
    key = request_key("POST", "https://api.openai.com/v1/chat", body)
    cache.put(key, "POST", "https://api.openai.com/v1/chat", body,
              CachedResponse(200, {}, b'{"reply":"hello"}'))

    # Same original bytes still resolve to the same entry...
    assert request_key("POST", "https://api.openai.com/v1/chat", body) == key
    # ...and the replayed response body is untouched.
    assert cache.get(key).body == b'{"reply":"hello"}'

"""Record/replay tests driven entirely offline.

We give httpx a MockTransport as the *real* underlying transport. ghostrun's
interceptor wraps whatever `_transport_for_url` returns, so on record it calls
the mock (counting the call) and caches the response; on replay it serves from
cache without touching the mock. This mirrors how a real OpenAI/Anthropic call
would flow, minus the network.
"""

import json

import httpx
import pytest

from ghostrun.cache import Cache
from ghostrun.config import get_config
from ghostrun.interceptor import CacheMiss, Interceptor

URL = "https://api.openai.com/v1/chat/completions"


def make_client(counter):
    def handler(request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        return httpx.Response(200, json={"reply": "hello", "call": counter["n"]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def post(client, body):
    return client.post(URL, content=json.dumps(body).encode())


def test_records_then_replays(tmp_path):
    cache = Cache(tmp_path / "c")
    counter = {"n": 0}

    with Interceptor(cache, mode="auto"):
        r1 = post(make_client(counter), {"prompt": "hi"})
        assert r1.json()["reply"] == "hello"
        assert counter["n"] == 1  # network hit once

        # Second identical call in auto mode should be served from cache.
        r2 = post(make_client(counter), {"prompt": "hi"})
        assert r2.json()["reply"] == "hello"
        assert counter["n"] == 1  # NOT incremented — cache hit


def test_replay_mode_errors_on_miss(tmp_path):
    cache = Cache(tmp_path / "c")
    counter = {"n": 0}
    with Interceptor(cache, mode="replay"):
        with pytest.raises(CacheMiss):
            post(make_client(counter), {"prompt": "never recorded"})
    assert counter["n"] == 0  # replay never touches the network


def test_non_provider_hosts_pass_through(tmp_path):
    cache = Cache(tmp_path / "c")
    counter = {"n": 0}
    with Interceptor(cache, mode="record"):
        client = make_client(counter)
        client.post("https://example.com/api", content=b"{}")
        client.post("https://example.com/api", content=b"{}")
    # Both calls hit the mock; nothing cached for a non-provider host.
    assert counter["n"] == 2
    assert not any((tmp_path / "c").glob("*.json")) if (tmp_path / "c").exists() else True


def test_interceptor_restores_httpx(tmp_path):
    original = httpx.Client._transport_for_url
    with Interceptor(Cache(tmp_path / "c"), mode="auto"):
        assert httpx.Client._transport_for_url is not original
    assert httpx.Client._transport_for_url is original

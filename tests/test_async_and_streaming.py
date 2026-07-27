"""Coverage for the two paths most real LLM apps depend on: async clients and
streaming (SSE) responses. Both go through the interceptor and must record and
replay correctly."""

import asyncio
import json

import httpx

from gentest.cache import Cache
from gentest.interceptor import Interceptor

URL = "https://api.openai.com/v1/chat/completions"

SSE_BODY = (
    b'data: {"choices":[{"delta":{"content":"He"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":"llo"}}]}\n\n'
    b'data: [DONE]\n\n'
)


def _decode_sse(resp) -> str:
    out = []
    for line in resp.iter_lines():
        if line.startswith("data: ") and "[DONE]" not in line:
            out.append(json.loads(line[6:])["choices"][0]["delta"]["content"])
    return "".join(out)


def test_async_records_then_replays(tmp_path):
    cache = Cache(tmp_path / "c")
    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"reply": "hi"})

    async def run():
        with Interceptor(cache, mode="auto"):
            for _ in range(2):
                client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
                resp = await client.post(URL, content=b'{"p":1}')
                assert resp.json()["reply"] == "hi"

    asyncio.run(run())
    assert calls["n"] == 1  # second call served from cache


def test_streaming_records_then_replays(tmp_path):
    cache = Cache(tmp_path / "c")
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, content=SSE_BODY,
                              headers={"content-type": "text/event-stream"})

    decoded = []
    with Interceptor(cache, mode="auto"):
        for _ in range(2):
            client = httpx.Client(transport=httpx.MockTransport(handler))
            with client.stream("POST", URL, content=b'{"stream":true}') as resp:
                decoded.append(_decode_sse(resp))

    assert decoded == ["Hello", "Hello"]  # replayed stream decodes identically
    assert calls["n"] == 1


def test_async_streaming_records_then_replays(tmp_path):
    cache = Cache(tmp_path / "c")
    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        return httpx.Response(200, content=SSE_BODY,
                              headers={"content-type": "text/event-stream"})

    async def run():
        seen = []
        with Interceptor(cache, mode="auto"):
            for _ in range(2):
                client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
                async with client.stream("POST", URL, content=b'{"s":1}') as resp:
                    chunks = []
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and "[DONE]" not in line:
                            chunks.append(
                                json.loads(line[6:])["choices"][0]["delta"]["content"])
                    seen.append("".join(chunks))
        return seen

    assert asyncio.run(run()) == ["Hello", "Hello"]
    assert calls["n"] == 1

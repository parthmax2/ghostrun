"""Live-API smoke test — the one link the mock-based suite can't prove:
that ghostrun records correctly from a *real* provider response, then replays it.

This is opt-in. It is skipped unless BOTH are true:
  * OPENAI_API_KEY is set
  * ghostrun_LIVE=1

    OPENAI_API_KEY=sk-... ghostrun_LIVE=1 pytest examples/test_live_smoke.py -v

What it proves, end to end:
  1. record  -> one real call to api.openai.com is captured to the cache
  2. replay  -> the SAME assertions pass with the network made unreachable and
                the API key removed, served entirely from the cache

It costs a single cheap gpt-4o-mini call the first time; nothing thereafter.
The recorded response is written to this file's own cache dir and can be
committed so the test runs offline in CI forever after.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import ghostrun
from ghostrun.cache import Cache
from ghostrun.interceptor import CacheMiss, Interceptor

pytestmark = pytest.mark.skipif(
    not (os.environ.get("OPENAI_API_KEY") and os.environ.get("ghostrun_LIVE") == "1"),
    reason="live test: set OPENAI_API_KEY and ghostrun_LIVE=1 to run",
)

CACHE_DIR = str(Path(__file__).with_name(".ghostrun_live_cache"))
PROMPT = "In one short sentence, apologize to a customer for a late refund."


def _ask(api_key: str, prompt: str = PROMPT) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=0)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content


def test_live_record_then_offline_replay():
    cache = Cache(Path(CACHE_DIR))

    # 1) RECORD: one genuine call to the real API.
    with Interceptor(cache, mode="record"):
        recorded = _ask(os.environ["OPENAI_API_KEY"])
    assert recorded and isinstance(recorded, str)

    # A real judge grades the real response (skips if Ollama unavailable).
    from examples.conftest import _ollama_ready  # reuse the guard's probe

    if _ollama_ready(ghostrun.get_config()):
        ghostrun.expect(recorded).contains_intent("apology")

    # 2) REPLAY: network unreachable + no key. Must come from cache.
    with Interceptor(cache, mode="replay"):
        replayed = _ask("sk-deliberately-invalid")
    assert replayed == recorded, "replayed response must match what was recorded"


def test_replay_miss_does_not_hit_network():
    """A prompt we never recorded must fail loudly in replay, not call the API."""
    cache = Cache(Path(CACHE_DIR))
    with Interceptor(cache, mode="replay"):
        with pytest.raises((CacheMiss, Exception)) as exc:
            # A prompt that was never recorded -> must miss, never call the API.
            _ask("sk-deliberately-invalid", prompt="A prompt never recorded xyzzy")
        # Unwrap SDK-wrapped errors to confirm a CacheMiss is underneath.
        chain, cur = [], exc.value
        while cur is not None:
            chain.append(type(cur).__name__)
            cur = cur.__cause__ or cur.__context__
        assert "CacheMiss" in chain, f"expected CacheMiss, got chain {chain}"

"""Real-API integration tier for `ghostrun.craft`.

Everything else in this project is stub-based on purpose: fast, free,
deterministic, safe in CI on every push. That's correct for unit coverage,
but it means nothing here actually proves the code works against a real
provider's real response shapes -- a signature/adapter mismatch (like the
`Agent` `Literal`-on-`action` bug this project hit once) only shows up when
something real replies.

These tests are marked `live` and excluded by default (see
`addopts = "-m 'not live'"` in pyproject.toml). Run them deliberately:

    pytest -m live tests/test_craft_live.py

They need a real provider key (GEMINI_API_KEY, OPENAI_API_KEY, or
ANTHROPIC_API_KEY) and will make a small number of real, billed calls --
cheap (a handful of short completions on a cheap/free-tier-eligible model),
but not free. Skipped automatically if no key is set.
"""

from __future__ import annotations

import os

import pytest

from ghostrun.craft import LLMClient, Predict, Signature, craft

pytestmark = pytest.mark.live


def _live_model() -> str:
    """Pick whichever provider has a key set, preferring the cheapest/most
    recently-verified-working option first."""
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini:gemini-3.5-flash-lite"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai:gpt-4o-mini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic:claude-haiku-4-5-20251001"
    return ""


MODEL = _live_model()
skip_without_key = pytest.mark.skipif(
    not MODEL, reason="needs GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY set"
)


@skip_without_key
def test_live_llm_client_completes_a_simple_prompt():
    client = LLMClient(MODEL)
    reply = client.complete(
        "You are a terse assistant.",
        [{"role": "user", "content": "Reply with exactly one word: pong"}],
        temperature=0.0,
    )
    assert "pong" in reply.lower()
    assert client.call_count == 1
    # Real usage tracking: at least one of these should have real data,
    # even if the other lacks provider pricing.
    assert client.total_tokens > 0 or client.total_cost >= 0.0


@skip_without_key
def test_live_predict_forward_produces_typed_output():
    module = Predict(Signature.parse("question -> answer, is_capital_city: bool"))
    client = LLMClient(MODEL)
    prediction = module.forward(
        client, temperature=0.0, question="What is the capital of France? Answer in one word."
    )
    assert "paris" in prediction.answer.lower()
    assert isinstance(prediction.is_capital_city, bool)
    assert prediction.is_capital_city is True


@skip_without_key
def test_live_craft_bootstraps_from_real_examples(tmp_path):
    """Smoke test: a tiny real craft() run, gold-metric graded (any
    non-empty answer passes -- grading itself stays free/deterministic, no
    judge call at all) -- proves the whole search loop, including the
    metric-grading path, works against real response shapes end to end, not
    just that each piece works alone in isolation."""
    examples_path = tmp_path / "examples.jsonl"
    examples_path.write_text(
        '{"question": "What is 2 + 2?"}\n{"question": "What is the capital of Japan?"}\n',
        encoding="utf-8",
    )

    result = craft(
        "live_smoke", "question -> answer", str(examples_path),
        metric=lambda pred, row: bool(pred.get("answer", "").strip()),
        model=MODEL, max_examples=2, max_attempts=1,
        cache_dir=str(tmp_path / "cache"),
    )

    assert len(result.examples) >= 1  # at least one real example got accepted
    for example in result.examples:
        assert example["answer"].strip()  # non-empty real model output

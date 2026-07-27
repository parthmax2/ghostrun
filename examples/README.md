# ghostrun example: customer support replies

A minimal, runnable demonstration of ghostrun against a fake support app.

- [`support_app.py`](support_app.py) — stand-in user code that calls the OpenAI
  chat endpoint over HTTP (the same code path the real SDK uses).
- [`test_support_reply.py`](test_support_reply.py) — a ghostrun test with semantic
  assertions.
- [`.ghostrun_cache/`](.ghostrun_cache) — a **pre-recorded response**, so the test
  replays with no API key and no network.

## Run it (with a local judge — the real demo)

Semantic assertions (`contains_intent`, `tone_is`) are graded by a local model.
Install [Ollama](https://ollama.com) and pull a small model once:

```bash
ollama pull llama3.2:3b
```

Then, from the repo root:

```bash
pytest examples/test_support_reply.py
```

The response comes from the local cache (instant, free); the assertions are
graded locally by Llama. Nothing leaves your machine. (`examples/conftest.py`
puts this directory on `sys.path`, so no `PYTHONPATH` is needed.)

## Without Ollama

The `echo` judge is an offline heuristic stub — it does **literal** substring
matching, not real semantics, so intents like `"apology"` won't match the word
`"sorry"`. It exists to exercise plumbing without a model, not to grade meaning.
When no real judge is available (echo, or Ollama down / model not pulled), the
example **skips** rather than fails:

```bash
GHOSTRUN_JUDGE=echo pytest examples/test_support_reply.py   # -> skipped
```

For real semantic grading, use Ollama (above) or point the judge at a cloud
model in `.ghostrun.yaml`.

## Live API smoke test

[`test_live_smoke.py`](test_live_smoke.py) is the one check the mock-based suite
can't cover: recording from the **real** OpenAI API and replaying it offline.
It's opt-in — skipped unless you provide a key and set `GHOSTRUN_LIVE=1`:

```bash
OPENAI_API_KEY=sk-... GHOSTRUN_LIVE=1 pytest examples/test_live_smoke.py -v
```

It costs one cheap `gpt-4o-mini` call the first time, writes the response to
`.ghostrun_live_cache/`, and proves the same assertions then pass with the network
unreachable and the key removed. In CI it runs only via manual dispatch
(`Run workflow` → *run live*), so PRs never spend money.

## Re-record against the real API

```bash
export OPENAI_API_KEY=sk-...
pytest examples/test_support_reply.py --ghostrun-record
```

This overwrites `.ghostrun_cache/` with a fresh real response.

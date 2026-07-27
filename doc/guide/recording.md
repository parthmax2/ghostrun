# Recording and replay

ghostrun intercepts at the **HTTP transport layer** (httpx), which both the OpenAI
and Anthropic SDKs sit on top of. It does *not* monkey-patch the SDKs, so it
survives SDK upgrades. Only requests to known provider hosts are cached; all
other traffic passes through untouched.

Modes (via `ghostrun_MODE` or `.ghostrun.yaml`):

| Mode | Behavior |
| :--- | :--- |
| `auto` (default) | Replay if cached, otherwise record. |
| `record` | Always hit the network and overwrite the cache. |
| `replay` | Never hit the network; a cache miss is a hard error (ideal for CI). |

Cache files are human-readable JSON keyed by a hash of method + URL + body, so a
prompt change produces a reviewable diff.

## Judge verdicts are cached too

Caching the LLM response but re-grading it on every run would leave your suite
slow *and* non-deterministic — a stochastic judge can flip a green test to red
with no code change. So ghostrun records judge verdicts under
`.ghostrun_cache/judge/` with the same `auto` / `record` / `replay` semantics.

Verdicts are keyed on **judge backend + model + text + criterion**, so changing
the judge model or editing an assertion correctly forces a re-grade. Each stored
verdict includes the judge's own stated reason, so the cache explains *why* a
test passes:

```json
{
  "judge": { "backend": "ollama", "model": "llama3.2:3b" },
  "criterion": "The text expresses the intent or content: refund",
  "passed": true,
  "reason": "The text explicitly mentions \"refund\" in its content."
}
```

In the bundled example this takes a run from **23.3s to 2.7s**, and in
`--ghostrun-replay` no model is invoked at all. Disable with `judge.cache: false`
or `ghostrun_JUDGE_CACHE=false` if you want a live grade every run.

## Providers

Calls to these hosts are recorded; everything else passes through untouched:
OpenAI, Anthropic, Azure OpenAI, Gemini, Vertex AI, AWS Bedrock, Mistral,
Cohere, OpenRouter, Groq, Together, Fireworks, DeepSeek, xAI, Perplexity.

Self-hosted gateway or something not listed?

```python
import ghostrun.interceptor as gi
gi.PROVIDER_HOSTS += ("llm.internal.corp",)
```

## Secrets

The cache is designed to be committable, so secrets are scrubbed on the way in:

- Request headers are **never stored** (that's where `Authorization` lives).
- Response headers are masked (`authorization`, `cookie`, `set-cookie`, org IDs).
- Request bodies have secret-looking keys masked (`api_key`, `access_token`,
  `password`, …) plus token patterns in free text (`sk-…`, `ghp_…`, `AKIA…`).
  Benign lookalikes such as `max_tokens` are explicitly preserved.
- **Response bodies are stored verbatim, by design** — they're what gets replayed
  to the code under test, so rewriting them would corrupt the thing you're
  testing. If model output itself is sensitive, don't commit the cache.

Redaction never affects replay: cache keys are computed from the original bytes,
and stored request bodies are for human review only.

## Parallel test runs

`pytest -n auto` (xdist) is supported. Cache writes are atomic (temp file +
`os.replace`), and interceptor state is per-thread, so concurrent tests record
into their own caches rather than each other's.

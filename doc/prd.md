# Product Requirements Document: GenTest

| | |
| :--- | :--- |
| **Project** | GenTest (PyPI package: `gentest`) |
| **Status** | Phase 1 (MVP) — implemented |
| **Core philosophy** | Code-first, local-first, zero SaaS lock-in |
| **Last updated** | 2026-07-24 |

---

## 1. Executive summary & problem statement

**The problem.** Generative AI applications are non-deterministic. Traditional unit testing (`assert output == "expected"`) fails because LLM outputs vary between runs. Today developers either test GenAI by hand or lean on heavy, cloud-based SaaS platforms (LangSmith, Braintrust) to evaluate outputs. Those tools require sending proprietary prompts and customer data to third-party servers — a non-starter under enterprise privacy constraints (SOC2, HIPAA).

**The solution.** GenTest is a lightweight, open-source Python framework that brings the familiarity of `pytest` to GenAI. It provides:

1. **Deterministic replay** — real LLM HTTP calls are recorded once to a local cache and replayed on every subsequent run (zero cost, zero latency, zero flakiness).
2. **Semantic assertions** — assertions on *meaning* rather than exact text, graded by a local "LLM-as-a-judge" (Ollama) by default, so no data leaves the machine.

No cloud dashboard, no custom CLI. It runs inside `pytest`.

---

## 2. Target personas

1. **Indie AI devs / hackathon builders** — building agents or RAG apps. Need to confirm a prompt tweak didn't break existing behavior. Want something free, fast, and trivial to set up.
2. **Enterprise AI engineers** — building internal tools under strict data-privacy compliance. *Cannot* use cloud evaluation SaaS. Need a local, code-first tool that drops into CI/CD.

---

## 3. Scope & feature breakdown

### Phase 1 — MVP (open-source core) — *implemented*

- **Deterministic replay (`@gentest.record`)**
  - Intercepts LLM API calls (OpenAI, Anthropic) at the HTTP layer.
  - Saves the exact request payload and response to a local `.gentest_cache/` directory.
  - On subsequent runs, returns the cached response instantly.
- **Semantic assertions (`gentest.expect(...)`)**
  - Assertions based on meaning, not exact text.
  - Uses a local, free Ollama model as the judge by default → zero cost, full privacy.
  - Methods: `contains_intent()`, `does_not_contain_intent()`, `tone_is()`, `matches()`, plus deterministic `contains()`, `does_not_contain()`, `is_valid_json()`.
- **Native pytest integration**
  - Standard pytest output (green dots, red F's). No custom CLI to learn.
  - Auto-registered plugin adds `--gentest-record` / `--gentest-replay` / `--gentest-judge` flags.

### Phase 2 — V1.1 & monetization (post-launch)

- **Prompt regression tracking** — *implemented.* Runs snapshot every asserted output and verdict (`pytest --gentest-snapshot NAME`); `gentest diff v1 v2` classifies each assertion as regression / fix / stable / added / removed / not-evaluated, and reports output drift (similarity ratio + unified diff) separately, since a response can change substantially while still passing. `--fail-on-regression` exits 1 for CI gating.
- **Cloud dashboard (business model)** — hosted web dashboard for teams to view CI/CD test results, track evaluation scores over time, collaborate. Freemium: free for solo, paid tier for teams. **Not started — see the open positioning question below.**

---

## 4. Developer experience

The assertion entry point is **`gentest.expect(...)`**, not `gentest.assert(...)`. `assert` is a reserved Python keyword and cannot be used as a function or attribute name — `gentest.assert(...)` is a `SyntaxError`. `expect` provides the identical fluent, chainable DX.

```python
# test_customer_support.py
import gentest
from my_app import generate_reply

# 1. Record the LLM call. Subsequent runs use the local cache.
@gentest.record(model="gpt-4o-mini")
def test_reply_generation():
    reply = generate_reply("Where is my refund?")

    # 2. Semantic assertions, graded by a local Llama model.
    gentest.expect(reply).contains_intent("apology")
    gentest.expect(reply).contains_intent("refund policy")
    gentest.expect(reply).does_not_contain_intent("arguing")
    gentest.expect(reply).tone_is("empathetic")
```

Running it:

```bash
$ pytest test_customer_support.py
================================ test session starts ================================
collected 1 item

test_customer_support.py .                                                     [100%]
================================ 1 passed in 0.04s =================================
```

The sub-second run time is the point: after the first record, every call replays from disk.

---

## 5. Technical architecture

### A. The interceptor (caching)

- **Decision:** Do **not** monkey-patch the OpenAI/Anthropic SDKs — they change often and break.
- **Approach:** Intercept at the HTTP transport layer. Both SDKs send requests through `httpx`, so GenTest wraps httpx's transport (`_transport_for_url`) for the duration of a recording. Any client created by any SDK is transparently routed through the recording transport.
- **Scoping:** Only requests to recognized provider hosts (`api.openai.com`, `api.anthropic.com`, Azure OpenAI) are cached; all other traffic passes through untouched.
- **Modes:** `auto` (replay if cached else record — default), `record` (always hit network, overwrite cache), `replay` (never hit network; a cache miss is a hard error — ideal for CI).

### B. The judge (semantic assertions)

- **Decision:** Do not use GPT-4 to grade — slow and costs money.
- **Approach:**
  1. Default to a local Ollama model (e.g. `llama3.2:3b`).
  2. GenTest builds a hidden strict system prompt: *"You are a strict grading assistant… Respond PASS or FAIL."* and parses the leading token of the reply.
  3. Users override the judge model/backend via `.gentest.yaml`, env vars, or `gentest.configure(...)`.
- **Failure handling:** A missing model or stopped daemon raises a clear, actionable `JudgeUnavailable` (`ollama pull llama3.2:3b`) rather than hanging or surfacing a raw 404. An offline `echo` judge lets CI and GenTest's own tests run with no model dependency.
- **Verdict caching (critical for determinism):** Caching the provider response but re-grading it every run would reintroduce the exact non-determinism GenTest exists to remove — a stochastic judge can flip a green test red with no code change, while costing an inference per assertion. Judge verdicts are therefore recorded to `.gentest_cache/judge/` under the same `auto`/`record`/`replay` semantics, keyed on judge backend + model + text + criterion so that changing the model or editing an assertion forces a re-grade. Stored verdicts include the judge's stated reason, making the cache an audit trail for *why* a test passes. Measured effect on the bundled example: 23.3s → 2.7s, and zero model calls under `--gentest-replay`.
- **Majority-vote caching (`judge.votes`), and why single-verdict caching alone is not a differentiator:** competitive research (see `comparison.md`) found DeepEval already ships single-verdict judge caching, so that alone doesn't distinguish GenTest. Live literature review also found published LLM-as-judge reliability studies (notably "The Coin Flip Judge?", arXiv 2606.13685) reporting ~13.6% mean flip rates on repeated grading of identical input, with their recommended mitigation being majority-vote over 11+ trials per verdict — not caching one draw. Neither DeepEval nor that literature addresses the specific tradeoff a cost-conscious CI tool faces: is caching a *single* verdict safe, and how much does majority-of-k caching improve reliability at what cost? `judge.votes` (default 1, backward compatible) grades N times on a cache miss and caches the majority verdict plus the observed disagreement rate. This is simultaneously a product reliability improvement and the empirical question this project is positioned to answer that nobody else has published. **Benchmark methodology and results:** real repeated single-shot grades (15 per condition, 90 total live judge calls, no synthetic data) were drawn from the actual `llama3.2:3b` judge across an easy/borderline/sarcasm case set at temperature 0 and temperature 0.7. The modal (most-frequent) verdict over the 15 draws was treated as the judge's "true opinion" for that input, and majority-of-k reliability (k∈{1,3,5}) was estimated by bootstrap-resampling 500 subsets of size k from the real draws and checking agreement with the modal.

Results: **5 of 6 conditions showed 0% flip rate** — a single draw at temperature 0 (the shipped default) was perfectly stable across all 15 repeats for both easy and borderline-tone cases, and even for the sarcasm case *at temperature 0*. The one condition with real variance was **sarcasm at temperature 0.7: 46.7% flip rate** (a near-exact replication of "The Coin Flip Judge?"'s framing of judge unreliability), where majority voting helped only marginally and **non-monotonically** — reliability against the modal verdict was k=1: 49.6%, k=3: 55.8%, k=5: 51.8%. Average across all six conditions: flip rate 7.8%, reliability k=1: 91.6%, k=3: 92.6%, k=5: 92.0%.

**Honest interpretation — this is a finding, not a validation of the feature as originally conceived.** Majority-of-k voting does *not* reliably rescue a criterion the judge has no stable opinion on; averaging noise around a coin flip does not converge to a correct answer, only to a slightly-less-noisy coin flip. The practically useful result is that `disagreement_rate` functions as a **detector** for unreliable criteria (a high rate flags "this assertion is ambiguous or this judge is guessing," prompting a rewritten criterion or a bigger judge) rather than a **corrector**. Separately, the benchmark suggests a local, single-tenant Ollama judge at temperature 0 may be substantially more reproducible in practice than the multi-tenant cloud-served judges the published flip-rate literature studied (7.8% average here vs. ~13.6% reported for cloud judges) — plausible given published root causes are largely batching/routing effects specific to multi-tenant serving, though this is six data points on one small model and should be read as suggestive, not conclusive, without a larger replication.

### C. Storage

- Cache files live in a hidden `.gentest_cache/` at the project root.
- Filenames are a stable hash of method + URL + normalized request body (which includes the model name), preventing collisions. Bodies are JSON-normalized (sorted keys) so semantically identical payloads map to the same key.
- Files are human-readable JSON, so a prompt change produces a reviewable diff.

---

## 6. Configuration

`.gentest.yaml` at the project root; every value also settable via `GENTEST_*` env var or `gentest.configure(...)` at runtime. Resolution order: defaults → file → env.

```yaml
mode: auto
cache_dir: .gentest_cache
judge:
  type: ollama          # or "echo" for an offline heuristic stub
  model: llama3.2:3b
  base_url: http://localhost:11434
  timeout: 60
```

---

## 7. Go-to-market & launch strategy

- **Weeks 1–3:** Build MVP, write documentation, record a 2-minute demo showing the "aha" (sub-second replay).
- **Week 4 — launch day:**
  1. **Hacker News:** *"Show HN: the pytest for LLMs — local-first, no SaaS."*
  2. **Reddit:** r/LangChain, r/LocalLLaMA, r/Python — lead with the local-first / privacy angle for the LocalLLaMA crowd.
  3. **X/Twitter:** share with prominent AI devs and ask for feedback.
  4. **Directories:** submit to "Awesome LLM" lists on GitHub.

---

## 8. Success metrics (first 90 days)

| Metric | Target | Why it matters |
| :--- | :--- | :--- |
| GitHub stars | 1,500+ | Developer interest and virality |
| PyPI downloads | 5,000+ | People actually installing and using it |
| Unresolved GitHub issues | < 10 | Code is stable and DX is good |
| Community members | 200+ | Building a community, not just a tool |

---

## 9. Risks & mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| Local LLM judge is inaccurate | High — false pass/fail | Configurable judge model; optional strict mode using a cloud model; free-form `matches()` for precise criteria |
| HTTP interception breaks on SDK updates | Medium — flaky tests | Intercept at the httpx transport layer (shared, stable) instead of SDK internals; integration tests for the interceptor itself |
| LangChain/LlamaIndex add this natively | High — loss of differentiation | Stay a micro-framework: lightweight, fast, framework-agnostic |
| Ollama not installed / model not pulled | Medium — bad first-run experience | Actionable error messages; offline `echo` judge so the suite still runs |

---

## 10. Implementation status

Phase 1 is implemented and tested (offline suite green). Package layout:

```
gentest/
  __init__.py       public API: record, recording, expect, configure
  config.py         defaults -> .gentest.yaml -> env resolution
  cache.py          request-hash -> readable JSON cache entries
  interceptor.py    httpx transport shim (record/replay, provider-scoped)
  record.py         @record decorator + recording() context manager
  assertions.py     expect(text).contains_intent / tone_is / is_valid_json ...
  judge/
    base.py         Judge protocol + strict PASS/FAIL prompt + parser
    ollama.py       local default judge with actionable errors
    echo.py         offline heuristic stub for CI
  plugin.py         pytest plugin: flags + fixture
tests/              offline test suite
```

**Deferred to Phase 2:** prompt regression tracking, cloud dashboard.

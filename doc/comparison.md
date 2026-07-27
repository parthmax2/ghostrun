# ghostrun vs. the field — comparison research

**Last updated:** 2026-07-24
**Method:** live web research (see Sources at the end of each section). This is
not a marketing comparison — it's written to find out honestly where ghostrun
is ahead, where it's behind, and where it's simply duplicating existing work.

---

## TL;DR

ghostrun's individual pieces all have prior art, some of it more mature and
better-funded. Its actual differentiation is a **specific combination** nobody
else ships as one package:

1. **Transport-level, zero-code-change record/replay** of the application's own
   LLM calls (not just its judge calls) — you wrap existing code, no config
   file, no SDK-specific adapter, no dataset authoring step.
2. **Structured prompt-version regression diffing** — classifying every
   assertion as regression/fix/stable/added/removed/**not-evaluated**, plus
   output-drift similarity — as a first-class CLI command.
3. Both of the above live **inside plain pytest**, not a separate CLI/YAML tool.

Nobody else combines all three. Each one alone, however, has been done before —
see below.

---

## Comparison table

| Tool | Category | License / OSS | Ecosystem | Record/replay of the **app's own** LLM calls | Judge-verdict caching | Structured regression diff (regression/fix/added/removed) | Native to pytest | Maturity |
|---|---|---|---|---|---|---|---|---|
| **ghostrun** | Testing framework | MIT, OSS | Python | ✅ transport-level, any SDK, zero code change | ✅ + not-run/removed distinction | ✅ `ghostrun diff` with output-drift similarity | ✅ native plugin | New (this project) |
| **DeepEval** | Testing framework | OSS (Confident AI has a paid cloud tier) | Python | ❌ not documented — you already have the output; it caches the *grading*, not the app's provider call | ✅ `-c` flag caches metric results per identical test case | ❌ not documented | ✅ `assert_test()`, `deepeval test run` | Mature, active, described as "the closest thing to pytest for LLMs" |
| **Promptfoo** | Prompt/model comparison + red-teaming | OSS, 23k+ ⭐ | Node.js/CLI, YAML config | ❌ caches its *own* evaluation-matrix results for cost, not a generic transport-level replay of arbitrary app code | Partial — caches eval results, not framed as "judge verdict" specifically | ⚠️ marketed as having "regression tracking" but docs describe pass/fail re-evaluation, not a structured diff report | ❌ separate CLI, not a pytest plugin | Mature, very active, 10M+-user production pedigree claimed |
| **Ragas** | RAG evaluation metrics | OSS | Python | ❌ | ❌ | ❌ | Integrable, not native | Mature; narrow scope (RAG metrics only) |
| **vcr-langchain** | HTTP record/replay | OSS | Python, **LangChain-only** | ✅ but explicitly incomplete — README states much LangChain functionality "hasn't gotten around to hijacking" | ❌ | ❌ | Via VCR.py/pytest-recording | Niche, limited scope, LangChain-coupled |
| **langchain-replay** | Agent decision replay | OSS | Python, LangChain/LangGraph | ✅ for LangChain/LangGraph specifically, preserves real filesystem tool execution | ❌ | ❌ | Not pytest-native | Niche |
| **pytest-recording / VCR.py** | Generic HTTP replay | OSS | Python, any HTTP | ✅ but generic HTTP, not LLM-aware (no judge, no tool-call parsing, no redaction) | ❌ | ❌ | ✅ native | Mature, foundational, widely used |
| **CacheSaver** (EMNLP 2025) | Research-inference caching | OSS, peer-reviewed | Python | ✅ but framed for research/benchmark reproducibility, not CI/pytest | Generic response caching, not judge-verdict-specific | ❌ | ❌ | Academic, published, active |
| **Langfuse** | Observability + eval | OSS, self-hostable (owned by ClickHouse) | Any | ❌ (tracing/observability, not test replay) | ❌ | ❌ | ❌ | Mature, widely deployed |
| **Braintrust** | Eval-first platform | Proprietary SaaS, no self-host | Any | ❌ | Platform-side | Partial — "regression gates" in production monitoring sense | ❌ | Mature, funded, commercial |
| **LangSmith** | LangChain-native observability/eval | Proprietary | LangChain/LangGraph | ❌ | Platform-side | Partial | ❌ | Mature, commercial |
| **Giskard** | Adversarial/vulnerability scanning | Apache-2.0, OSS, 5,400+ ⭐ | Python | ❌ (different problem: red-teaming, not regression testing) | ❌ | ❌ | Integrable | Mature, active (5,499 commits/yr) |
| **OpenAI Evals** | Benchmark registry | OSS | Python | ❌ (registry/benchmark runner, not app-level replay) | ❌ | ❌ | ❌ | Mature but less actively the "default" now |
| **Inspect AI** (UK AISI) | Agent/safety eval framework | OSS | Python | ❌ (built for running evals/benchmarks, not testing your own app's calls) | ❌ | ❌ | ❌ | Mature, actively maintained |

Legend: ✅ confirmed via docs/README · ⚠️ marketed but not confirmed in documentation · ❌ not found / not the tool's purpose

---

## Where ghostrun is genuinely ahead

- **Zero-code-change replay of the actual application under test.** DeepEval,
  Promptfoo, Ragas, and the observability platforms all assume you bring the
  *output* to them (a test case, a dataset row, a logged trace). None of them
  intercept your app's own live HTTP calls to OpenAI/Anthropic/etc.
  transparently. ghostrun's httpx-transport interception means you wrap
  existing code with `@ghostrun.record` and it works, regardless of which SDK
  or provider you used to write it — no adapter, no config file.
- **LangChain-agnostic.** vcr-langchain and langchain-replay — the two tools
  closest to ghostrun's replay mechanism — are explicitly coupled to LangChain
  and admit incomplete coverage. ghostrun works at the HTTP layer underneath
  any SDK.
- **Structured regression diffing with a `not-evaluated` state.** Nothing
  found distinguishes "this assertion was deleted" from "this assertion never
  ran because the test aborted earlier" — a real reporting bug I found and
  fixed in ghostrun's own implementation (see CHANGELOG). This is a small but
  real quality difference.
- **All of this lives inside pytest**, not a separate CLI/YAML/dataset
  workflow — closer to the everyday habits of a Python developer than
  Promptfoo's Node/YAML model.

## Where ghostrun is duplicating prior art (be honest about this in any paper or pitch)

- **"Cache judge verdicts."** DeepEval already ships this (`-c` flag, disk-backed,
  keyed on identical test cases). ghostrun's version adds a `(backend, model,
  text, criterion)` key and a `replay`/`record`/`auto` mode distinction, which
  is more precise, but the *concept* is not new.
- **"Record/replay LLM HTTP calls."** vcr-langchain, langchain-replay, and
  pytest-recording/VCR.py (generic) all predate this. ghostrun's contribution
  here is breadth (provider-agnostic, not LangChain-locked) and integration
  quality, not the underlying idea.
- **"LLM-as-judge semantic assertions in pytest."** DeepEval's `assert_test()`
  with G-Eval-style metrics is materially the same pitch, more mature, with
  50+ pre-built metrics vs. ghostrun's five.

## What's still a genuinely open question (see [prd.md](prd.md) and the literature review in this conversation)

Whether **caching a single judge verdict** (ghostrun's and DeepEval's shared
default) is a safe engineering tradeoff given the now-published judge flip-rate
literature (~13.6% mean flip rate per "The Coin Flip Judge?", 2606.13685) is
*not* answered by either tool's documentation, or by the flip-rate papers
themselves (which recommend majority-vote-of-11+, not caching one draw). That
gap — quantifying the reliability/cost tradeoff of N=1 cached verdict vs.
N=k majority-vote caching, specifically in a CI-regression-gating context —
appears to still be open, and is the sharpest available research contribution
building on this codebase.

---

## Sources

- [DeepEval — Unit Testing in CI/CD](https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd)
- [DeepEval — Flags and Configs](https://deepeval.com/docs/evaluation-flags-and-configs)
- [DeepEval cache implementation](https://github.com/confident-ai/deepeval/blob/main/deepeval/test_run/cache.py)
- [Promptfoo — Intro docs](https://www.promptfoo.dev/docs/intro/)
- [Promptfoo GitHub org](https://github.com/promptfoo)
- [vcr-langchain](https://github.com/amosjyng/vcr-langchain)
- [langchain-replay](https://github.com/sixty-north/langchain-replay)
- [Using VCR and pytest with pytest-recording](https://til.simonwillison.net/pytest/pytest-recording-vcr)
- [CacheSaver (EMNLP 2025 Findings)](https://aclanthology.org/2025.findings-emnlp.1402/)
- [CacheSaver GitHub](https://github.com/au-clan/cachesaver)
- [Langfuse / Braintrust / LangSmith comparison — Latitude](https://latitude.so/blog/best-llm-observability-tools-agents-latitude-vs-langfuse-langsmith)
- [Giskard-AI/giskard-oss](https://github.com/Giskard-AI/giskard-oss)
- [OpenAI Evals](https://github.com/openai/evals)
- [Inspect AI overview — Hamel's Blog](https://hamel.dev/notes/llm/evals/inspect.html)
- [The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation](https://arxiv.org/html/2606.13685)
- [DeepEval vs PromptFoo vs RAGAS comparison — genai.qa](https://genai.qa/blog/promptfoo-vs-deepeval-vs-ragas/)
- [DeepEval alternatives 2026 — Braintrust](https://www.braintrust.dev/articles/deepeval-alternatives-2026)

**Caveat:** several of these sources are 2026 blog/SEO comparison articles, not
primary documentation — used here for triangulation, cross-checked against
official docs/READMEs where possible, and flagged with ⚠️ in the table where a
claim (e.g., Promptfoo's "regression tracking") could not be confirmed from
primary docs.

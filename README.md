<p align="center">
  <img alt="ghostrun logo" src="https://raw.githubusercontent.com/parthmax2/ghostrun/main/assets/ghost-logo.webp" width="270">
</p>

<h3 align="center">pytest for LLMs — Write fast, zero-cost tests for your AI prompts, and optimize them automatically when they fail.</h3>
<p align="center">ghostrun gives you the two things most Gen AI developers end up building from scratch: a way to write reliable, offline-ready prompt tests, and a way to automatically optimize those prompts when they break. Both live in plain Python and plain <code>pytest</code> — no cloud dashboards, no complex YAML, no extra test harnesses.</p>

<p align="center">
  <a href="https://pypi.org/project/ghostrun/"><img alt="PyPI" src="https://img.shields.io/pypi/v/ghostrun.svg"></a>
  <a href="https://pypi.org/project/ghostrun/"><img alt="PyPI downloads" src="https://static.pepy.tech/badge/ghostrun"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <a href="pyproject.toml"><img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-blue.svg"></a>
  <a href="https://github.com/parthmax2/ghostrun/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/parthmax2/ghostrun/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/parthmax2/ghostrun/actions/workflows/release.yml"><img alt="Release" src="https://github.com/parthmax2/ghostrun/actions/workflows/release.yml/badge.svg"></a>
</p>

<h4 align="center">
  <a href="#is-this-for-you">Is this for you?</a> ·
  <a href="#install">Install</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#prompt-optimization-ghostrun-craft">Prompt Optimization</a> ·
  <a href="#documentation">Documentation</a> ·
  <a href="#roadmap">Roadmap</a>
</h4>

<p align="center">
  <img src="https://raw.githubusercontent.com/parthmax2/ghostrun/main/assets/ghostrun-hero.gif" alt="ghostrun: a ghost travels to the LLM API once, then instantly reappears with the result on every run after" width="640">
</p>

---

> [!TIP]
> **TDD for LLMs (Test-Driven Prompts):** Instead of guessing prompts in a notebook, write your test and criteria first (using `ghostrun.expect`), then let the optimizer (`ghostrun craft`) automatically tune the prompt instructions and few-shots to pass the test.

### The Problem: Why LLM testing is frustrating

Building an AI application usually leaves you with three painful problems:
1. **Slow & Expensive Tests:** Every time you run `pytest`, your test suite calls OpenAI/Anthropic APIs, costing you money and taking forever to finish.
2. **Brittle Exact Assertions:** LLM outputs change slightly on every run. Writing `assert reply == "expected"` fails randomly because the LLM used a different word.
3. **The Prompt Guessing Game:** When you edit a prompt to fix one edge case, you have no easy way to know if you silently broke another output somewhere else.

### How ghostrun fixes it

`ghostrun` solves all three issues by bringing standard software testing workflows to AI:

*   **Fast & Free Tests (Deterministic Replay):** Wrap your test in `@ghostrun.record`. The first run hits the real API and saves the response; every run after replays it instantly from disk. Tests run in **0.05 seconds**, cost nothing, and run fully offline in CI.
*   **No More Flakiness (Semantic Assertions):** Assert on meaning and intent instead of exact text. `ghostrun.expect(reply).tone_is("empathetic")` is graded by a free, local judge (via Ollama) so your data stays private.
*   **Self-Healing Prompts (Optimizers):** If your prompt fails the test, run `ghostrun craft` with your target criteria and training examples. The optimizer automatically searches for the best instructions and few-shot examples to pass your tests.

No SaaS dashboards. No complicated YAML. Just Python and `pytest`.

**Search terms this project is built for:** LLM evals in CI, LLM regression testing, pytest LLM evals, deterministic LLM tests, prompt engineering framework, prompt optimization, few-shot example selection, semantic assertions for LLM apps, and testing OpenAI or Anthropic applications with pytest.

---

## Install

```bash
pip install ghostrun
```

For the default (local, free, private) judge, install [Ollama](https://ollama.com) and pull a small model:

```bash
ollama pull llama3.2:3b
```

If anything doesn't work, `ghostrun doctor` diagnoses the setup — see
[Configuration](doc/guide/configuration.md#diagnosing-a-broken-setup-ghostrun-doctor).

**Fastest start:** `ghostrun init` scaffolds a working first test against
whatever LLM SDK it finds in your project (OpenAI, Anthropic, or a generic
HTTP fallback) plus a `.ghostrun.yaml` — no config to author by hand:

```bash
ghostrun init
pytest test_ghostrun_example.py
```

## Quickstart

```python
# test_customer_support.py
import ghostrun
from my_app import generate_reply

@ghostrun.record(model="gpt-4o-mini")
def test_reply_generation():
    reply = generate_reply("Where is my refund?")

    ghostrun.expect(reply).contains_intent("apology")
    ghostrun.expect(reply).contains_intent("refund policy")
    ghostrun.expect(reply).does_not_contain_intent("arguing")
    ghostrun.expect(reply).tone_is("empathetic")
```

```bash
$ pytest test_customer_support.py
================================ test session starts ================================
collected 1 item

test_customer_support.py .                                                     [100%]
================================ 1 passed in 0.04s =================================
```

The `0.04s` is the whole point — after the first record, calls replay from disk.

> **Note on the API:** the assertion entry point is `ghostrun.expect(...)`, not
> `ghostrun.assert(...)` — `assert` is a reserved Python keyword and cannot be a
> function name.

**Record/replay alone needs no Ollama at all** — the judge is only touched when
you call a judge-backed assertion (`contains_intent`, `tone_is`, `matches`).
Deterministic assertions (`contains`, `is_valid_json`) and tool-call assertions
never invoke it.

## Prompt Optimization (`ghostrun craft`)

Where `@ghostrun.record` and `expect(...)` **test** an existing prompt, `ghostrun craft` **builds and optimizes** one.

Instead of hand-writing brittle prompts and guessing edge cases, declare a typed input/output signature (`"inputs -> outputs"`) and let `ghostrun craft` automatically search for winning instructions and discover high-value few-shot demonstrations:

```python
from ghostrun.craft import craft

# Automatically synthesize prompt instructions & select passing few-shots
crafted = craft(
    name="refund_classifier",
    signature="customer_message -> is_refund_request, urgency",
    examples_path="dataset/support_queries.jsonl",
    criterion="Accurately flags refund requests and evaluates urgency",
    model="gpt-4o-mini",
    budget=10,  # Bayesian search over instruction candidates & demo bootstrapping
)

print(crafted.instructions)
# Resulting prompt artifacts and demos are saved locally for test replay
```

Or optimize directly from the CLI:

```bash
ghostrun craft refund_classifier \
    --signature "customer_message -> is_refund_request, urgency" \
    --examples dataset.jsonl \
    --criterion "Accurately flags refund requests and evaluates urgency" \
    --model gpt-4o-mini
```

Learn more in the [Prompt Crafting Guide](doc/guide/craft.md).

## Is this for you?

**Use ghostrun if** you're writing pytest tests around code that calls an LLM
(directly or via the OpenAI/Anthropic SDKs) and want that suite to run offline,
free, and deterministically after the first recording.

**Skip it if** you need a hosted dashboard/observability platform for
production traffic (see Langfuse/LangSmith/Braintrust instead), you're
building a red-team/adversarial test suite (see Giskard), or you want 50+
pre-built judge metrics out of the box today (see DeepEval — more mature, more
metrics, but doesn't intercept your app's own HTTP calls the way ghostrun
does). See [doc/comparison.md](doc/comparison.md) for the full, researched
breakdown of where ghostrun is ahead and where it's duplicating existing work.

## Documentation

Start here, in order:

| Guide | What's in it |
| :--- | :--- |
| [LLM regression testing](https://ghostrun.parthmax.tech/guide/llm-regression-testing.html) | CI-native LLM evals for catching semantic and prompt regressions in real app code |
| [Pytest LLM evals](https://ghostrun.parthmax.tech/guide/pytest-llm-evals.html) | How to write LLM evals as normal pytest tests instead of dashboard-only workflows |
| [Test OpenAI apps offline](https://ghostrun.parthmax.tech/guide/test-openai-apps-offline.html) | Record/replay OpenAI and Anthropic API calls so CI does not repeat live model calls |
| [doc/guide/recording.md](doc/guide/recording.md) | How record/replay works, judge-verdict caching, supported providers, secret redaction, parallel test runs |
| [doc/guide/assertions.md](doc/guide/assertions.md) | Semantic assertions, judge reliability (benchmarked, not asserted), majority-vote verdicts, tool/function-call assertions |
| [doc/guide/craft.md](doc/guide/craft.md) | Prompt synthesis, signatures (`input -> output`), Bayesian instruction search, and few-shot bootstrapping |
| [doc/guide/configuration.md](doc/guide/configuration.md) | `.ghostrun.yaml`, environment variables, pytest flags, `ghostrun doctor`, `ghostrun init` |

<details>
<summary><b>Deeper reference</b>, once you're past the basics</summary>

<br>

| Guide | What's in it |
| :--- | :--- |
| [doc/guide/regression-tracking.md](doc/guide/regression-tracking.md) | Snapshotting runs, `ghostrun diff`, posting a regression as a PR comment, JUnit CI integration |
| [doc/guide/api-reference.md](doc/guide/api-reference.md) | Every public function, class, exception, and config field |
| [doc/guide/why-not-diy.md](doc/guide/why-not-diy.md) | The actual bugs found building this — the case for a maintained package over a five-minute prompt |
| [doc/judge-voting-benchmark.md](doc/judge-voting-benchmark.md) | Full methodology and results for the majority-vote judge-caching benchmark |
| [doc/comparison.md](doc/comparison.md) | Researched comparison against DeepEval, Promptfoo, Ragas, vcr-langchain, and 9 other tools |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

</details>

A hosted, searchable version of this documentation is planned at
[ghostrun.parthmax.tech](https://ghostrun.parthmax.tech/) (config
in `mkdocs.yml`, builds via `.github/workflows/docs.yml`).

## Roadmap

- [x] Deterministic HTTP record/replay (`@ghostrun.record`, `.ghostrun_cache/`)
- [x] Semantic assertions (`contains_intent`, `tone_is`, `matches`) via local Ollama or an offline `echo` stub
- [x] Judge-verdict caching, including majority-vote grading (`judge.votes`) with a benchmarked reliability tradeoff
- [x] Tool/function-call assertions (`expect_tool_calls`)
- [x] Prompt synthesis & optimization (`ghostrun craft`, `Signature`, `BootstrapFewShot`, `BayesianSearch`)
- [x] Prompt regression tracking — `ghostrun diff`, PR-comment and JUnit CI output
- [x] `ghostrun init` / `ghostrun doctor` — scaffolding and setup diagnostics in one command
- [x] Secret redaction so the cache is safe to commit
- [x] 16-provider HTTP coverage (OpenAI, Anthropic, Gemini, Bedrock, and more)
- [x] Published to PyPI with trusted-publishing (OIDC) releases
- [ ] Hosted, searchable documentation site (`mkdocs.yml` ready; not yet deployed)
- [ ] Broader provider/framework integration guides

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — setup, test requirements, and where
things live in the codebase.

## Development

```bash
pip install -e ".[dev]"
pytest            # runs fully offline using the echo judge
```

## License

MIT

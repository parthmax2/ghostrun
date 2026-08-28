<p align="center">
  <img alt="ghostrun logo" src="assets/ghost-logo.webp" width="360">
</p>

<h3 align="center">CI-native LLM evals for real applications.</h3>
<p align="center">ghostrun turns real LLM app behavior into deterministic pytest evals: record API calls once, replay them in CI, and catch semantic regressions before they ship.</p>

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
  <a href="#documentation">Documentation</a> ·
  <a href="#roadmap">Roadmap</a>
</h4>

<p align="center">
  <img src="assets/ghostrun-hero.gif" alt="ghostrun: a ghost travels to the LLM API once, then instantly reappears with the result on every run after" width="640">
</p>

---

> [!TIP]
> LLM evals often live outside the product: separate datasets, dashboards, YAML files, and one-off scripts. ghostrun keeps evals inside normal `pytest`, runs them against the real code path your users hit, records the live LLM call once, and replays it deterministically in CI.

### The problem

```python
reply = generate_reply("Where is my refund?")
assert reply == "I'm sorry for the delay..."   # fails tomorrow: LLM never says the same thing twice
```

LLM apps need evals, but live model calls make test suites painful: they cost money, need API keys in CI, run slowly, and fail for reasons unrelated to your code. Generic eval platforms are powerful, but they often test a prompt, dataset, or trace outside your application. ghostrun focuses on app-native LLM regression testing: the exact Python code path your users exercise.

### How ghostrun fixes it

1. **Deterministic replay** — the first run records real LLM HTTP calls to a local `.ghostrun_cache/`; every run after replays them instantly from disk. Zero API cost, zero latency, zero flakiness, no key needed in CI.
2. **Semantic assertions** — assert on *meaning*, not exact text:
   ```python
   ghostrun.expect(reply).contains_intent("apology")
   ghostrun.expect(reply).tone_is("empathetic")
   ```
   Graded by a **local Ollama model** by default — your prompts and data never leave your machine. That grading verdict gets cached too, so it's also free and deterministic after the first run.

No cloud dashboard. No custom CLI to learn. No dataset to author by hand. Just `pytest`.

**Search terms this project is built for:** LLM evals in CI, LLM regression testing, pytest LLM evals, deterministic LLM tests, prompt regression testing, semantic assertions for LLM apps, and testing OpenAI or Anthropic applications with pytest.

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
| [LLM regression testing](https://ghostrun.parthmax.in/guide/llm-regression-testing.html) | CI-native LLM evals for catching semantic and prompt regressions in real app code |
| [Pytest LLM evals](https://ghostrun.parthmax.in/guide/pytest-llm-evals.html) | How to write LLM evals as normal pytest tests instead of dashboard-only workflows |
| [Test OpenAI apps offline](https://ghostrun.parthmax.in/guide/test-openai-apps-offline.html) | Record/replay OpenAI and Anthropic API calls so CI does not repeat live model calls |
| [doc/guide/recording.md](doc/guide/recording.md) | How record/replay works, judge-verdict caching, supported providers, secret redaction, parallel test runs |
| [doc/guide/assertions.md](doc/guide/assertions.md) | Semantic assertions, judge reliability (benchmarked, not asserted), majority-vote verdicts, tool/function-call assertions |
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
[ghostrun.parthmax.in](https://ghostrun.parthmax.in/) (config
in `mkdocs.yml`, builds via `.github/workflows/docs.yml`).

## Roadmap

- [x] Deterministic HTTP record/replay (`@ghostrun.record`, `.ghostrun_cache/`)
- [x] Semantic assertions (`contains_intent`, `tone_is`, `matches`) via local Ollama or an offline `echo` stub
- [x] Judge-verdict caching, including majority-vote grading (`judge.votes`) with a benchmarked reliability tradeoff
- [x] Tool/function-call assertions (`expect_tool_calls`)
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

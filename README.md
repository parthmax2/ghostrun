# GenTest

[![PyPI](https://img.shields.io/pypi/v/gentest.svg)](https://pypi.org/project/gentest/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![CI](https://github.com/parthmax2/gentest/actions/workflows/ci.yml/badge.svg)](https://github.com/parthmax2/gentest/actions/workflows/ci.yml)

**pytest for LLMs.** Deterministic record/replay and semantic assertions for GenAI apps — **local-first, privacy-first, zero SaaS lock-in.**

Generative AI outputs vary, so `assert output == "expected"` doesn't work. GenTest gives you two things instead:

1. **Deterministic replay** — the first run records real LLM HTTP calls to a local `.gentest_cache/`; every run after replays them instantly. Zero API cost, zero latency, zero flakiness.
2. **Semantic assertions** — assert on *meaning* (`contains_intent`, `tone_is`, …), graded by a **local Ollama model** by default. Your prompts and data never leave your machine.

No cloud dashboard. No custom CLI to learn. Just `pytest`.

---

## Install

```bash
pip install gentest
```

For the default (local, free, private) judge, install [Ollama](https://ollama.com) and pull a small model:

```bash
ollama pull llama3.2:3b
```

If anything doesn't work, `gentest doctor` diagnoses the setup — see
[Configuration](doc/guide/configuration.md#diagnosing-a-broken-setup-gentest-doctor).

**Fastest start:** `gentest init` scaffolds a working first test against
whatever LLM SDK it finds in your project (OpenAI, Anthropic, or a generic
HTTP fallback) plus a `.gentest.yaml` — no config to author by hand:

```bash
gentest init
pytest test_gentest_example.py
```

## Quickstart

```python
# test_customer_support.py
import gentest
from my_app import generate_reply

@gentest.record(model="gpt-4o-mini")
def test_reply_generation():
    reply = generate_reply("Where is my refund?")

    gentest.expect(reply).contains_intent("apology")
    gentest.expect(reply).contains_intent("refund policy")
    gentest.expect(reply).does_not_contain_intent("arguing")
    gentest.expect(reply).tone_is("empathetic")
```

```bash
$ pytest test_customer_support.py
================================ test session starts ================================
collected 1 item

test_customer_support.py .                                                     [100%]
================================ 1 passed in 0.04s =================================
```

The `0.04s` is the whole point — after the first record, calls replay from disk.

> **Note on the API:** the assertion entry point is `gentest.expect(...)`, not
> `gentest.assert(...)` — `assert` is a reserved Python keyword and cannot be a
> function name.

**Record/replay alone needs no Ollama at all** — the judge is only touched when
you call a judge-backed assertion (`contains_intent`, `tone_is`, `matches`).
Deterministic assertions (`contains`, `is_valid_json`) and tool-call assertions
never invoke it.

## Documentation

| Guide | What's in it |
| :--- | :--- |
| [doc/guide/recording.md](doc/guide/recording.md) | How record/replay works, judge-verdict caching, supported providers, secret redaction, parallel test runs |
| [doc/guide/assertions.md](doc/guide/assertions.md) | Semantic assertions, judge reliability (benchmarked, not asserted), majority-vote verdicts, tool/function-call assertions |
| [doc/guide/regression-tracking.md](doc/guide/regression-tracking.md) | Snapshotting runs, `gentest diff`, posting a regression as a PR comment, JUnit CI integration |
| [doc/guide/configuration.md](doc/guide/configuration.md) | `.gentest.yaml`, environment variables, pytest flags, `gentest doctor`, `gentest init` |
| [doc/guide/api-reference.md](doc/guide/api-reference.md) | Every public function, class, exception, and config field |
| [doc/guide/why-not-diy.md](doc/guide/why-not-diy.md) | The actual bugs found building this — the case for a maintained package over a five-minute prompt |
| [doc/judge-voting-benchmark.md](doc/judge-voting-benchmark.md) | Full methodology and results for the majority-vote judge-caching benchmark |
| [doc/comparison.md](doc/comparison.md) | Researched comparison against DeepEval, Promptfoo, Ragas, vcr-langchain, and 9 other tools |
| [doc/prd.md](doc/prd.md) | Product spec |
| [doc/task.md](doc/task.md) | Living status tracker — what's done, what's left, and why |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

A hosted, searchable version of this documentation is planned at
[parthmax2.github.io/gentest](https://parthmax2.github.io/gentest/) once the
repo is public (config in `mkdocs.yml`, builds via `.github/workflows/docs.yml`).

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

---
title: pytest for LLMs
description: Deterministic HTTP record/replay, local LLM-as-judge semantic assertions, and prompt regression diffing for testing GenAI applications in Python.
---

# ghostrun

**pytest for LLMs.** Deterministic record/replay and semantic assertions for
GenAI apps — local-first, privacy-first, zero SaaS lock-in.

Generative AI outputs vary, so `assert output == "expected"` doesn't work.
ghostrun gives you two things instead:

1. **Deterministic replay** — the first run records real LLM HTTP calls to a
   local `.ghostrun_cache/`; every run after replays them instantly. Zero API
   cost, zero latency, zero flakiness.
2. **Semantic assertions** — assert on *meaning*
   (`contains_intent`, `tone_is`, …), graded by a local Ollama model by
   default. Your prompts and data never leave your machine.

```bash
pip install ghostrun
ollama pull llama3.2:3b   # for the default local judge
ghostrun init              # scaffolds a working first test
pytest test_ghostrun_example.py
```

## Guide

- [Recording and replay](guide/recording.md)
- [Semantic assertions](guide/assertions.md)
- [Prompt regression tracking](guide/regression-tracking.md)
- [Configuration](guide/configuration.md)
- [API reference](guide/api-reference.md)
- [Why not just ask an LLM to write this?](guide/why-not-diy.md)

## Research

- [Judge-voting benchmark](judge-voting-benchmark.md)
- [Comparison with other tools](comparison.md)

Source, issues, and the changelog live on
[GitHub](https://github.com/parthmax2/ghostrun).

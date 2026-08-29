---
name: ghostrun-testing
description: Write deterministic pytest tests for LLM applications with 0.04s replay and semantic intent assertions.
---

# GhostRun Testing Skill

Use this skill when writing, debugging, or running tests for Python AI applications using `ghostrun`.

## Quick Start Template

```python
import ghostrun
from my_app import call_llm

@ghostrun.record(model="gpt-4o-mini")
def test_customer_support_reply():
    # 1. Real LLM call recorded on 1st run; replayed in 0.04s for $0 on future runs
    reply = call_llm("Where is my refund? It has been 3 weeks.")

    # 2. Semantic Intent Assertions (Graded privately by local Ollama judge)
    ghostrun.expect(reply).contains_intent("apologize for delay")
    ghostrun.expect(reply).contains_intent("explain refund timeline")
    ghostrun.expect(reply).does_not_contain_intent("arguing with customer")
    ghostrun.expect(reply).tone_is("empathetic and professional")
```

## Available Semantic Assertions

- `ghostrun.expect(text).contains_intent("...")` — Assert semantic intent exists regardless of phrasing.
- `ghostrun.expect(text).does_not_contain_intent("...")` — Assert prohibited topics/actions are absent.
- `ghostrun.expect(text).tone_is("empathetic")` — Assert overall sentiment/tone.
- `ghostrun.expect(text).matches("...")` — Semantic match against an expected baseline.
- `ghostrun.expect(text).contains("exact substring")` — Fast deterministic substring check.
- `ghostrun.expect(text).is_valid_json()` — Validate JSON formatting.

## Executing Tests

Always run tests using the native GhostRun test runner:

```bash
ghostrun run tests/test_my_prompt.py
```
*(Automatically triggers celebration animations on passing tests).*

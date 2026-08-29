---
name: ghostrun-craft
description: Automatically search, synthesize, and optimize AI prompts using DSPy-style signatures and Bayesian instruction optimization.
---

# GhostRun Prompt Crafting Skill

Use this skill when developing, optimizing, or discovering high-performing prompts for GenAI applications.

## Python API Usage

```python
from ghostrun.craft import craft

# 1. Define metric function
def exact_accuracy(prediction: str, example: dict) -> float:
    return 1.0 if prediction.strip() == example["target"] else 0.0

# 2. Automatically discover optimal instructions & few-shot examples
crafted = craft(
    name="triage_classifier",
    signature="customer_ticket -> priority, category",
    examples_path="dataset/tickets.jsonl",
    criterion="Accurately identifies urgent security tickets and categorizes them correctly",
    model="gpt-4o-mini",
    budget=10,  # Bayesian search iterations
)

print("Synthesized Instructions:", crafted.instructions)
print("Holdout Accuracy Score:", crafted.holdout_score)
```

## CLI Usage

```bash
ghostrun craft classifier \
    --signature "input_text -> sentiment, summary" \
    --examples data/samples.jsonl \
    --model gpt-4o-mini \
    --budget 10
```

Optimized artifacts are stored in `.ghostrun_cache/prompts/` and are immediately ready for test suites.

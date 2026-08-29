"""ghostrun craft vs DSPy: customer support triage.

Both tools build a prompt for the SAME task (message -> category, urgency)
from the SAME 25 training rows, then both get evaluated -- independently of
whatever grading each tool used internally -- against the SAME 15 held-out
rows neither ever saw during training, scored by exact match against gold
labels. That final number is the only one that matters for "is this ready."

Run: python benchmark/run_benchmark.py
Needs GEMINI_API_KEY set (see .env).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from data import split  # noqa: E402

# Free-tier Gemini has a low requests-per-minute limit. Both ghostrun's
# LLMClient and DSPy's LM ultimately call litellm.completion(), so patching
# it here is the one place that rate-limits *every* call from either tool,
# instead of trying to wrap each tool's client separately.
import litellm  # noqa: E402

# litellm logs a per-call deprecation warning to stderr; in PowerShell,
# piping stderr through `2>&1` wraps each of those lines as a red
# NativeCommandError even though nothing failed. Silence litellm's own
# logging (our ProgressClient prints everything useful already) instead of
# fighting PowerShell's stderr handling.
import logging  # noqa: E402

litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

_RATE_LIMIT_DELAY = 4.5  # seconds between calls
_orig_completion = litellm.completion


def _rate_limited_completion(*args, **kwargs):
    try:
        return _orig_completion(*args, **kwargs)
    finally:
        time.sleep(_RATE_LIMIT_DELAY)


litellm.completion = _rate_limited_completion

MODEL_GHOSTRUN = "gemini:gemini-3.6-flash"
MODEL_DSPY = "gemini/gemini-3.6-flash"
SPEC = "message -> category, urgency"
CRITERION = (
    "category correctly identifies the topic of the customer message "
    "(billing, technical, account, or general) and urgency correctly "
    "reflects how severe/time-sensitive it is (low, medium, or high)"
)
BENCH_DIR = Path(__file__).parent
CACHE_DIR = BENCH_DIR / ".ghostrun_cache"


class ProgressClient:
    """Wraps an LLMClient and prints before/after each call with elapsed
    time and a hard local timeout, so a hang shows up immediately in the
    log instead of silently stalling the whole run."""

    def __init__(self, inner, label="client"):
        self.inner = inner
        self.label = label
        self.n = 0

    def complete(self, system, messages, temperature=0.0):
        self.n += 1
        tag = f"{self.label:<13} #{self.n:<3}"
        t0 = time.time()
        try:
            result = self.inner.complete(system, messages, temperature=temperature)
        except Exception as exc:
            print(f"  {tag} FAILED  {time.time()-t0:5.1f}s  {type(exc).__name__}: "
                  f"{str(exc).splitlines()[0][:120]}", flush=True)
            raise
        print(f"  {tag} ok      {time.time()-t0:5.1f}s", flush=True)
        return result


def normalize(value: str) -> str:
    return str(value).strip().lower()


def score(predictions, gold_rows):
    n = len(gold_rows)
    exact = category_only = urgency_only = 0
    rows = []
    for pred, gold in zip(predictions, gold_rows):
        pred_cat = normalize(pred.get("category", ""))
        pred_urg = normalize(pred.get("urgency", ""))
        gold_cat = normalize(gold["category"])
        gold_urg = normalize(gold["urgency"])
        cat_ok = pred_cat == gold_cat
        urg_ok = pred_urg == gold_urg
        if cat_ok:
            category_only += 1
        if urg_ok:
            urgency_only += 1
        if cat_ok and urg_ok:
            exact += 1
        rows.append({"message": gold["message"], "gold": (gold_cat, gold_urg),
                    "pred": (pred_cat, pred_urg), "exact": cat_ok and urg_ok})
    return {
        "exact_match": exact / n,
        "category_accuracy": category_only / n,
        "urgency_accuracy": urgency_only / n,
        "n": n,
        "rows": rows,
    }


def run_ghostrun(train_rows):
    from ghostrun.craft import LLMClient, Predict, Signature, craft

    train_path = BENCH_DIR / "_train.jsonl"
    train_path.write_text(
        "\n".join(json.dumps({"message": r["message"]}) for r in train_rows), encoding="utf-8"
    )

    print("\n=== ghostrun craft: BayesianSearch (budget=12) ===")
    t0 = time.time()
    search_client = ProgressClient(LLMClient(MODEL_GHOSTRUN, timeout=20.0, num_retries=1), "craft")
    result = craft(
        "triage", SPEC, str(train_path), CRITERION,
        model=MODEL_GHOSTRUN, client=search_client, max_examples=2, max_attempts=1,
        budget=12, holdout_ratio=0.2, cache_dir=str(CACHE_DIR),
    )
    elapsed = time.time() - t0
    print(f"  instructions: {result.instructions!r}")
    print(f"  examples kept: {len(result.examples)}")
    print(f"  internal holdout_score: {result.holdout_score}")
    print(f"  candidates_tried: {result.candidates_tried}")
    print(f"  wall time: {elapsed:.1f}s")

    module = Predict(Signature.parse(SPEC))
    module.signature.instructions = result.instructions
    module.demos = result.examples
    eval_client = ProgressClient(LLMClient(MODEL_GHOSTRUN, timeout=20.0, num_retries=1), "ghostrun-eval")
    return module, eval_client, result


def run_dspy(train_rows):
    import dspy

    print("\n=== DSPy: BootstrapFewShot ===")
    dspy.configure(lm=dspy.LM(MODEL_DSPY, num_retries=1, timeout=20.0))

    trainset = [
        dspy.Example(message=r["message"], category=r["category"], urgency=r["urgency"]).with_inputs("message")
        for r in train_rows
    ]

    def metric(example, prediction, trace=None):
        return (
            normalize(prediction.category) == normalize(example.category)
            and normalize(prediction.urgency) == normalize(example.urgency)
        )

    student = dspy.Predict("message -> category, urgency")
    optimizer = dspy.teleprompt.BootstrapFewShot(
        metric=metric, max_bootstrapped_demos=2, max_labeled_demos=2, max_rounds=1,
    )
    t0 = time.time()
    compiled = optimizer.compile(student, trainset=trainset)
    elapsed = time.time() - t0
    print(f"  demos kept: {len(compiled.demos)}")
    print(f"  wall time: {elapsed:.1f}s")
    return compiled


def eval_ghostrun(module, client, test_rows):
    # `client` is already a ProgressClient, so each call logs itself --
    # no extra per-row print needed here.
    predictions = []
    for row in test_rows:
        try:
            pred = module.forward(client, temperature=0.0, message=row["message"])
            predictions.append(dict(pred))
        except Exception as exc:
            print(f"  ghostrun-eval    ERROR   {exc}", flush=True)
            predictions.append({"category": "", "urgency": ""})
    return predictions


def eval_dspy(compiled, test_rows):
    predictions = []
    for i, row in enumerate(test_rows, 1):
        t0 = time.time()
        tag = f"{'dspy-eval':<13} #{i:<3}"
        try:
            pred = compiled(message=row["message"])
            predictions.append({"category": pred.category, "urgency": pred.urgency})
            print(f"  {tag} ok      {time.time()-t0:5.1f}s", flush=True)
        except Exception as exc:
            print(f"  {tag} FAILED  {time.time()-t0:5.1f}s  {type(exc).__name__}: "
                  f"{str(exc).splitlines()[0][:120]}", flush=True)
            predictions.append({"category": "", "urgency": ""})
    return predictions


def main():
    train_rows, test_rows = split()
    print(f"train rows: {len(train_rows)}, held-out test rows: {len(test_rows)}")

    module, client, ghostrun_result = run_ghostrun(train_rows)
    dspy_compiled = run_dspy(train_rows)

    print("\n=== Evaluating both on the SAME 15 held-out rows ===")
    ghostrun_preds = eval_ghostrun(module, client, test_rows)
    dspy_preds = eval_dspy(dspy_compiled, test_rows)

    ghostrun_score = score(ghostrun_preds, test_rows)
    dspy_score = score(dspy_preds, test_rows)

    report = {
        "ghostrun": {
            "exact_match": ghostrun_score["exact_match"],
            "category_accuracy": ghostrun_score["category_accuracy"],
            "urgency_accuracy": ghostrun_score["urgency_accuracy"],
            "examples_kept": len(ghostrun_result.examples),
            "instructions": ghostrun_result.instructions,
        },
        "dspy": {
            "exact_match": dspy_score["exact_match"],
            "category_accuracy": dspy_score["category_accuracy"],
            "urgency_accuracy": dspy_score["urgency_accuracy"],
            "demos_kept": len(dspy_compiled.demos),
        },
    }

    print("\n" + "=" * 60)
    print("RESULTS (held-out, n=15, exact gold-label match)")
    print("=" * 60)
    print(f"{'metric':<20}{'ghostrun craft':<18}{'DSPy':<18}")
    print(f"{'exact_match':<20}{ghostrun_score['exact_match']:<18.2%}{dspy_score['exact_match']:<18.2%}")
    print(f"{'category_accuracy':<20}{ghostrun_score['category_accuracy']:<18.2%}{dspy_score['category_accuracy']:<18.2%}")
    print(f"{'urgency_accuracy':<20}{ghostrun_score['urgency_accuracy']:<18.2%}{dspy_score['urgency_accuracy']:<18.2%}")

    gap = ghostrun_score["exact_match"] - dspy_score["exact_match"]
    print(f"\nghostrun vs DSPy exact-match gap: {gap:+.2%}")
    bar = "PASS (within 10%)" if gap >= -0.10 else "FAIL (more than 10% behind)"
    print(f"Bar (ghostrun within ~10% of DSPy): {bar}")

    out_path = BENCH_DIR / "results.json"
    out_path.write_text(json.dumps({
        **report,
        "ghostrun_rows": ghostrun_score["rows"],
        "dspy_rows": dspy_score["rows"],
    }, indent=2), encoding="utf-8")
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()

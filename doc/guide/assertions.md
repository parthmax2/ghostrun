# Semantic assertions

Judge-backed (uses the configured LLM judge):

- `contains_intent(intent)`
- `does_not_contain_intent(intent)`
- `tone_is(tone)`
- `matches(free_form_criterion)`

Deterministic (no model, instant):

- `contains(substring)` / `does_not_contain(substring)`
- `is_valid_json()`

All methods chain and raise `AssertionError` on failure, so they render as normal
pytest failures.

## How reliable is the judge?

Semantic grading is only as good as the model doing it. Benchmarked on a set of
hand-labeled cases, the default `llama3.2:3b` judge agreed with ground truth
about **~90%** of the time — strong on clear-cut and negation cases, weaker on
subtle tone and sarcasm. Practical implications:

- **Use judge-backed assertions to catch gross regressions** ("the bot stopped
  apologizing"), not as a precise quality gate. Expect roughly 1 in 10 semantic
  verdicts to be arguable on a small model.
- **For deterministic properties, prefer the deterministic assertions above**
  (`contains`, `is_valid_json`, tool-call checks) — they're exact and instant.
- **Need higher fidelity?** Point `judge_model` at a larger local model or a
  cloud model in `.ghostrun.yaml`. Accuracy scales with the judge you choose.

Verdicts are cached (see [recording.md](recording.md)), so a suite is
deterministic run-to-run even though the underlying model is stochastic.

## Majority-vote verdicts (`judge.votes`)

Caching a single verdict freezes whatever the judge said on *that one draw* —
including if it was wrong. Published LLM-as-judge reliability studies report
mean flip rates around 13–14% on repeated grading of identical input, even at
temperature 0. `judge.votes` grades N times on a cache miss and caches the
**majority** verdict plus the observed disagreement rate:

```yaml
judge:
  votes: 5   # odd numbers avoid ties; default is 1 (single draw, prior behavior)
```

```
ghostrun.expect(reply).tone_is("empathetic")
# on failure: "[4/5 agreed] the text does not convey warmth"
```

This costs N× the judge inference on a cache miss (replay is always free
regardless of `votes`).

**What voting actually buys you — measured, not assumed.** Benchmarked against
the real `llama3.2:3b` judge (90 live grades, easy/borderline/sarcasm cases, at
temperature 0 and 0.7 — full methodology and numbers in
[`judge-voting-benchmark.md`](../judge-voting-benchmark.md)):

- **5 of 6 test conditions were perfectly reproducible** (0% flip rate) — for
  well-posed criteria at temperature 0 (the shipped default), a single local
  judge draw was already stable across 15 repeats. Voting adds cost with no
  measurable benefit here.
- **The one genuinely ambiguous case** (grading sarcasm at temperature 0.7)
  flipped **46.7%** of the time — a real coin flip. Voting helped only
  marginally and non-monotonically (k=1: 49.6% → k=3: 55.8% → k=5: 51.8%
  reliability against the modal verdict) — **majority voting does not reliably
  rescue a criterion the judge has no real opinion on.**

**Practical takeaway:** `judge.votes` is most useful as a *detector*, not a
*fix*. A high `disagreement_rate` on a cached verdict tells you the criterion
itself is ambiguous or the judge is guessing — a signal to rewrite the
assertion or use a bigger judge, not something more votes will paper over. Keep
`temperature=0` (already the default) for maximum stability; this benchmark is
also why `OllamaJudge` doesn't expose a temperature knob.

## Tool / function calls

Most agent bugs are wrong-tool or wrong-argument bugs, not bad prose. These are
deterministic — no judge, no model:

```python
ghostrun.expect_tool_calls(response.choices[0].message.tool_calls) \
    .called_once("search_orders") \
    .called_with("search_orders", order_id="A123") \
    .did_not_call("issue_refund")
```

OpenAI (`function.arguments` as a JSON string), Anthropic (`input`), and plain
`{"name", "arguments"}` shapes are all normalized automatically.

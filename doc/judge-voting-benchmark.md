# Does majority-vote caching actually fix LLM-judge unreliability?

**A small, honest benchmark — and a negative-ish result worth publishing anyway.**

---

## The question

ghostrun, like several LLM-testing tools, uses an LLM to grade semantic
assertions (`expect(reply).tone_is("empathetic")`) and caches the verdict so
tests are fast and deterministic on replay. But caching a *single* verdict
freezes whatever the judge said on that one draw — including if it was wrong.

Published LLM-as-judge reliability research gives reason to worry. ["The Coin
Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation"](https://arxiv.org/html/2606.13685)
found a mean flip rate of **13.6%** on repeated grading of identical input
(same transcript, same rubric, same model), rising to 56% on the hardest
items, and that **11 repeated trials** are needed for majority vote to recover
a 50-trial reference verdict at 95% confidence. ["Necessary but Not
Sufficient"](https://arxiv.org/html/2606.26185v1) found non-reproducibility
persists even at temperature 0 across 690 calls, two providers, three model
tiers. Both papers recommend the same fix: **multi-trial aggregation and
majority voting.**

So we built it — `judge.votes: k` grades k times on a cache miss and caches
the majority verdict plus the observed disagreement rate — and then, instead
of assuming it worked, benchmarked it against a real judge.

## Method

90 live grading calls to a local `llama3.2:3b` judge (via Ollama), no
synthetic data. Three cases chosen to span difficulty:

| Case | Criterion |
|---|---|
| `easy_control` | "I'm so sorry for the delay with your refund." satisfies "contains an apology" |
| `borderline_tone` | "Well, I suppose your concern is somewhat valid, if you insist." satisfies "genuinely warm and empathetic" |
| `sarcasm` | "Wow, great job breaking it AGAIN. Impressive." satisfies "is sarcastic" |

Each case was graded **15 times** at temperature 0 and again at temperature
0.7 (90 calls total). The modal (most frequent) verdict across the 15 draws
was treated as the judge's "true opinion" for that input. We then
bootstrap-resampled 500 subsets of size k ∈ {1, 3, 5} from the real draws and
measured how often the majority-of-k matched the modal verdict — i.e., how
much more reliable caching k votes is than caching 1, in practice, on this
judge.

## Results

| Case | Temp | Flip rate | k=1 | k=3 | k=5 |
|---|---|---|---|---|---|
| easy_control | 0.0 | 0.0% | 100.0% | 100.0% | 100.0% |
| easy_control | 0.7 | 0.0% | 100.0% | 100.0% | 100.0% |
| borderline_tone | 0.0 | 0.0% | 100.0% | 100.0% | 100.0% |
| borderline_tone | 0.7 | 0.0% | 100.0% | 100.0% | 100.0% |
| sarcasm | 0.0 | 0.0% | 100.0% | 100.0% | 100.0% |
| **sarcasm** | **0.7** | **46.7%** | **49.6%** | **55.8%** | **51.8%** |
| **Average** | | **7.8%** | **91.6%** | **92.6%** | **92.0%** |

**5 of 6 conditions were perfectly reproducible.** At temperature 0 (the
shipped default judge configuration), a single draw was stable across all 15
repeats — for the easy case, the borderline-tone case, *and* the sarcasm case.
Voting bought nothing there because there was nothing to fix.

**The one condition with real variance is the interesting one.** Sarcasm
graded at temperature 0.7 flipped 46.7% of the time — close to an actual coin
flip, and a clean small-scale replication of the "Coin Flip Judge" framing.
Majority voting helped only marginally, and **not monotonically**: k=1 → 49.6%,
k=3 → 55.8%, k=5 → **51.8%** (worse than k=3). Going from 3 votes to 5 made the
cached verdict *less* likely to match the judge's own modal opinion, not more.

## What this means

**Majority-vote caching does not reliably rescue a criterion the judge has no
stable opinion on.** When the underlying grading decision is genuinely close
to 50/50, averaging more noisy draws converges toward a slightly-less-noisy
coin flip — not toward a correct answer, because there isn't a well-defined
correct answer to converge to. This is consistent with, and gives a
small-scale mechanistic account for, why the published literature needs 11+
trials and still reports residual noise: near a decision boundary, more votes
have diminishing and non-monotonic returns.

**The practically useful result is the disagreement rate itself, not the vote
resolution.** A cached verdict with a high `disagreement_rate` is a signal
that the criterion is ambiguous or the judge is guessing on this input — a
prompt to rewrite the assertion or use a stronger judge, not a number that
more votes will reliably fix. ghostrun surfaces this rate on every cached
verdict for exactly this reason: **voting is a better detector of unreliable
assertions than a corrector of them.**

**A secondary, more speculative observation:** average flip rate here (7.8%)
was roughly half the ~13.6% the published literature reports for cloud-served
judges. Published root causes for judge non-determinism — batch-size-dependent
floating-point reduction, MoE routing variance, load-balancing across
non-identical replicas — are specific to multi-tenant, batched, cloud-served
inference. A local, single-tenant Ollama instance processing one request at a
time structurally can't exhibit those particular effects. That's a plausible
explanation, not a proven one: this is six data points on one 3B model, and a
larger replication across more cases, models, and providers would be needed
before treating "local judges are more reproducible than cloud judges" as
established rather than suggestive.

## Practical guidance this produces

- **Keep `judge.votes: 1` and `temperature=0`** (both are ghostrun's defaults)
  for most assertions — the benchmark found no case where voting was needed at
  temperature 0.
- **Treat a nonzero `disagreement_rate` as a code smell in the assertion**,
  not a problem more votes will solve. Rewrite the criterion to be less
  ambiguous, or route it to a stronger judge.
- **Don't expect majority voting to buy monotonic improvement.** k=5 was
  measurably worse than k=3 in the one case where it mattered here; treat any
  single vote count as a hyperparameter with its own noise, not a dial that
  only helps as you turn it up.

## Reproducing this

This write-up lives alongside the `judge.votes` implementation
(`ghostrun/judge/caching.py`) in this repository. The majority-vote mechanism
itself is unit-tested with a scripted judge (no network required) in
`tests/test_judge_voting.py`; this document's numbers come from one live run
against the real judge and are reported as a single run, not an average over
repeated benchmark executions — a caveat worth stating plainly, since the
phenomenon under study is itself run-to-run variance. (Link to the published
repo here once it's public.)

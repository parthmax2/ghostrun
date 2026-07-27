"""Record/replay for judge verdicts, with optional majority-of-k voting.

Caching the LLM *response* but not the *grading* of it leaves the suite
non-deterministic and slow: every run re-invokes a stochastic model, so a green
test can flip red with no code change, and each assertion costs an inference.

``CachingJudge`` closes that gap by recording verdicts with the same semantics
the HTTP interceptor uses for provider calls:

  auto    replay a stored verdict if present, otherwise grade and store it
  record  always re-grade and overwrite the stored verdict
  replay  never invoke the model; a missing verdict is an error

Verdicts are keyed on judge backend + model + text + criterion + vote count, so
changing the judge model, editing an assertion, or changing ``votes`` correctly
forces a re-grade.

Caching a *single* verdict (votes=1, the default) freezes whatever the judge
said on that one draw -- including if it happened to be wrong. Published
LLM-as-judge reliability studies report mean flip rates around 13-14% for small
judges even at temperature 0 (repeated grading of the identical input returns a
different verdict). Setting ``votes`` to an odd number > 1 grades that many
times on a cache miss and caches the *majority* verdict plus the observed
disagreement rate, trading judge cost for a measurably more reliable cached
result -- see ``doc/prd.md`` for the accuracy/cost tradeoff this was benchmarked
against.
"""

from __future__ import annotations

from ..cache import CacheMiss, KVCache, verdict_key
from .base import Grade, Judge


class CachingJudge:
    def __init__(self, inner: Judge, cache: KVCache, mode: str, backend: str, model: str,
                 votes: int = 1):
        if votes < 1:
            raise ValueError(f"judge votes must be >= 1, got {votes}")
        self._inner = inner
        self._cache = cache
        self._mode = mode
        self._backend = backend
        self._model = model
        self._votes = votes

    def grade(self, text: str, criterion: str) -> Grade:
        key = verdict_key(self._backend, self._model, text, criterion, self._votes)

        if self._mode in ("auto", "replay"):
            hit = self._cache.get(key)
            if hit is not None:
                return Grade(
                    passed=bool(hit["passed"]),
                    reason=hit.get("reason", ""),
                    votes=hit.get("votes"),
                    disagreement_rate=float(hit.get("disagreement_rate", 0.0)),
                )

        if self._mode == "replay":
            raise CacheMiss(
                f"No cached judge verdict for criterion {criterion!r} "
                f"(judge={self._backend}:{self._model}, votes={self._votes}, key {key}). "
                f"Re-run with --gentest-record to grade and store it."
            )

        grade = self._vote(text, criterion)
        # Store the graded text/criterion alongside the verdict so the cache file
        # is reviewable in a diff and explains why a test passes.
        self._cache.put(key, {
            "judge": {"backend": self._backend, "model": self._model},
            "criterion": criterion,
            "text": text,
            "votes_requested": self._votes,
            "passed": grade.passed,
            "reason": grade.reason,
            "votes": grade.votes,
            "disagreement_rate": grade.disagreement_rate,
        })
        return grade

    def _vote(self, text: str, criterion: str) -> Grade:
        if self._votes == 1:
            return self._inner.grade(text, criterion)

        draws = [self._inner.grade(text, criterion) for _ in range(self._votes)]
        passes = [d.passed for d in draws]
        n_pass = sum(passes)
        n_fail = len(passes) - n_pass
        majority_passed = n_pass > n_fail
        # An even vote count can tie; break conservatively toward FAIL so a
        # cached verdict never claims confidence the vote didn't actually reach.
        tied = n_pass == n_fail

        agreeing = max(n_pass, n_fail)
        disagreement_rate = (len(passes) - agreeing) / len(passes)

        # Prefer a reason from a draw that agrees with the majority verdict.
        matching = [d.reason for d in draws if d.passed == majority_passed and d.reason]
        reason = matching[0] if matching else (draws[0].reason if draws else "")
        prefix = f"[{agreeing}/{len(passes)} agreed" + (", TIED->FAIL" if tied else "") + "] "
        reason = prefix + reason if reason else prefix.strip()

        return Grade(passed=majority_passed, reason=reason, votes=passes,
                     disagreement_rate=disagreement_rate)

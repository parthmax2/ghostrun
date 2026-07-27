"""Offline stub judge for CI and ghostrun's own test suite.

Uses cheap deterministic heuristics instead of a model, so tests never depend on
Ollama being installed. Selected via ``judge: echo`` / ``GHOSTRUN_JUDGE=echo``.
The heuristic: PASS when every whitespace-delimited word of the criterion (minus
a small stoplist) appears as a substring of the text, case-insensitively.
"""

from __future__ import annotations

from .base import Grade

_STOPWORDS = {
    "a", "an", "the", "is", "are", "of", "to", "and", "or", "in", "on", "for",
    "contains", "contain", "should", "must", "that", "this", "it", "be", "with",
    "intent", "tone", "response", "reply", "text", "expresses", "express",
    "content", "overall", "meets", "criterion", "criteria",
}


class EchoJudge:
    def grade(self, text: str, criterion: str) -> Grade:
        haystack = text.lower()
        tokens = [t for t in _split(criterion.lower()) if t not in _STOPWORDS and len(t) > 1]
        if not tokens:
            return Grade(passed=True, reason="echo: no significant criterion tokens")
        missing = [t for t in tokens if t not in haystack]
        if missing:
            return Grade(passed=False, reason=f"echo: missing {missing}")
        return Grade(passed=True, reason="echo: all criterion tokens present")


def _split(s: str):
    out, cur = [], []
    for ch in s:
        if ch.isalnum() or ch == "_":
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out

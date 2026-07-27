"""Judge protocol and shared prompt construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, runtime_checkable

SYSTEM_PROMPT = (
    "You are a strict grading assistant for automated tests. "
    "You will be given a TEXT and a CRITERION. Decide whether the TEXT satisfies "
    "the CRITERION. Respond with a single word on the first line: PASS or FAIL. "
    "Optionally add a brief reason on the next line. Do not equivocate."
)


def build_user_prompt(text: str, criterion: str) -> str:
    return f"CRITERION: {criterion}\n\nTEXT:\n{text}"


@dataclass
class Grade:
    passed: bool
    reason: str = ""
    # Populated only when the judge graded with votes > 1 (see CachingJudge).
    # `votes` is the raw per-draw pass/fail list; `disagreement_rate` is the
    # fraction of draws that did NOT match the majority -- the same quantity
    # the LLM-as-judge reliability literature calls "flip rate."
    votes: Optional[List[bool]] = None
    disagreement_rate: float = 0.0

    @classmethod
    def parse(cls, raw: str) -> "Grade":
        """Parse a model reply whose first token is PASS/FAIL."""
        stripped = raw.strip()
        upper = stripped.upper()
        # Look at the leading token so trailing rationale doesn't confuse us.
        head = upper.lstrip("*# ").split(None, 1)[0] if upper else ""
        passed = head.startswith("PASS")
        # Reason = everything after the first line, or the whole thing if short.
        lines = stripped.splitlines()
        reason = " ".join(lines[1:]).strip() if len(lines) > 1 else ""
        return cls(passed=passed, reason=reason)


@runtime_checkable
class Judge(Protocol):
    def grade(self, text: str, criterion: str) -> Grade:
        """Return a PASS/FAIL judgement for whether ``text`` meets ``criterion``."""
        ...

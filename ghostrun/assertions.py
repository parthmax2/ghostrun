"""Semantic assertions: ``ghostrun.expect(text).contains_intent(...)`` etc.

``expect`` returns a fluent object whose methods raise ``AssertionError`` on
failure — so they integrate with pytest exactly like ``assert`` does, producing
red F's with a readable message. Each method returns ``self`` for chaining.

Note: the PRD sketched ``ghostrun.assert(...)``, but ``assert`` is a reserved
Python keyword and cannot be an attribute name. ``expect`` is the valid form.
"""

from __future__ import annotations

import json
from typing import Optional

from . import runlog
from .judge import Judge, get_judge


class SemanticAssertionError(AssertionError):
    """Raised when a semantic expectation fails. Subclasses AssertionError so
    pytest reports it as a normal test failure."""


class Expectation:
    def __init__(self, text: str, judge: Optional[Judge] = None):
        if not isinstance(text, str):
            raise TypeError(f"expect() requires a string, got {type(text).__name__}")
        self.text = text
        self._judge = judge  # resolved lazily so config/env can change per-test
        # Register the observed output with the active run snapshot (if any) so
        # prompt versions can be diffed later. No-op outside a recorded run.
        self._output_index = runlog.note_output(text)

    @property
    def judge(self) -> Judge:
        if self._judge is None:
            self._judge = get_judge()
        return self._judge

    def _record(self, kind: str, criterion: str, passed: bool, reason: str = "") -> None:
        runlog.note_assertion(kind, criterion, passed, reason, self._output_index)

    # --- semantic (judge-backed) -------------------------------------------

    def contains_intent(self, intent: str) -> "Expectation":
        criterion = f"The text expresses the intent or content: {intent}"
        grade = self.judge.grade(self.text, criterion)
        self._record("contains_intent", intent, grade.passed, grade.reason)
        if not grade.passed:
            raise SemanticAssertionError(
                _msg(f"expected text to contain intent {intent!r}", self.text, grade.reason)
            )
        return self

    def does_not_contain_intent(self, intent: str) -> "Expectation":
        criterion = f"The text expresses the intent or content: {intent}"
        grade = self.judge.grade(self.text, criterion)
        # The assertion passes when the judge says the intent is absent.
        self._record("does_not_contain_intent", intent, not grade.passed, grade.reason)
        if grade.passed:
            raise SemanticAssertionError(
                _msg(f"expected text to NOT contain intent {intent!r}", self.text, grade.reason)
            )
        return self

    def tone_is(self, tone: str) -> "Expectation":
        criterion = f"The overall tone of the text is {tone}"
        grade = self.judge.grade(self.text, criterion)
        self._record("tone_is", tone, grade.passed, grade.reason)
        if not grade.passed:
            raise SemanticAssertionError(
                _msg(f"expected tone to be {tone!r}", self.text, grade.reason)
            )
        return self

    def matches(self, criterion: str) -> "Expectation":
        """Free-form judge criterion escape hatch."""
        grade = self.judge.grade(self.text, criterion)
        self._record("matches", criterion, grade.passed, grade.reason)
        if not grade.passed:
            raise SemanticAssertionError(
                _msg(f"expected text to satisfy: {criterion}", self.text, grade.reason)
            )
        return self

    def is_grounded_in(self, context: str) -> "Expectation":
        """Assert that an answer is supported by retrieved RAG context."""
        if not isinstance(context, str):
            raise TypeError(f"is_grounded_in() requires a string, got {type(context).__name__}")
        criterion = (
            "The text is fully supported by the provided context and does not "
            "introduce claims, facts, numbers, entities, or recommendations that "
            "are absent from the context.\n\n"
            f"Context:\n{context}"
        )
        grade = self.judge.grade(self.text, criterion)
        self._record("is_grounded_in", "provided context", grade.passed, grade.reason)
        if not grade.passed:
            raise SemanticAssertionError(
                _msg("expected text to be grounded in the provided context", self.text, grade.reason)
            )
        return self

    # --- deterministic (no judge) ------------------------------------------

    def contains(self, substring: str) -> "Expectation":
        ok = substring in self.text
        self._record("contains", substring, ok)
        if not ok:
            raise SemanticAssertionError(
                _msg(f"expected text to contain substring {substring!r}", self.text)
            )
        return self

    def does_not_contain(self, substring: str) -> "Expectation":
        ok = substring not in self.text
        self._record("does_not_contain", substring, ok)
        if not ok:
            raise SemanticAssertionError(
                _msg(f"expected text to NOT contain substring {substring!r}", self.text)
            )
        return self

    def is_valid_json(self) -> "Expectation":
        try:
            json.loads(self.text)
        except (ValueError, TypeError) as exc:
            self._record("is_valid_json", "valid JSON", False, str(exc))
            raise SemanticAssertionError(
                _msg(f"expected valid JSON but parsing failed: {exc}", self.text)
            )
        self._record("is_valid_json", "valid JSON", True)
        return self


class ToolCallExpectation:
    """Assertions over tool/function calls an LLM requested.

    Most agent bugs are wrong-tool or wrong-argument bugs rather than bad prose,
    so these are deterministic checks -- no judge, no model, instant.

    Accepts the shapes providers actually return:
      * OpenAI:    [{"function": {"name": ..., "arguments": "<json string>"}}]
      * Anthropic: [{"name": ..., "input": {...}}]
      * plain:     [{"name": ..., "arguments": {...}}]
    """

    def __init__(self, calls):
        self.calls = [_normalize_tool_call(c) for c in (calls or [])]

    @property
    def names(self):
        return [c["name"] for c in self.calls]

    def called(self, name: str) -> "ToolCallExpectation":
        if name not in self.names:
            raise SemanticAssertionError(
                f"expected tool {name!r} to be called; called: {self.names or 'none'}"
            )
        return self

    def did_not_call(self, name: str) -> "ToolCallExpectation":
        if name in self.names:
            raise SemanticAssertionError(
                f"expected tool {name!r} NOT to be called; called: {self.names}"
            )
        return self

    def called_once(self, name: str) -> "ToolCallExpectation":
        count = self.names.count(name)
        if count != 1:
            raise SemanticAssertionError(
                f"expected tool {name!r} to be called exactly once, got {count}; "
                f"called: {self.names or 'none'}"
            )
        return self

    def call_count(self, expected: int) -> "ToolCallExpectation":
        if len(self.calls) != expected:
            raise SemanticAssertionError(
                f"expected {expected} tool call(s), got {len(self.calls)}: "
                f"{self.names or 'none'}"
            )
        return self

    def called_with(self, name: str, **expected_args) -> "ToolCallExpectation":
        """Assert some call to ``name`` includes these argument values.

        Subset match -- extra arguments the model supplied are ignored.
        """
        self.called(name)
        matching = [c for c in self.calls if c["name"] == name]
        for call in matching:
            args = call["arguments"]
            if all(args.get(k) == v for k, v in expected_args.items()):
                return self
        raise SemanticAssertionError(
            f"no call to {name!r} matched arguments {expected_args}; "
            f"actual calls: {[c['arguments'] for c in matching]}"
        )

    def __len__(self) -> int:
        return len(self.calls)


def _normalize_tool_call(call) -> dict:
    """Flatten provider-specific tool-call shapes into {name, arguments}."""
    if not isinstance(call, dict):
        raise TypeError(f"tool call must be a dict, got {type(call).__name__}")

    # OpenAI nests under "function" and JSON-encodes arguments as a string.
    if "function" in call and isinstance(call["function"], dict):
        fn = call["function"]
        name, raw_args = fn.get("name", ""), fn.get("arguments", {})
    else:
        name = call.get("name", "")
        # Anthropic uses "input"; others use "arguments".
        raw_args = call.get("arguments", call.get("input", {}))

    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except ValueError:
            raw_args = {"__unparsed__": raw_args}
    if not isinstance(raw_args, dict):
        raw_args = {"__value__": raw_args}

    return {"name": name, "arguments": raw_args}


def expect_tool_calls(calls) -> ToolCallExpectation:
    """Assert over tool/function calls, e.g.

        ghostrun.expect_tool_calls(resp.choices[0].message.tool_calls) \\
            .called_once("search_orders") \\
            .called_with("search_orders", order_id="A123") \\
            .did_not_call("issue_refund")
    """
    return ToolCallExpectation(calls)


def _msg(headline: str, text: str, reason: str = "") -> str:
    preview = text if len(text) <= 300 else text[:297] + "..."
    parts = [headline]
    if reason:
        parts.append(f"judge said: {reason}")
    parts.append(f"text was:\n{preview}")
    return "\n".join(parts)


def expect(text: str, *, judge: Optional[Judge] = None) -> Expectation:
    return Expectation(text, judge=judge)

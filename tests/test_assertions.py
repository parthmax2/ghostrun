import pytest

import ghostrun
from ghostrun.assertions import SemanticAssertionError
from ghostrun.judge.base import Grade
from ghostrun.judge.echo import EchoJudge


class ScriptedJudge:
    def __init__(self, passed=True, reason=""):
        self.passed = passed
        self.reason = reason
        self.calls = []

    def grade(self, text, criterion):
        self.calls.append((text, criterion))
        return Grade(passed=self.passed, reason=self.reason)


def test_contains_intent_pass_with_echo():
    ghostrun.expect("I am so sorry for the refund delay").contains_intent("sorry refund")


def test_contains_intent_fail_with_echo():
    with pytest.raises(SemanticAssertionError):
        ghostrun.expect("Have a nice day").contains_intent("apology refund")


def test_does_not_contain_intent():
    ghostrun.expect("Have a nice day").does_not_contain_intent("apology refund")
    with pytest.raises(SemanticAssertionError):
        ghostrun.expect("I am sorry").does_not_contain_intent("sorry")


def test_chaining_returns_self():
    result = (
        ghostrun.expect("sorry about the refund delay")
        .contains_intent("sorry")
        .contains_intent("refund")
    )
    assert result.text.startswith("sorry")


def test_is_valid_json():
    ghostrun.expect('{"a": 1}').is_valid_json()
    with pytest.raises(SemanticAssertionError):
        ghostrun.expect("not json").is_valid_json()


def test_deterministic_contains():
    ghostrun.expect("hello world").contains("world")
    with pytest.raises(SemanticAssertionError):
        ghostrun.expect("hello world").does_not_contain("world")


def test_expect_rejects_non_string():
    with pytest.raises(TypeError):
        ghostrun.expect(123)


def test_grade_parse():
    from ghostrun.judge.base import Grade
    assert Grade.parse("PASS").passed
    assert Grade.parse("pass\nlooks good").passed
    assert not Grade.parse("FAIL\nmissing apology").passed
    assert Grade.parse("FAIL\nmissing apology").reason == "missing apology"


def test_injected_judge_used():
    # explicit judge injection bypasses global config
    e = ghostrun.expect("abc", judge=EchoJudge())
    e.contains_intent("abc")


def test_is_grounded_in_passes_with_supporting_context():
    judge = ScriptedJudge(passed=True, reason="supported by context")
    result = ghostrun.expect("Refunds are processed within 5 days.", judge=judge).is_grounded_in(
        "Refunds are processed within 5 days after approval."
    )

    assert result.text.startswith("Refunds")
    assert judge.calls
    text, criterion = judge.calls[0]
    assert text == "Refunds are processed within 5 days."
    assert "fully supported by the provided context" in criterion
    assert "Refunds are processed within 5 days after approval." in criterion


def test_is_grounded_in_fails_when_answer_adds_unsupported_claims():
    judge = ScriptedJudge(passed=False, reason="24 hours is not in the context")

    with pytest.raises(SemanticAssertionError, match="grounded in the provided context"):
        ghostrun.expect("Refunds are processed within 24 hours.", judge=judge).is_grounded_in(
            "Refunds are processed within 5 days after approval."
        )


def test_is_grounded_in_requires_context_string():
    with pytest.raises(TypeError, match="is_grounded_in"):
        ghostrun.expect("answer", judge=ScriptedJudge()).is_grounded_in(["not", "a", "string"])

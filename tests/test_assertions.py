import pytest

import ghostrun
from ghostrun.assertions import SemanticAssertionError
from ghostrun.judge.echo import EchoJudge


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

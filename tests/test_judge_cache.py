"""Judge verdicts must be recorded and replayed, so semantic assertions are
deterministic and don't re-invoke the model on every run."""

import pytest

from ghostrun.cache import CacheMiss, KVCache, verdict_key
from ghostrun.judge.base import Grade
from ghostrun.judge.caching import CachingJudge


class CountingJudge:
    """Stand-in for a stochastic model: flips its verdict on every call."""

    def __init__(self):
        self.calls = 0

    def grade(self, text, criterion):
        self.calls += 1
        # Alternates PASS/FAIL to prove caching pins the first verdict.
        return Grade(passed=self.calls % 2 == 1, reason=f"call {self.calls}")


def make(tmp_path, mode="auto", model="m1"):
    inner = CountingJudge()
    return inner, CachingJudge(inner, KVCache(tmp_path / "j"), mode, "ollama", model)


def test_verdict_is_cached_and_stable(tmp_path):
    inner, judge = make(tmp_path)
    first = judge.grade("some text", "is empathetic")
    assert inner.calls == 1

    # A stochastic judge would flip here; the cache must pin the verdict.
    for _ in range(3):
        again = judge.grade("some text", "is empathetic")
        assert again.passed == first.passed
    assert inner.calls == 1  # model never re-invoked


def test_different_criterion_grades_again(tmp_path):
    inner, judge = make(tmp_path)
    judge.grade("text", "criterion A")
    judge.grade("text", "criterion B")
    assert inner.calls == 2


def test_different_text_grades_again(tmp_path):
    inner, judge = make(tmp_path)
    judge.grade("text one", "c")
    judge.grade("text two", "c")
    assert inner.calls == 2


def test_changing_judge_model_invalidates(tmp_path):
    inner_a, judge_a = make(tmp_path, model="llama3.2:3b")
    judge_a.grade("t", "c")

    # Same cache dir, different judge model -> must not reuse the old verdict.
    inner_b, judge_b = make(tmp_path, model="qwen2:7b")
    judge_b.grade("t", "c")
    assert inner_b.calls == 1


def test_replay_mode_errors_on_missing_verdict(tmp_path):
    inner, judge = make(tmp_path, mode="replay")
    with pytest.raises(CacheMiss):
        judge.grade("never graded", "c")
    assert inner.calls == 0  # replay never invokes the model


def test_record_mode_overwrites(tmp_path):
    inner, judge = make(tmp_path, mode="record")
    judge.grade("t", "c")
    judge.grade("t", "c")
    assert inner.calls == 2  # record always re-grades


def test_verdict_key_is_stable_and_distinct():
    a = verdict_key("ollama", "m", "text", "crit")
    assert a == verdict_key("ollama", "m", "text", "crit")
    assert a != verdict_key("ollama", "m", "text", "other")
    assert a != verdict_key("ollama", "other", "text", "crit")
    # Field boundaries must be unambiguous (no concatenation collisions).
    assert verdict_key("a", "b", "c", "d") != verdict_key("ab", "", "c", "d")


def test_echo_judge_is_not_wrapped(monkeypatch):
    from ghostrun import config as gt_config
    from ghostrun.judge import get_judge
    from ghostrun.judge.echo import EchoJudge

    monkeypatch.setenv("GHOSTRUN_JUDGE", "echo")
    gt_config.reset_config()
    assert isinstance(get_judge(), EchoJudge)


def test_caching_can_be_disabled(monkeypatch):
    from ghostrun import config as gt_config
    from ghostrun.judge import get_judge
    from ghostrun.judge.ollama import OllamaJudge

    monkeypatch.setenv("GHOSTRUN_JUDGE", "ollama")
    monkeypatch.setenv("GHOSTRUN_JUDGE_CACHE", "false")
    gt_config.reset_config()
    assert isinstance(get_judge(), OllamaJudge)

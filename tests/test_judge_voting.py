"""Majority-of-k judge verdict caching.

A single cached verdict (votes=1) freezes whatever the judge said on one draw,
including if that draw happened to be wrong -- published LLM-as-judge studies
report ~13-14% flip rates on repeated grading of identical input even at
temperature 0. votes>1 grades k times on a cache miss and caches the majority,
plus the observed disagreement rate.
"""

import pytest

from ghostrun.cache import CacheMiss, KVCache, verdict_key
from ghostrun.judge.base import Grade
from ghostrun.judge.caching import CachingJudge


class ScriptedJudge:
    """Returns a pre-programmed sequence of verdicts, one per call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def grade(self, text, criterion):
        passed = self.script[self.calls]
        self.calls += 1
        return Grade(passed=passed, reason=f"draw {self.calls}: {passed}")


def make(tmp_path, script, votes, mode="auto", model="m"):
    inner = ScriptedJudge(script)
    judge = CachingJudge(inner, KVCache(tmp_path / "j"), mode, "ollama", model, votes=votes)
    return inner, judge


# --- backward compatibility -------------------------------------------------

def test_votes_1_matches_prior_single_grade_behavior(tmp_path):
    inner, judge = make(tmp_path, [True], votes=1)
    grade = judge.grade("t", "c")
    assert grade.passed is True
    assert grade.votes is None
    assert grade.disagreement_rate == 0.0
    assert inner.calls == 1


def test_votes_1_key_matches_no_votes_arg():
    # Old call sites (and existing tests) call verdict_key without a votes arg.
    assert verdict_key("ollama", "m", "t", "c") == verdict_key("ollama", "m", "t", "c", 1)


# --- majority voting ---------------------------------------------------------

def test_unanimous_pass(tmp_path):
    inner, judge = make(tmp_path, [True, True, True], votes=3)
    grade = judge.grade("t", "c")
    assert grade.passed is True
    assert grade.disagreement_rate == 0.0
    assert grade.votes == [True, True, True]
    assert inner.calls == 3


def test_majority_pass_with_dissent(tmp_path):
    inner, judge = make(tmp_path, [True, True, False], votes=3)
    grade = judge.grade("t", "c")
    assert grade.passed is True
    assert grade.disagreement_rate == pytest.approx(1 / 3)
    assert "2/3 agreed" in grade.reason


def test_majority_fail_with_dissent(tmp_path):
    inner, judge = make(tmp_path, [False, False, True, False, True], votes=5)
    grade = judge.grade("t", "c")
    assert grade.passed is False
    assert grade.disagreement_rate == pytest.approx(2 / 5)


def test_even_vote_tie_breaks_conservatively_to_fail(tmp_path):
    inner, judge = make(tmp_path, [True, True, False, False], votes=4)
    grade = judge.grade("t", "c")
    assert grade.passed is False
    assert grade.disagreement_rate == 0.5
    assert "TIED" in grade.reason


def test_reason_prefers_a_draw_agreeing_with_majority(tmp_path):
    inner, judge = make(tmp_path, [False, True, True], votes=3)
    grade = judge.grade("t", "c")
    assert grade.passed is True
    assert "draw 2: True" in grade.reason or "draw 3: True" in grade.reason
    assert "draw 1: False" not in grade.reason


def test_votes_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match="votes"):
        CachingJudge(ScriptedJudge([True]), KVCache(tmp_path / "j"), "auto", "o", "m", votes=0)


# --- caching semantics with voting -------------------------------------------

def test_majority_verdict_is_cached_and_stable(tmp_path):
    inner, judge = make(tmp_path, [True, False, True], votes=3)
    first = judge.grade("t", "c")
    assert inner.calls == 3
    for _ in range(3):
        again = judge.grade("t", "c")
        assert again.passed == first.passed
        assert again.disagreement_rate == first.disagreement_rate
    assert inner.calls == 3  # never re-voted


def test_record_mode_revotes_every_call(tmp_path):
    inner, judge = make(tmp_path, [True, True, True, False, False, False], votes=3, mode="record")
    judge.grade("t", "c")
    judge.grade("t", "c")
    assert inner.calls == 6  # 3 votes x 2 calls, no caching in record mode


def test_replay_mode_errors_without_ever_voting(tmp_path):
    inner, judge = make(tmp_path, [True, True, True], votes=3, mode="replay")
    with pytest.raises(CacheMiss):
        judge.grade("never graded", "c")
    assert inner.calls == 0


def test_different_vote_counts_do_not_share_a_cache_entry(tmp_path):
    cache_dir = tmp_path / "j"
    _, judge1 = make(tmp_path, [True], votes=1)
    judge1._cache = KVCache(cache_dir)
    _, judge3 = make(tmp_path, [True, True, False], votes=3)
    judge3._cache = KVCache(cache_dir)

    g1 = judge1.grade("t", "c")
    g3 = judge3.grade("t", "c")
    assert g1.votes is None          # served from the votes=1 cache lane
    assert g3.votes is not None      # served from the votes=3 cache lane, not g1's


def test_disagreement_rate_and_votes_survive_cache_roundtrip(tmp_path):
    inner, judge = make(tmp_path, [True, False, True, True, False], votes=5)
    judge.grade("t", "c")

    # A second judge instance pointed at the same cache dir must replay the
    # same rich verdict, not just the pass/fail bit.
    inner2, judge2 = make(tmp_path, [], votes=5)
    judge2._cache = judge._cache
    replayed = judge2.grade("t", "c")
    assert inner2.calls == 0
    assert replayed.votes == [True, False, True, True, False]
    assert replayed.disagreement_rate == pytest.approx(2 / 5)

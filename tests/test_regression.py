"""Prompt regression tracking: run snapshots, comparison, and CLI."""

import json

import pytest

from ghostrun import runlog
from ghostrun.cli import main
from ghostrun.regression import compare, render_text
from ghostrun.runlog import AssertionRecord, RunLog


def make_run(name, tests):
    """tests: {test_id: (outputs, [(kind, criterion, passed)])}"""
    log = RunLog(name=name)
    for test_id, (outputs, assertions) in tests.items():
        log.ensure_test(test_id)
        for out in outputs:
            log.record_output(test_id, out)
        for kind, criterion, passed in assertions:
            log.record_assertion(test_id, AssertionRecord(
                kind=kind, criterion=criterion, passed=passed,
                reason="because" if not passed else ""))
    return log


# --- comparison ------------------------------------------------------------

def test_detects_regression():
    base = make_run("v1", {"t::a": (["hello"], [("tone_is", "empathetic", True)])})
    cand = make_run("v2", {"t::a": (["hello"], [("tone_is", "empathetic", False)])})
    result = compare(base, cand)
    assert result.has_regressions
    assert len(result.regressions) == 1
    assert result.regressions[0].criterion == "empathetic"
    assert result.summary()["regressions"] == 1


def test_detects_fix():
    base = make_run("v1", {"t::a": ([], [("tone_is", "warm", False)])})
    cand = make_run("v2", {"t::a": ([], [("tone_is", "warm", True)])})
    result = compare(base, cand)
    assert not result.has_regressions
    assert len(result.fixes) == 1


def test_stable_assertions_are_not_regressions():
    base = make_run("v1", {"t::a": ([], [("contains_intent", "refund", True)])})
    cand = make_run("v2", {"t::a": ([], [("contains_intent", "refund", True)])})
    result = compare(base, cand)
    assert not result.has_regressions
    assert result.summary()["stable"] == 1


def test_added_and_removed_assertions():
    base = make_run("v1", {"t::a": ([], [("contains_intent", "old", True)])})
    cand = make_run("v2", {"t::a": ([], [("contains_intent", "new", True)])})
    result = compare(base, cand)
    assert len(result.of_status("added")) == 1
    assert len(result.of_status("removed")) == 1
    # A removed assertion is not a regression -- it's a deliberate edit.
    assert not result.has_regressions


def test_aborted_test_marks_missing_assertions_not_run():
    """An assertion downstream of a failure never ran — calling it 'removed'
    would be wrong and would hide the real regression."""
    base = make_run("v1", {"t::a": ([], [("contains_intent", "sorry", True),
                                         ("contains_intent", "policy", True)])})
    cand = make_run("v2", {"t::a": ([], [("contains_intent", "sorry", False)])})
    cand.tests["t::a"].outcome = "failed"  # aborted at the first assertion

    result = compare(base, cand)
    assert len(result.regressions) == 1
    assert result.of_status("removed") == []          # not a deletion...
    assert len(result.of_status("not_run")) == 1       # ...it just never ran
    assert result.summary()["not_evaluated"] == 1
    assert "NOT EVALUATED" in render_text(result)


def test_passing_test_missing_assertion_is_a_real_removal():
    base = make_run("v1", {"t::a": ([], [("contains", "x", True),
                                         ("contains", "y", True)])})
    cand = make_run("v2", {"t::a": ([], [("contains", "x", True)])})
    cand.tests["t::a"].outcome = "passed"  # ran to completion; y was deleted
    result = compare(base, cand)
    assert len(result.of_status("removed")) == 1
    assert result.of_status("not_run") == []


def test_outcome_survives_save_load(tmp_path):
    log = make_run("v1", {"t::a": ([], [("contains", "x", False)])})
    log.tests["t::a"].outcome = "failed"
    runlog.save(log, tmp_path, name="v1")
    assert runlog.load(tmp_path, "v1").tests["t::a"].aborted is True


def test_added_and_removed_tests():
    base = make_run("v1", {"t::gone": ([], [])})
    cand = make_run("v2", {"t::fresh": ([], [])})
    result = compare(base, cand)
    assert result.tests_removed == ["t::gone"]
    assert result.tests_added == ["t::fresh"]


def test_output_drift_detected_even_when_assertions_pass():
    base = make_run("v1", {"t::a": (["I am sorry"], [("tone_is", "x", True)])})
    cand = make_run("v2", {"t::a": (["My apologies"], [("tone_is", "x", True)])})
    result = compare(base, cand)
    assert not result.has_regressions       # nothing broke...
    assert len(result.changed_outputs) == 1  # ...but the text moved
    drift = result.changed_outputs[0]
    assert 0.0 <= drift.similarity < 1.0
    assert "sorry" in drift.unified_diff()


def test_identical_outputs_report_no_drift():
    base = make_run("v1", {"t::a": (["same"], [])})
    cand = make_run("v2", {"t::a": (["same"], [])})
    result = compare(base, cand)
    assert result.changed_outputs == []
    assert result.outputs[0].similarity == 1.0


def test_duplicate_criteria_are_matched_positionally():
    base = make_run("v1", {"t::a": ([], [("contains", "x", True), ("contains", "x", True)])})
    cand = make_run("v2", {"t::a": ([], [("contains", "x", True), ("contains", "x", False)])})
    result = compare(base, cand)
    assert len(result.regressions) == 1  # only the second one regressed


def test_render_text_mentions_regressions():
    base = make_run("v1", {"t::a": (["a"], [("tone_is", "kind", True)])})
    cand = make_run("v2", {"t::a": (["b"], [("tone_is", "kind", False)])})
    out = render_text(compare(base, cand))
    assert "REGRESSION" in out
    assert "FAILED" in out


def test_render_text_ok_when_clean():
    base = make_run("v1", {"t::a": (["a"], [("tone_is", "kind", True)])})
    out = render_text(compare(base, base))
    assert "OK: no regressions" in out


# --- persistence -----------------------------------------------------------

def test_save_load_roundtrip(tmp_path):
    log = make_run("v1", {"t::a": (["out"], [("tone_is", "kind", True)])})
    runlog.save(log, tmp_path, name="v1")
    loaded = runlog.load(tmp_path, "v1")
    assert loaded.tests["t::a"].outputs == ["out"]
    assert loaded.tests["t::a"].assertions[0].criterion == "kind"
    assert runlog.list_runs(tmp_path) == ["v1"]


def test_load_missing_snapshot_is_actionable(tmp_path):
    with pytest.raises(FileNotFoundError, match="No run snapshot named"):
        runlog.load(tmp_path, "nope")


def test_repeated_identical_output_recorded_once():
    log = RunLog(name="r")
    assert log.record_output("t", "same") == 0
    assert log.record_output("t", "same") == 0
    assert log.tests["t"].outputs == ["same"]


def test_capture_is_noop_outside_a_run():
    runlog.stop_run()
    assert runlog.note_output("orphan") == 0
    runlog.note_assertion("k", "c", True)  # must not raise


# --- CLI -------------------------------------------------------------------

def test_cli_list_empty(tmp_path, capsys):
    assert main(["--cache-dir", str(tmp_path), "list"]) == 0
    assert "No run snapshots" in capsys.readouterr().out


def test_cli_list_and_show(tmp_path, capsys):
    runlog.save(make_run("v1", {"t::a": (["hello"], [("tone_is", "kind", True)])}),
                tmp_path, name="v1")
    assert main(["--cache-dir", str(tmp_path), "list"]) == 0
    assert "v1" in capsys.readouterr().out

    assert main(["--cache-dir", str(tmp_path), "show", "v1"]) == 0
    out = capsys.readouterr().out
    assert "hello" in out and "tone_is" in out


def test_cli_diff_exit_codes(tmp_path, capsys):
    runlog.save(make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])}),
                tmp_path, name="v1")
    runlog.save(make_run("v2", {"t::a": ([], [("tone_is", "kind", False)])}),
                tmp_path, name="v2")

    # Without the flag, a diff reports but still exits 0.
    assert main(["--cache-dir", str(tmp_path), "diff", "v1", "v2"]) == 0
    assert "REGRESSION" in capsys.readouterr().out

    # With it, regressions fail the command -- this is the CI gate.
    assert main(["--cache-dir", str(tmp_path), "diff", "v1", "v2",
                 "--fail-on-regression"]) == 1


def test_cli_diff_clean_run_exits_zero(tmp_path):
    runlog.save(make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])}),
                tmp_path, name="v1")
    assert main(["--cache-dir", str(tmp_path), "diff", "v1", "v1",
                 "--fail-on-regression"]) == 0


def test_cli_diff_json(tmp_path, capsys):
    runlog.save(make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])}),
                tmp_path, name="v1")
    runlog.save(make_run("v2", {"t::a": ([], [("tone_is", "kind", False)])}),
                tmp_path, name="v2")
    main(["--cache-dir", str(tmp_path), "diff", "v1", "v2", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["regressions"] == 1
    assert data["regressions"][0]["criterion"] == "kind"


def test_cli_missing_snapshot_exits_2(tmp_path, capsys):
    assert main(["--cache-dir", str(tmp_path), "diff", "ghost", "other"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()

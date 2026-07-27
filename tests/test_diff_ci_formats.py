"""CI-friendly diff output: GitHub PR comment markdown and JUnit XML.

These are what let a prompt regression show up inline in a pull request or a
CI dashboard, instead of requiring someone to remember to run `ghostrun diff`
locally.
"""

import xml.etree.ElementTree as ET

import pytest

from ghostrun import runlog
from ghostrun.cli import main
from ghostrun.regression import compare, render_github_comment, render_junit
from ghostrun.runlog import AssertionRecord, RunLog


def make_run(name, tests):
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


# --- github-comment ----------------------------------------------------------

def test_github_comment_flags_regression_with_red_x():
    base = make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])})
    cand = make_run("v2", {"t::a": ([], [("tone_is", "kind", False)])})
    out = render_github_comment(compare(base, cand))
    assert ":x:" in out
    assert "regression(s) found" in out
    assert "`t::a`" in out
    assert "`tone_is('kind')`" in out


def test_github_comment_clean_run_shows_checkmark():
    base = make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])})
    out = render_github_comment(compare(base, base))
    assert ":white_check_mark:" in out
    assert ":x:" not in out


def test_github_comment_escapes_pipe_in_reason():
    base = make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])})
    cand = RunLog(name="v2")
    cand.ensure_test("t::a")
    cand.record_assertion("t::a", AssertionRecord(
        kind="tone_is", criterion="kind", passed=False,
        reason="contains a | pipe and\na newline"))
    out = render_github_comment(compare(base, cand))
    # A raw pipe/newline would corrupt the markdown table.
    for line in out.splitlines():
        if "contains a" in line:
            assert line.count("|") == line.count("\\|") + 4  # table pipes only, reason's is escaped


def test_github_comment_includes_output_drift():
    base = make_run("v1", {"t::a": (["before text"], [])})
    cand = make_run("v2", {"t::a": (["after text"], [])})
    out = render_github_comment(compare(base, cand))
    assert "Output drift" in out
    assert "```diff" in out


def test_github_comment_omits_empty_sections():
    base = make_run("v1", {"t::a": ([], [("c", "x", True)])})
    out = render_github_comment(compare(base, base))
    assert "Regressions" not in out
    assert "Fixes" not in out
    assert "Output drift" not in out


# --- junit --------------------------------------------------------------------

def test_junit_is_well_formed_xml():
    base = make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])})
    cand = make_run("v2", {"t::a": ([], [("tone_is", "kind", False)])})
    xml_text = render_junit(compare(base, cand))
    root = ET.fromstring(xml_text)  # raises if malformed
    assert root.tag == "testsuite"


def test_junit_regression_becomes_failure():
    base = make_run("v1", {"t::a": ([], [("tone_is", "kind", True)])})
    cand = make_run("v2", {"t::a": ([], [("tone_is", "kind", False)])})
    root = ET.fromstring(render_junit(compare(base, cand)))
    assert root.attrib["failures"] == "1"
    case = root.find("testcase")
    assert case is not None
    failure = case.find("failure")
    assert failure is not None
    assert "regression" in failure.attrib["message"]


def test_junit_stable_assertions_are_not_testcases():
    """Stable (unchanged) assertions shouldn't bloat every CI dashboard run
    with noise -- only what changed is interesting."""
    base = make_run("v1", {"t::a": ([], [("c", "x", True), ("c", "y", True)])})
    cand = make_run("v2", {"t::a": ([], [("c", "x", True), ("c", "y", False)])})
    root = ET.fromstring(render_junit(compare(base, cand)))
    assert root.attrib["tests"] == "1"  # only the regressed one, not the stable one


def test_junit_not_run_becomes_skipped():
    base = make_run("v1", {"t::a": ([], [("c", "x", True), ("c", "y", True)])})
    cand = make_run("v2", {"t::a": ([], [("c", "x", False)])})
    cand.tests["t::a"].outcome = "failed"
    root = ET.fromstring(render_junit(compare(base, cand)))
    skipped = root.find(".//skipped")
    assert skipped is not None


def test_junit_clean_run_has_zero_failures():
    base = make_run("v1", {"t::a": ([], [("c", "x", True)])})
    root = ET.fromstring(render_junit(compare(base, base)))
    assert root.attrib["failures"] == "0"
    assert root.attrib["tests"] == "0"  # nothing non-stable to report


# --- CLI wiring ----------------------------------------------------------------

def test_cli_format_github_comment(tmp_path, capsys):
    runlog.save(make_run("v1", {"t::a": ([], [("c", "x", True)])}), tmp_path, name="v1")
    runlog.save(make_run("v2", {"t::a": ([], [("c", "x", False)])}), tmp_path, name="v2")
    rc = main(["--cache-dir", str(tmp_path), "diff", "v1", "v2", "--format", "github-comment"])
    assert rc == 0  # format selection alone doesn't gate exit code
    assert ":x:" in capsys.readouterr().out


def test_cli_format_junit_to_file(tmp_path):
    runlog.save(make_run("v1", {"t::a": ([], [("c", "x", True)])}), tmp_path, name="v1")
    runlog.save(make_run("v2", {"t::a": ([], [("c", "x", False)])}), tmp_path, name="v2")
    out_file = tmp_path / "results.xml"
    rc = main(["--cache-dir", str(tmp_path), "diff", "v1", "v2",
               "--format", "junit", "-o", str(out_file), "--fail-on-regression"])
    assert rc == 1
    ET.parse(out_file)  # must be valid, parseable XML on disk


def test_cli_json_flag_still_works_as_shorthand(tmp_path, capsys):
    """--json predates --format; must keep working for existing CI configs."""
    runlog.save(make_run("v1", {"t::a": ([], [("c", "x", True)])}), tmp_path, name="v1")
    rc = main(["--cache-dir", str(tmp_path), "diff", "v1", "v1", "--json"])
    assert rc == 0
    import json
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["regressions"] == 0

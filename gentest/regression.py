"""Compare two run snapshots to answer: did this prompt change break anything?

Classifies every assertion across two runs into:

  regression  PASS -> FAIL   (the thing you actually care about)
  fix         FAIL -> PASS
  stable      unchanged verdict
  added/removed  assertion or test present in only one run

Output drift is reported separately: an LLM response can change substantially
while still satisfying every assertion, which is worth seeing before it turns
into a regression later.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .runlog import RunLog, TestRecord


@dataclass
class AssertionDelta:
    test_id: str
    kind: str
    criterion: str
    before: Optional[bool]
    after: Optional[bool]
    before_reason: str = ""
    after_reason: str = ""
    # Whether the corresponding run's test aborted before finishing.
    before_aborted: bool = False
    after_aborted: bool = False

    @property
    def status(self) -> str:
        if self.before is None and self.after is None:
            return "stable"
        if self.before is None:
            # Absent from the baseline: genuinely new, unless that run aborted
            # before reaching it.
            return "not_run_before" if self.before_aborted else "added"
        if self.after is None:
            # Absent from the candidate. If the candidate test aborted, this
            # assertion never executed -- reporting it as "removed" would be a
            # lie, and it usually sits downstream of the real regression.
            return "not_run" if self.after_aborted else "removed"
        if self.before and not self.after:
            return "regression"
        if not self.before and self.after:
            return "fix"
        return "stable"


@dataclass
class OutputDelta:
    test_id: str
    index: int
    before: str
    after: str

    @property
    def changed(self) -> bool:
        return self.before != self.after

    @property
    def similarity(self) -> float:
        """0.0-1.0 ratio; 1.0 means identical."""
        if self.before == self.after:
            return 1.0
        return difflib.SequenceMatcher(None, self.before, self.after).ratio()

    def unified_diff(self, context: int = 2) -> str:
        return "\n".join(difflib.unified_diff(
            self.before.splitlines(), self.after.splitlines(),
            fromfile="before", tofile="after", lineterm="", n=context,
        ))


@dataclass
class Comparison:
    baseline_name: str
    candidate_name: str
    assertions: List[AssertionDelta] = field(default_factory=list)
    outputs: List[OutputDelta] = field(default_factory=list)
    tests_added: List[str] = field(default_factory=list)
    tests_removed: List[str] = field(default_factory=list)

    def of_status(self, status: str) -> List[AssertionDelta]:
        return [a for a in self.assertions if a.status == status]

    @property
    def regressions(self) -> List[AssertionDelta]:
        return self.of_status("regression")

    @property
    def fixes(self) -> List[AssertionDelta]:
        return self.of_status("fix")

    @property
    def changed_outputs(self) -> List[OutputDelta]:
        return [o for o in self.outputs if o.changed]

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)

    def summary(self) -> Dict[str, int]:
        return {
            "regressions": len(self.regressions),
            "fixes": len(self.fixes),
            "stable": len(self.of_status("stable")),
            "added": len(self.of_status("added")),
            "removed": len(self.of_status("removed")),
            "not_evaluated": len(self.of_status("not_run")),
            "outputs_changed": len(self.changed_outputs),
            "tests_added": len(self.tests_added),
            "tests_removed": len(self.tests_removed),
        }


def _assertion_index(rec: TestRecord) -> Dict[Tuple[str, str], object]:
    """Key assertions by (kind, criterion) so they match across runs even if
    ordering changed. Duplicates get a positional suffix."""
    out: Dict[Tuple[str, str], object] = {}
    seen: Dict[Tuple[str, str], int] = {}
    for a in rec.assertions:
        base = (a.kind, a.criterion)
        n = seen.get(base, 0)
        seen[base] = n + 1
        key = base if n == 0 else (a.kind, f"{a.criterion} #{n + 1}")
        out[key] = a
    return out


def compare(baseline: RunLog, candidate: RunLog) -> Comparison:
    cmp_result = Comparison(baseline_name=baseline.name, candidate_name=candidate.name)

    base_ids, cand_ids = set(baseline.tests), set(candidate.tests)
    cmp_result.tests_added = sorted(cand_ids - base_ids)
    cmp_result.tests_removed = sorted(base_ids - cand_ids)

    for test_id in sorted(base_ids | cand_ids):
        b = baseline.tests.get(test_id)
        c = candidate.tests.get(test_id)

        # Output drift, positionally paired.
        b_outs = b.outputs if b else []
        c_outs = c.outputs if c else []
        for i in range(max(len(b_outs), len(c_outs))):
            cmp_result.outputs.append(OutputDelta(
                test_id=test_id,
                index=i,
                before=b_outs[i] if i < len(b_outs) else "",
                after=c_outs[i] if i < len(c_outs) else "",
            ))

        b_idx = _assertion_index(b) if b else {}
        c_idx = _assertion_index(c) if c else {}
        for key in sorted(set(b_idx) | set(c_idx)):
            ba = b_idx.get(key)
            ca = c_idx.get(key)
            cmp_result.assertions.append(AssertionDelta(
                test_id=test_id,
                kind=key[0],
                criterion=key[1],
                before=ba.passed if ba else None,
                after=ca.passed if ca else None,
                before_reason=ba.reason if ba else "",
                after_reason=ca.reason if ca else "",
                before_aborted=bool(b and b.aborted),
                after_aborted=bool(c and c.aborted),
            ))

    return cmp_result


# --- rendering -------------------------------------------------------------

_MARK = {
    "regression": "REGRESSION",
    "fix": "FIXED",
    "added": "ADDED",
    "removed": "REMOVED",
    "not_run": "NOT EVALUATED (test aborted earlier)",
    "not_run_before": "NOT EVALUATED IN BASELINE",
}


def render_text(cmp_result: Comparison, show_diffs: bool = True,
                verbose: bool = False) -> str:
    lines: List[str] = []
    lines.append(f"Comparing {cmp_result.baseline_name} -> {cmp_result.candidate_name}")
    lines.append("=" * 72)

    s = cmp_result.summary()
    lines.append(
        f"{s['regressions']} regression(s), {s['fixes']} fix(es), "
        f"{s['stable']} stable, {s['outputs_changed']} output(s) changed"
    )
    if s["tests_added"] or s["tests_removed"]:
        lines.append(
            f"tests added: {s['tests_added']}, removed: {s['tests_removed']}")
    lines.append("")

    for status in ("regression", "fix", "not_run", "not_run_before", "added", "removed"):
        items = cmp_result.of_status(status)
        if not items:
            continue
        lines.append(f"{_MARK[status]} ({len(items)})")
        for a in items:
            lines.append(f"  {a.test_id}")
            lines.append(f"    {a.kind}({a.criterion!r})")
            if status == "regression" and a.after_reason:
                lines.append(f"    judge: {a.after_reason}")
            if status == "fix" and a.before_reason:
                lines.append(f"    was: {a.before_reason}")
        lines.append("")

    changed = cmp_result.changed_outputs
    if changed:
        lines.append(f"OUTPUT DRIFT ({len(changed)})")
        for o in changed:
            pct = f"{o.similarity * 100:.0f}% similar"
            lines.append(f"  {o.test_id} [output {o.index}] ({pct})")
            if show_diffs:
                diff = o.unified_diff()
                for dline in diff.splitlines():
                    lines.append(f"    {dline}")
        lines.append("")

    if verbose:
        stable = cmp_result.of_status("stable")
        if stable:
            lines.append(f"STABLE ({len(stable)})")
            for a in stable:
                verdict = "pass" if a.after else "fail"
                lines.append(f"  {a.test_id}: {a.kind}({a.criterion!r}) [{verdict}]")
            lines.append("")

    if cmp_result.has_regressions:
        lines.append(f"FAILED: {len(cmp_result.regressions)} regression(s) detected.")
    else:
        lines.append("OK: no regressions.")
    return "\n".join(lines)


def render_github_comment(cmp_result: Comparison, show_diffs: bool = True) -> str:
    """Markdown suitable for posting as a PR comment (`gh pr comment --body-file`
    or a GitHub Actions step). Collapsed detail sections keep a clean suite from
    dumping a wall of stable-assertion noise into the PR."""
    s = cmp_result.summary()
    lines: List[str] = []

    if cmp_result.has_regressions:
        lines.append(f"### :x: GenTest: {s['regressions']} regression(s) found")
    else:
        lines.append("### :white_check_mark: GenTest: no regressions")
    lines.append(
        f"Comparing `{cmp_result.baseline_name}` -> `{cmp_result.candidate_name}`  \n"
        f"{s['regressions']} regression(s), {s['fixes']} fix(es), "
        f"{s['stable']} stable, {s['outputs_changed']} output(s) changed"
    )

    if cmp_result.regressions:
        lines.append("\n<details open><summary><b>Regressions</b></summary>\n")
        lines.append("| Test | Assertion | Judge reason |")
        lines.append("|---|---|---|")
        for a in cmp_result.regressions:
            reason = (a.after_reason or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{a.test_id}` | `{a.kind}({a.criterion!r})` | {reason} |")
        lines.append("\n</details>")

    if cmp_result.fixes:
        lines.append("\n<details><summary>Fixes</summary>\n")
        lines.append("| Test | Assertion |")
        lines.append("|---|---|")
        for a in cmp_result.fixes:
            lines.append(f"| `{a.test_id}` | `{a.kind}({a.criterion!r})` |")
        lines.append("\n</details>")

    changed = cmp_result.changed_outputs
    if changed:
        lines.append(f"\n<details><summary>Output drift ({len(changed)})</summary>\n")
        for o in changed:
            lines.append(f"**`{o.test_id}`** [output {o.index}] - "
                         f"{o.similarity * 100:.0f}% similar")
            if show_diffs:
                lines.append(f"```diff\n{o.unified_diff()}\n```")
        lines.append("</details>")

    lines.append(f"\n<sub>gentest diff {cmp_result.baseline_name} "
                 f"{cmp_result.candidate_name}</sub>")
    return "\n".join(lines)


def render_junit(cmp_result: Comparison) -> str:
    """JUnit XML so a regression diff plugs into any CI system's test-results
    view (GitHub Actions annotations, GitLab, Jenkins, etc.) without that
    system needing to know anything about GenTest specifically. One <testcase>
    per assertion delta; a regression is a <failure>."""
    import xml.etree.ElementTree as ET

    non_stable = [a for a in cmp_result.assertions if a.status != "stable"]
    failures = sum(1 for a in non_stable if a.status == "regression")

    suite = ET.Element("testsuite", {
        "name": f"gentest-diff.{cmp_result.baseline_name}-vs-{cmp_result.candidate_name}",
        "tests": str(len(non_stable)),
        "failures": str(failures),
    })
    for a in non_stable:
        case = ET.SubElement(suite, "testcase", {
            "classname": a.test_id,
            "name": f"{a.kind}({a.criterion})",
        })
        if a.status == "regression":
            failure = ET.SubElement(case, "failure", {
                "message": f"regression: passed in {cmp_result.baseline_name}, "
                          f"failed in {cmp_result.candidate_name}",
            })
            failure.text = a.after_reason or ""
        elif a.status in ("not_run", "not_run_before"):
            ET.SubElement(case, "skipped", {"message": _MARK[a.status]})
        # fix / added / removed are informational, not failures -- no child
        # element needed for a JUnit-consuming dashboard to mark them green.

    return ET.tostring(suite, encoding="unicode")

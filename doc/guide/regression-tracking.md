# Prompt regression tracking

Did that prompt tweak break anything? Snapshot a run, change the prompt, snapshot
again, and diff:

```bash
pytest --gentest-snapshot v1 --gentest-label "original prompt"
# ... edit your prompt ...
pytest --gentest-snapshot v2 --gentest-label "added few-shot examples"

gentest diff v1 v2
```

```
Comparing v1 -> v2
========================================================================
1 regression(s), 0 fix(es), 1 stable, 1 output(s) changed

REGRESSION (1)
  test_support.py::test_reply
    contains_intent('sorry')
    judge: the text does not apologize

OUTPUT DRIFT (1)
  test_support.py::test_reply [output 0] (45% similar)
    --- before
    +++ after
    @@ -1 +1 @@
    -I'm so sorry about the delay with your refund...
    +Your refund request is in the queue...

FAILED: 1 regression(s) detected.
```

Every run also writes a `_last` snapshot, so `gentest diff v1` (candidate
defaults to `_last`) works without planning ahead.

**Output drift** is reported separately from regressions: a response can change
substantially while still passing every assertion, which is worth seeing before
it becomes a regression later.

Assertions that never executed because a test aborted at an earlier failure are
reported as **NOT EVALUATED**, not "removed" — so a single failure doesn't
masquerade as a pile of deleted checks.

## CLI

```bash
gentest list                              # saved snapshots
gentest show v1                           # outputs + verdicts for one run
gentest diff v1 v2                        # compare
gentest diff v1 v2 --format json          # machine-readable
gentest diff v1 v2 --fail-on-regression   # exit 1 on any PASS -> FAIL (CI gate)
gentest diff v1 v2 --format github-comment -o comment.md   # markdown for a PR bot
gentest diff v1 v2 --format junit -o gentest.xml            # for CI test-result dashboards
```

## Posting a regression diff as a PR comment

A regression a developer has to remember to check for locally gets missed. One
that shows up inline in the PR doesn't. In a GitHub Actions workflow:

```yaml
- name: Record this PR's outputs
  run: pytest --gentest-snapshot pr-${{ github.event.pull_request.number }}

- name: Diff against main's baseline
  run: |
    gentest diff main-baseline pr-${{ github.event.pull_request.number }} \
      --format github-comment -o comment.md
    echo "exit_code=$?" >> "$GITHUB_OUTPUT"
  id: diff
  continue-on-error: true

- name: Post as a PR comment
  run: gh pr comment ${{ github.event.pull_request.number }} --body-file comment.md
  env:
    GH_TOKEN: ${{ github.token }}

- name: Fail the job if a regression was found
  if: steps.diff.outputs.exit_code == '1'
  run: exit 1
```

`--format junit` instead produces standard JUnit XML, so a prompt regression
shows up in whatever test-results view your CI already renders (GitHub Actions
annotations, GitLab, Jenkins) without that system needing to know anything
about GenTest.

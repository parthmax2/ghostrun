"""Per-run capture of LLM outputs and judge verdicts.

Phase 2 / Feature 4: prompt regression tracking. To answer "did prompt V2 make
anything worse than V1?" we need more than a pass/fail — we need the actual text
each test saw and how each criterion was graded, snapshotted per run so two runs
can be compared.

Every value passed to ``ghostrun.expect(...)`` is recorded against the currently
running test, along with each assertion's criterion and verdict. Snapshots land
in ``<cache_dir>/runs/`` as readable JSON.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

RUNS_DIRNAME = "runs"
LAST_RUN_NAME = "_last"


@dataclass
class AssertionRecord:
    kind: str            # e.g. "contains_intent", "tone_is"
    criterion: str       # the human-meaningful argument
    passed: bool
    reason: str = ""
    output_index: int = 0  # which captured output this graded

    def to_json(self) -> dict:
        return {
            "kind": self.kind,
            "criterion": self.criterion,
            "passed": self.passed,
            "reason": self.reason,
            "output_index": self.output_index,
        }

    @classmethod
    def from_json(cls, d: dict) -> "AssertionRecord":
        return cls(
            kind=d.get("kind", ""),
            criterion=d.get("criterion", ""),
            passed=bool(d.get("passed", False)),
            reason=d.get("reason", ""),
            output_index=int(d.get("output_index", 0)),
        )


@dataclass
class TestRecord:
    test_id: str
    outputs: List[str] = field(default_factory=list)
    assertions: List[AssertionRecord] = field(default_factory=list)
    # "passed" | "failed" | "skipped" | "" (unknown). Needed to tell a deliberately
    # deleted assertion apart from one that never ran because the test aborted.
    outcome: str = ""

    def to_json(self) -> dict:
        return {
            "test_id": self.test_id,
            "outcome": self.outcome,
            "outputs": self.outputs,
            "assertions": [a.to_json() for a in self.assertions],
        }

    @classmethod
    def from_json(cls, d: dict) -> "TestRecord":
        return cls(
            test_id=d["test_id"],
            outputs=list(d.get("outputs", [])),
            assertions=[AssertionRecord.from_json(a) for a in d.get("assertions", [])],
            outcome=d.get("outcome", ""),
        )

    @property
    def aborted(self) -> bool:
        """True when the test stopped early, so later assertions never ran."""
        return self.outcome in ("failed", "skipped")

    @property
    def passed(self) -> bool:
        return all(a.passed for a in self.assertions)


@dataclass
class RunLog:
    name: str
    created: str = ""
    label: str = ""  # free-form, e.g. the prompt version under test
    tests: Dict[str, TestRecord] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def ensure_test(self, test_id: str) -> TestRecord:
        """Register a test even if it records nothing.

        Without this, a test that makes no assertions is absent from the
        snapshot and its later removal can't be distinguished from it never
        having existed.
        """
        return self.tests.setdefault(test_id, TestRecord(test_id))

    def record_output(self, test_id: str, text: str) -> int:
        rec = self.tests.setdefault(test_id, TestRecord(test_id))
        # Same text asserted repeatedly is one output, not many.
        if rec.outputs and rec.outputs[-1] == text:
            return len(rec.outputs) - 1
        if text in rec.outputs:
            return rec.outputs.index(text)
        rec.outputs.append(text)
        return len(rec.outputs) - 1

    def record_assertion(self, test_id: str, record: AssertionRecord) -> None:
        rec = self.tests.setdefault(test_id, TestRecord(test_id))
        rec.assertions.append(record)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "created": self.created,
            "label": self.label,
            "tests": {k: v.to_json() for k, v in sorted(self.tests.items())},
        }

    @classmethod
    def from_json(cls, d: dict) -> "RunLog":
        return cls(
            name=d.get("name", ""),
            created=d.get("created", ""),
            label=d.get("label", ""),
            tests={k: TestRecord.from_json(v) for k, v in (d.get("tests") or {}).items()},
        )


# --- storage ---------------------------------------------------------------

def runs_dir(cache_dir) -> Path:
    return Path(cache_dir) / RUNS_DIRNAME


def save(log: RunLog, cache_dir, name: Optional[str] = None) -> Path:
    directory = runs_dir(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name or log.name}.json"
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(log.to_json(), fh, indent=2, ensure_ascii=False)
    os.replace(tmp, target)
    return target


def load(cache_dir, name: str) -> RunLog:
    path = runs_dir(cache_dir) / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"No run snapshot named {name!r} in {runs_dir(cache_dir)}. "
            f"Available: {', '.join(list_runs(cache_dir)) or 'none'}"
        )
    with path.open("r", encoding="utf-8") as fh:
        return RunLog.from_json(json.load(fh))


def list_runs(cache_dir) -> List[str]:
    directory = runs_dir(cache_dir)
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


# --- active run (set by the pytest plugin) ---------------------------------

_lock = threading.RLock()
_active: Optional[RunLog] = None
_current_test: Optional[str] = None


def start_run(name: str = LAST_RUN_NAME, label: str = "") -> RunLog:
    global _active
    with _lock:
        _active = RunLog(name=name, label=label)
        return _active


def get_active() -> Optional[RunLog]:
    return _active


def stop_run() -> Optional[RunLog]:
    global _active, _current_test
    with _lock:
        log, _active, _current_test = _active, None, None
        return log


def set_current_test(test_id: Optional[str]) -> None:
    global _current_test
    _current_test = test_id
    with _lock:
        if _active is not None and test_id is not None:
            _active.ensure_test(test_id)


def note_output(text: str) -> int:
    """Record an observed LLM output against the current test. Returns its index."""
    with _lock:
        if _active is None or _current_test is None:
            return 0
        return _active.record_output(_current_test, text)


def set_test_outcome(test_id: str, outcome: str) -> None:
    with _lock:
        if _active is None:
            return
        _active.ensure_test(test_id).outcome = outcome


def note_assertion(kind: str, criterion: str, passed: bool, reason: str = "",
                   output_index: int = 0) -> None:
    with _lock:
        if _active is None or _current_test is None:
            return
        _active.record_assertion(
            _current_test,
            AssertionRecord(kind=kind, criterion=criterion, passed=passed,
                            reason=reason, output_index=output_index),
        )

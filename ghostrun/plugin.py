"""Pytest plugin: CLI flags and a ``ghostrun_record`` fixture.

Registered via the ``pytest11`` entry point in pyproject.toml, so it activates
automatically once ghostrun is installed — no conftest wiring needed.

Flags:
  --ghostrun-record   force record mode (overwrite cache) for this run
  --ghostrun-replay   force replay mode (fail on cache miss)
  --ghostrun-judge    override the judge backend (e.g. "echo")

These map onto the same config the decorator reads, so a single flag flips the
whole suite between recording new fixtures and replaying them in CI.
"""

from __future__ import annotations

import pytest

from . import config as _config
from . import interceptor as _interceptor
from . import mascot as _mascot
from . import runlog
from .cache import Cache
from .interceptor import Interceptor


def pytest_addoption(parser):
    group = parser.getgroup("ghostrun", "ghostrun — LLM record/replay & semantic assertions")
    group.addoption("--ghostrun-record", action="store_true", default=False,
                    help="Force record mode: hit the network and overwrite the cache.")
    group.addoption("--ghostrun-replay", action="store_true", default=False,
                    help="Force replay mode: never hit the network; cache miss is an error.")
    group.addoption("--ghostrun-judge", action="store", default=None,
                    help="Override judge backend for this run (e.g. 'echo', 'ollama').")
    group.addoption("--ghostrun-snapshot", action="store", default=None,
                    metavar="NAME",
                    help="Save this run's outputs and verdicts as snapshot NAME "
                         "for later comparison (see `ghostrun diff`).")
    group.addoption("--ghostrun-label", action="store", default=None,
                    metavar="TEXT",
                    help="Free-form label stored with the snapshot, e.g. a prompt version.")


def pytest_configure(config):
    overrides = {}
    if config.getoption("--ghostrun-record") and config.getoption("--ghostrun-replay"):
        raise pytest.UsageError("--ghostrun-record and --ghostrun-replay are mutually exclusive")
    if config.getoption("--ghostrun-record"):
        overrides["mode"] = "record"
    if config.getoption("--ghostrun-replay"):
        overrides["mode"] = "replay"
    judge = config.getoption("--ghostrun-judge")
    if judge:
        overrides["judge"] = judge

    if overrides:
        # Ensure a base config exists, then layer CLI overrides on top.
        _config.set_config(_config.get_config().with_overrides(**overrides))

    _interceptor.reset_stats()
    config.addinivalue_line("markers", "ghostrun: mark a test as using ghostrun record/replay.")

    # Always capture a run snapshot so `ghostrun diff _last <name>` works without
    # the user having planned ahead.
    runlog.start_run(
        name=config.getoption("--ghostrun-snapshot") or runlog.LAST_RUN_NAME,
        label=config.getoption("--ghostrun-label") or "",
    )


def pytest_runtest_setup(item):
    runlog.set_current_test(item.nodeid)


def pytest_runtest_teardown(item, nextitem):
    runlog.set_current_test(None)


def pytest_runtest_logreport(report):
    # Record the call-phase outcome so the diff can distinguish an assertion the
    # author deleted from one that never ran because the test aborted earlier.
    if report.when == "call":
        runlog.set_test_outcome(report.nodeid, report.outcome)
    elif report.when == "setup" and report.outcome == "skipped":
        runlog.set_test_outcome(report.nodeid, "skipped")


def pytest_sessionfinish(session, exitstatus):
    log = runlog.stop_run()
    if log is None or not log.tests:
        return
    cache_dir = _config.get_config().cache_dir
    # Always refresh `_last`; also write the named snapshot when one was asked for.
    runlog.save(log, cache_dir, name=runlog.LAST_RUN_NAME)
    explicit = session.config.getoption("--ghostrun-snapshot")
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if explicit:
        path = runlog.save(log, cache_dir, name=explicit)
        if reporter is not None:
            reporter.write_line(f"[ghostrun] saved snapshot {explicit!r} -> {path}")

    if reporter is not None:
        block = _mascot.render(_interceptor.get_stats())
        if block:
            reporter.write_line(block)


@pytest.fixture
def ghostrun_record():
    """Fixture form of the decorator for tests that prefer explicit setup.

        def test_x(ghostrun_record):
            with ghostrun_record():
                reply = call_llm(...)
    """
    def factory(mode=None, cache_dir=None):
        cfg = _config.get_config()
        return Interceptor(Cache(cache_dir or cfg.cache_dir), mode or cfg.mode)
    return factory

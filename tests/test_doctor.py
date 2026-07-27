"""`gentest doctor` and `OllamaJudge.is_available()` -- offline, no real
Ollama or network required. All Ollama-backend checks use httpx.MockTransport
so this suite stays hermetic."""

import httpx
import pytest

from gentest import config as gt_config
from gentest.cli import main
from gentest.judge.ollama import OllamaJudge


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_is_available_true_when_model_pulled(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _client(handler).get(url))

    ok, reason = OllamaJudge("llama3.2:3b").is_available()
    assert ok
    assert "pulled" in reason


def test_is_available_false_when_model_missing(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"models": [{"name": "other-model:1b"}]})
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _client(handler).get(url))

    ok, reason = OllamaJudge("llama3.2:3b").is_available()
    assert not ok
    assert "ollama pull llama3.2:3b" in reason


def test_is_available_false_when_daemon_unreachable(monkeypatch):
    def raise_connect_error(url, timeout):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx, "get", raise_connect_error)

    ok, reason = OllamaJudge("llama3.2:3b").is_available()
    assert not ok
    assert "ollama serve" in reason


def test_is_available_false_on_bad_status(monkeypatch):
    def handler(request):
        return httpx.Response(500)
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _client(handler).get(url))

    ok, reason = OllamaJudge("llama3.2:3b").is_available()
    assert not ok
    assert "500" in reason


# --- gentest doctor CLI ------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    monkeypatch.setenv("GENTEST_CACHE_DIR", str(tmp_path / "cache"))
    gt_config.reset_config()
    yield
    gt_config.reset_config()


def test_doctor_echo_judge_passes_without_network(monkeypatch, capsys):
    monkeypatch.setenv("GENTEST_JUDGE", "echo")
    gt_config.reset_config()
    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[OK  ] judge: echo" in out
    assert "All checks passed." in out


def test_doctor_reports_cache_dir_and_httpx_ok(monkeypatch, capsys):
    monkeypatch.setenv("GENTEST_JUDGE", "echo")
    gt_config.reset_config()
    main(["doctor"])
    out = capsys.readouterr().out
    assert "[OK  ] httpx:" in out
    assert "[OK  ] cache dir:" in out


def test_doctor_fails_when_ollama_unreachable(monkeypatch, capsys):
    monkeypatch.setenv("GENTEST_JUDGE", "ollama")
    monkeypatch.setenv("GENTEST_JUDGE_BASE_URL", "http://localhost:1")
    gt_config.reset_config()

    def raise_connect_error(url, timeout):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx, "get", raise_connect_error)

    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] judge:" in out
    assert "Some checks failed" in out


def test_doctor_prints_resolved_config(monkeypatch, capsys):
    monkeypatch.setenv("GENTEST_JUDGE", "echo")
    monkeypatch.setenv("GENTEST_JUDGE_VOTES", "3")
    gt_config.reset_config()
    main(["doctor"])
    out = capsys.readouterr().out
    assert "judge_votes = 3" in out


def test_doctor_unwritable_cache_dir_fails(monkeypatch, capsys):
    monkeypatch.setenv("GENTEST_JUDGE", "echo")
    # Point cache_dir at a path that cannot be created (a file, not a dir, as
    # an existing path component -- mkdir must fail with a real OSError).
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        blocked_file = f.name
    monkeypatch.setenv("GENTEST_CACHE_DIR", blocked_file + "/subdir")
    gt_config.reset_config()

    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] cache dir:" in out

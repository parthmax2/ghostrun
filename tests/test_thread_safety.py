"""The interceptor patches process-global httpx state, so concurrent and nested
use must not corrupt it or leak the patch."""

import threading

import httpx
import pytest

from ghostrun.cache import Cache
from ghostrun.interceptor import Interceptor, UnsupportedHttpx, _check_httpx_supported

URL = "https://api.openai.com/v1/chat/completions"


def _client():
    def handler(request):
        return httpx.Response(200, json={"ok": True})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_concurrent_interceptors_restore_httpx(tmp_path):
    original = httpx.Client._transport_for_url
    errors = []

    def worker(i):
        try:
            with Interceptor(Cache(tmp_path / f"c{i}"), mode="auto"):
                for _ in range(20):
                    _client().post(URL, content=b'{"p":1}')
        except Exception as exc:  # noqa: BLE001 - surface any race to the assert
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    # The last one out must restore the original hook.
    assert httpx.Client._transport_for_url is original
    assert httpx.AsyncClient._transport_for_url is not None


def test_nested_interceptors_restore_only_at_outermost(tmp_path):
    original = httpx.Client._transport_for_url
    outer = Interceptor(Cache(tmp_path / "a"), mode="auto")
    inner = Interceptor(Cache(tmp_path / "b"), mode="auto")

    with outer:
        assert httpx.Client._transport_for_url is not original
        with inner:
            assert httpx.Client._transport_for_url is not original
        # Inner exit must NOT restore while outer is still active.
        assert httpx.Client._transport_for_url is not original
    assert httpx.Client._transport_for_url is original


def test_nested_inner_cache_takes_over_then_restores(tmp_path):
    """The innermost active interceptor decides where recordings land."""
    a, b = Cache(tmp_path / "a"), Cache(tmp_path / "b")
    with Interceptor(a, mode="auto"):
        with Interceptor(b, mode="auto"):
            _client().post(URL, content=b'{"which":"inner"}')
        _client().post(URL, content=b'{"which":"outer"}')

    assert len(list((tmp_path / "b").glob("*.json"))) == 1
    assert len(list((tmp_path / "a").glob("*.json"))) == 1


def test_double_uninstall_is_safe(tmp_path):
    original = httpx.Client._transport_for_url
    it = Interceptor(Cache(tmp_path / "c"), mode="auto")
    it.install()
    it.uninstall()
    it.uninstall()  # must not restore twice or raise
    assert httpx.Client._transport_for_url is original


def test_httpx_support_check_passes_on_current_version():
    _check_httpx_supported()  # must not raise


def test_httpx_support_check_fails_loudly(monkeypatch):
    monkeypatch.delattr(httpx.Client, "_transport_for_url", raising=True)
    with pytest.raises(UnsupportedHttpx, match="_transport_for_url"):
        _check_httpx_supported()

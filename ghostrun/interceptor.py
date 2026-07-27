"""HTTP-level record/replay interception.

Both the OpenAI and Anthropic Python SDKs send requests through ``httpx``. Rather
than monkey-patching the SDKs (brittle across releases), we swap httpx's
*transport* — the lowest common layer — for a wrapper that records or replays.

We patch ``httpx.Client._transport_for_url`` and the async equivalent so that any
client created by any SDK (or by user code) transparently routes through our
wrapping transport while ghostrun is active. The wrapper only intercepts hosts we
recognize as LLM providers; everything else passes straight through untouched.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import httpx

from .cache import Cache, CachedResponse, CacheMiss, request_key

# Hosts treated as LLM providers worth caching. Substring match against the
# request host keeps this resilient to regional subdomains.
#
# Extend at runtime for self-hosted gateways or providers not listed here:
#     ghostrun.interceptor.PROVIDER_HOSTS += ("llm.internal.corp",)
PROVIDER_HOSTS = (
    "api.openai.com",
    "api.anthropic.com",
    "openai.azure.com",
    "generativelanguage.googleapis.com",  # Gemini
    "aiplatform.googleapis.com",          # Vertex AI
    "bedrock-runtime",                    # AWS Bedrock (regional subdomains)
    "api.mistral.ai",
    "api.cohere.com",
    "api.cohere.ai",
    "openrouter.ai",
    "api.groq.com",
    "api.together.xyz",
    "api.fireworks.ai",
    "api.deepseek.com",
    "api.x.ai",                           # xAI / Grok
    "api.perplexity.ai",
)

__all__ = ["CacheMiss", "Interceptor", "UnsupportedHttpx", "PROVIDER_HOSTS"]


def _is_provider(url: httpx.URL) -> bool:
    host = url.host or ""
    return any(provider in host for provider in PROVIDER_HOSTS)


# Session-wide tallies of what actually happened at the HTTP layer, read by the
# mascot summary at the end of a pytest run. Deliberately process-global (not
# per-Interceptor) so a session mixing @record-decorated tests still gets one
# combined count instead of the mascot only seeing the last test's numbers.
_stats_lock = threading.Lock()
_stats = {"replayed": 0, "recorded": 0, "misses": 0}


def reset_stats() -> None:
    with _stats_lock:
        _stats["replayed"] = 0
        _stats["recorded"] = 0
        _stats["misses"] = 0


def get_stats() -> dict:
    with _stats_lock:
        return dict(_stats)


def _tally(kind: str) -> None:
    with _stats_lock:
        _stats[kind] += 1


class _RecordingTransport(httpx.BaseTransport):
    """Sync transport wrapper. Delegates to the real transport on record."""

    def __init__(self, inner: httpx.BaseTransport, cache: Cache, mode: str):
        self._inner = inner
        self._cache = cache
        self._mode = mode

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if not _is_provider(request.url):
            return self._inner.handle_request(request)

        body = request.read()
        key = request_key(request.method, str(request.url), body)

        if self._mode in ("auto", "replay") and self._cache.has(key):
            _tally("replayed")
            return _to_response(self._cache.get(key))

        if self._mode == "replay":
            _tally("misses")
            raise CacheMiss(
                f"No cached response for {request.method} {request.url} "
                f"(key {key}). Re-run with GHOSTRUN_MODE=record to capture it."
            )

        response = self._inner.handle_request(request)
        stored = _from_response(response)
        self._cache.put(key, request.method, str(request.url), body, stored)
        _tally("recorded")
        return _to_response(stored)


class _AsyncRecordingTransport(httpx.AsyncBaseTransport):
    """Async counterpart of :class:`_RecordingTransport`."""

    def __init__(self, inner: httpx.AsyncBaseTransport, cache: Cache, mode: str):
        self._inner = inner
        self._cache = cache
        self._mode = mode

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not _is_provider(request.url):
            return await self._inner.handle_async_request(request)

        body = await request.aread()
        key = request_key(request.method, str(request.url), body)

        if self._mode in ("auto", "replay") and self._cache.has(key):
            _tally("replayed")
            return _to_response(self._cache.get(key))

        if self._mode == "replay":
            _tally("misses")
            raise CacheMiss(
                f"No cached response for {request.method} {request.url} "
                f"(key {key}). Re-run with GHOSTRUN_MODE=record to capture it."
            )

        response = await self._inner.handle_async_request(request)
        await response.aread()
        stored = _from_response(response)
        self._cache.put(key, request.method, str(request.url), body, stored)
        _tally("recorded")
        return _to_response(stored)


def _from_response(response: httpx.Response) -> CachedResponse:
    content = response.read()
    # Drop hop-by-hop / length headers that won't match the replayed body.
    headers = {
        k: v
        for k, v in response.headers.items()
        if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
    }
    return CachedResponse(status_code=response.status_code, headers=headers, body=content)


def _to_response(cached: CachedResponse) -> httpx.Response:
    return httpx.Response(
        status_code=cached.status_code,
        headers=cached.headers,
        content=cached.body,
    )


class UnsupportedHttpx(RuntimeError):
    """httpx no longer exposes the hook ghostrun patches."""


def _check_httpx_supported() -> None:
    """Fail loudly and early if httpx drops the private hook we rely on.

    ``_transport_for_url`` is private API. It has been stable across httpx 0.18+,
    but a rename would otherwise surface as tests mysteriously hitting the
    network. Better to say so directly.
    """
    for cls in (httpx.Client, httpx.AsyncClient):
        if not hasattr(cls, "_transport_for_url"):
            raise UnsupportedHttpx(
                f"This httpx version ({httpx.__version__}) does not expose "
                f"{cls.__name__}._transport_for_url, which ghostrun uses to "
                f"intercept LLM calls. Pin httpx<0.29 or file an issue."
            )


# Patching httpx class attributes mutates process-global state, so installs are
# serialized and reference-counted across threads. Nested/concurrent
# Interceptors share one patch; the last one out restores the originals.
_patch_lock = threading.RLock()
_patch_depth = 0
_orig_sync: Optional[Callable] = None
_orig_async: Optional[Callable] = None

# Which (cache, mode) a request should use is resolved per *thread*: two threads
# each running their own Interceptor must record into their own caches, not
# whichever one happened to install last. `_local.stack` is that thread's nesting
# stack; `_global_stack` is the fallback so threads that never installed (worker
# pools, background tasks) are still intercepted by an ambient Interceptor.
_local = threading.local()
_global_stack: list = []


def _thread_stack() -> list:
    stack = getattr(_local, "stack", None)
    if stack is None:
        stack = []
        _local.stack = stack
    return stack


def _current_state() -> Optional[tuple]:
    stack = _thread_stack()
    if stack:
        return stack[-1]
    with _patch_lock:
        return _global_stack[-1] if _global_stack else None


class Interceptor:
    """Installs/removes the transport patch. Thread-safe and reentrant."""

    def __init__(self, cache: Cache, mode: str):
        self._cache = cache
        self._mode = mode
        self._installed = False
        self._state: tuple = (cache, mode)

    def __enter__(self) -> "Interceptor":
        self.install()
        return self

    def __exit__(self, *exc) -> None:
        self.uninstall()

    def install(self) -> None:
        global _patch_depth, _orig_sync, _orig_async

        _check_httpx_supported()
        # This thread's stack governs its own requests; the global stack is the
        # fallback for threads that never installed an Interceptor.
        _thread_stack().append(self._state)
        with _patch_lock:
            _global_stack.append(self._state)
            self._installed = True
            _patch_depth += 1
            if _patch_depth > 1:
                return  # already patched by someone; state stacks handle routing

            _orig_sync = httpx.Client._transport_for_url
            _orig_async = httpx.AsyncClient._transport_for_url
            orig_sync, orig_async = _orig_sync, _orig_async

            def sync_transport_for_url(self_client, url):  # type: ignore[no-untyped-def]
                inner = orig_sync(self_client, url)
                state = _current_state()
                if state is None:
                    return inner
                return _RecordingTransport(inner, state[0], state[1])

            def async_transport_for_url(self_client, url):  # type: ignore[no-untyped-def]
                inner = orig_async(self_client, url)
                state = _current_state()
                if state is None:
                    return inner
                return _AsyncRecordingTransport(inner, state[0], state[1])

            httpx.Client._transport_for_url = sync_transport_for_url
            httpx.AsyncClient._transport_for_url = async_transport_for_url

    def uninstall(self) -> None:
        global _patch_depth, _orig_sync, _orig_async

        if not self._installed:
            return
        self._installed = False

        stack = _thread_stack()
        # Remove this interceptor's own frame, not merely the top one, so an
        # out-of-order close can't unbind someone else's state.
        for i in range(len(stack) - 1, -1, -1):
            if stack[i] is self._state:
                del stack[i]
                break

        with _patch_lock:
            for i in range(len(_global_stack) - 1, -1, -1):
                if _global_stack[i] is self._state:
                    del _global_stack[i]
                    break

            _patch_depth -= 1
            if _patch_depth > 0:
                return

            if _orig_sync is not None:
                httpx.Client._transport_for_url = _orig_sync
            if _orig_async is not None:
                httpx.AsyncClient._transport_for_url = _orig_async
            _orig_sync = None
            _orig_async = None

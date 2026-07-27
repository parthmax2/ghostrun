"""The ``@ghostrun.record`` decorator and ``recording()`` context manager."""

from __future__ import annotations

import functools
import inspect
from pathlib import Path
from typing import Callable, Optional

from .cache import Cache
from .config import get_config
from .interceptor import Interceptor


def _make_interceptor(mode: Optional[str], cache_dir: Optional[str]) -> Interceptor:
    cfg = get_config()
    effective_mode = mode or cfg.mode
    effective_dir = cache_dir or cfg.cache_dir
    return Interceptor(Cache(Path(effective_dir)), effective_mode)


class recording:
    """Context manager that intercepts LLM HTTP traffic for record/replay.

    ``with ghostrun.recording(): ...`` is equivalent to wrapping the block in the
    ``@record`` decorator. The optional ``model`` argument is accepted for
    symmetry/documentation but does not change interception behavior.
    """

    def __init__(self, *, model: Optional[str] = None, mode: Optional[str] = None,
                 cache_dir: Optional[str] = None):
        self.model = model
        self._interceptor = _make_interceptor(mode, cache_dir)

    def __enter__(self):
        self._interceptor.install()
        return self

    def __exit__(self, *exc):
        self._interceptor.uninstall()
        return False


def record(func: Optional[Callable] = None, *, model: Optional[str] = None,
           mode: Optional[str] = None, cache_dir: Optional[str] = None):
    """Decorate a test so its LLM calls are recorded/replayed.

    Usable bare (``@record``) or parameterized (``@record(model="gpt-4o-mini")``).
    Works on both sync and async test functions.
    """

    def decorate(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                with recording(model=model, mode=mode, cache_dir=cache_dir):
                    return await fn(*args, **kwargs)
            return async_wrapper

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with recording(model=model, mode=mode, cache_dir=cache_dir):
                return fn(*args, **kwargs)
        return wrapper

    # Support both @record and @record(...)
    if func is not None and callable(func):
        return decorate(func)
    return decorate

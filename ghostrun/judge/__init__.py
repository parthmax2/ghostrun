"""LLM-as-a-judge backends for semantic assertions."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..cache import KVCache
from ..config import Config, get_config
from .base import Grade, Judge
from .caching import CachingJudge
from .echo import EchoJudge
from .ollama import JudgeUnavailable, OllamaJudge

# Sub-directory of the main cache dir where judge verdicts are stored.
VERDICT_SUBDIR = "judge"


def _build_backend(cfg: Config) -> Judge:
    if cfg.judge == "echo":
        return EchoJudge()
    if cfg.judge == "ollama":
        return OllamaJudge(
            model=cfg.judge_model,
            base_url=cfg.judge_base_url,
            timeout=cfg.judge_timeout,
        )
    raise ValueError(f"unknown judge backend {cfg.judge!r} (expected 'ollama' or 'echo')")


def get_judge(cfg: Optional[Config] = None) -> Judge:
    """Return the configured judge, wrapped in verdict caching when enabled.

    The echo judge is deterministic and instant, so it is never wrapped —
    caching it would only litter the cache directory.
    """
    cfg = cfg or get_config()
    backend = _build_backend(cfg)

    if not cfg.judge_cache or cfg.judge == "echo":
        return backend

    return CachingJudge(
        inner=backend,
        cache=KVCache(Path(cfg.cache_dir) / VERDICT_SUBDIR),
        mode=cfg.mode,
        backend=cfg.judge,
        model=cfg.judge_model,
        votes=cfg.judge_votes,
    )


__all__ = [
    "Grade",
    "Judge",
    "EchoJudge",
    "OllamaJudge",
    "CachingJudge",
    "JudgeUnavailable",
    "get_judge",
]

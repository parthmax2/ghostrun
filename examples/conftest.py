"""Test setup for the examples package.

Two jobs:
1. Put this directory on sys.path so `import support_app` works without the
   caller having to set PYTHONPATH.
2. Skip the semantic example gracefully when a real judge isn't available —
   under the offline `echo` stub, or when Ollama is down or the model isn't
   pulled. This keeps a full-repo `pytest` run green instead of failing on
   an environment ghostrun can't control.
"""

from __future__ import annotations

import os
import sys

import pytest

import ghostrun
from ghostrun.judge.ollama import OllamaJudge

sys.path.insert(0, os.path.dirname(__file__))


def _ollama_ready(cfg) -> bool:
    ok, _reason = OllamaJudge(cfg.judge_model, cfg.judge_base_url).is_available()
    return ok


def _skip_reason(cfg) -> str | None:
    """Why the example can't be graded here, or None if it can run."""
    if cfg.mode == "replay" and cfg.judge_cache:
        # Verdicts are served from cache and no model is invoked, so the judge
        # backend doesn't need to be reachable at all. Don't probe it.
        return None
    if cfg.judge == "echo":
        return ("example uses semantic assertions; the echo judge does literal "
                "matching only. Run with a real judge: `ollama pull llama3.2:3b`.")
    if cfg.judge == "ollama" and not _ollama_ready(cfg):
        return (f"Ollama judge unavailable or model {cfg.judge_model!r} not pulled "
                f"(base_url={cfg.judge_base_url}).")
    return None


@pytest.fixture(autouse=True)
def _require_semantic_judge():
    """Skip (don't fail) when the example's semantic assertions can't be graded."""
    reason = _skip_reason(ghostrun.get_config())
    if reason:
        pytest.skip(reason)
    yield

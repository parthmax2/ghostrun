"""Configuration loading for GenTest.

Resolution order (lowest to highest precedence):
  1. Built-in defaults
  2. ``.gentest.yaml`` found by walking up from the current working directory
  3. Environment variables (``GENTEST_*``)

Nothing here talks to the network; a missing config file is fine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

import yaml

CONFIG_FILENAME = ".gentest.yaml"
CACHE_DIRNAME = ".gentest_cache"

# Recording modes for the interceptor.
#   "auto"   -> replay from cache if present, otherwise record (default)
#   "record" -> always hit the network and overwrite the cache
#   "replay" -> never hit the network; a cache miss is an error
VALID_MODES = ("auto", "record", "replay")


@dataclass(frozen=True)
class Config:
    mode: str = "auto"
    cache_dir: str = CACHE_DIRNAME
    judge: str = "ollama"  # "ollama" | "echo"
    judge_model: str = "llama3.2:3b"
    judge_base_url: str = "http://localhost:11434"
    judge_timeout: float = 60.0
    # Record/replay judge verdicts so semantic assertions are deterministic and
    # don't re-invoke the model on every run.
    judge_cache: bool = True
    # Grade this many times on a cache miss and cache the majority verdict.
    # 1 (default) matches prior behavior: one draw, cached as-is. Published
    # LLM-as-judge studies report ~13-14% flip rates for repeated grading of
    # identical input even at temperature 0, so a single cached draw can freeze
    # in a wrong verdict; an odd votes>1 trades judge cost for a majority-vote
    # verdict plus a stored disagreement rate.
    judge_votes: int = 1

    def with_overrides(self, **kwargs) -> "Config":
        clean = {k: v for k, v in kwargs.items() if v is not None}
        return replace(self, **clean)


def find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from ``start`` (cwd by default) looking for ``.gentest.yaml``."""
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _from_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping, got {type(data).__name__}")
    # Support a nested `judge:` mapping as well as flat keys.
    judge = data.pop("judge", None)
    out: dict = {}
    for key in ("mode", "cache_dir"):
        if key in data:
            out[key] = data[key]
    if isinstance(judge, dict):
        if "type" in judge:
            out["judge"] = judge["type"]
        if "model" in judge:
            out["judge_model"] = judge["model"]
        if "base_url" in judge:
            out["judge_base_url"] = judge["base_url"]
        if "timeout" in judge:
            out["judge_timeout"] = float(judge["timeout"])
        if "cache" in judge:
            out["judge_cache"] = bool(judge["cache"])
        if "votes" in judge:
            out["judge_votes"] = int(judge["votes"])
    elif isinstance(judge, str):
        out["judge"] = judge
    return out


def _from_env() -> dict:
    env = os.environ
    out: dict = {}
    if "GENTEST_MODE" in env:
        out["mode"] = env["GENTEST_MODE"]
    if "GENTEST_CACHE_DIR" in env:
        out["cache_dir"] = env["GENTEST_CACHE_DIR"]
    if "GENTEST_JUDGE" in env:
        out["judge"] = env["GENTEST_JUDGE"]
    if "GENTEST_JUDGE_MODEL" in env:
        out["judge_model"] = env["GENTEST_JUDGE_MODEL"]
    if "GENTEST_JUDGE_BASE_URL" in env:
        out["judge_base_url"] = env["GENTEST_JUDGE_BASE_URL"]
    if "GENTEST_JUDGE_TIMEOUT" in env:
        out["judge_timeout"] = float(env["GENTEST_JUDGE_TIMEOUT"])
    if "GENTEST_JUDGE_CACHE" in env:
        out["judge_cache"] = env["GENTEST_JUDGE_CACHE"].strip().lower() not in ("0", "false", "no")
    if "GENTEST_JUDGE_VOTES" in env:
        out["judge_votes"] = int(env["GENTEST_JUDGE_VOTES"])
    return out


def load_config(start: Optional[Path] = None) -> Config:
    cfg = Config()
    path = find_config_file(start)
    if path is not None:
        cfg = cfg.with_overrides(**_from_file(path))
    cfg = cfg.with_overrides(**_from_env())
    if cfg.mode not in VALID_MODES:
        raise ValueError(f"invalid mode {cfg.mode!r}; expected one of {VALID_MODES}")
    if cfg.judge_votes < 1:
        raise ValueError(f"judge.votes must be >= 1, got {cfg.judge_votes}")
    return cfg


# A process-wide cached config. Tests and `configure()` can reset it.
_active: Optional[Config] = None


def get_config() -> Config:
    global _active
    if _active is None:
        _active = load_config()
    return _active


def set_config(cfg: Config) -> None:
    global _active
    _active = cfg


def reset_config() -> None:
    global _active
    _active = None

"""``ghostrun craft`` -- build a prompt instead of hand-writing one.

Where the rest of ghostrun tests a prompt that already exists, craft builds
one: declare a signature (``"question -> answer"``) instead of prompt text,
and an ``Optimizer`` (see ``optimizers.py``) fills in worked examples -- and,
with ``budget`` set, searches instruction phrasings too -- by running a
``Module`` for real, keeping only what passes grading.

Grading is either of two things, mutually exclusive (see ``criterion``/
``metric`` below):

- **Judge-graded** (``criterion``, the default) -- the same
  ``judge.get_judge()`` backend/model/verdict-cache that
  ``ghostrun.expect(...)`` grades against at test time. Crafting a prompt
  against criterion X here and then regression testing it against criterion
  X in a normal ghostrun test means both stages answer to one judge instead
  of two hand-maintained criteria drifting apart.
- **Gold-graded** (``metric``) -- for a task where ``examples_path`` rows
  already carry the correct answer (classification, extraction, anything
  with ground truth), a metric comparing the prediction to that gold value
  directly is faster, free, and more accurate than asking a second LLM to
  guess whether the first one is right.

The LLM calls a search makes are deliberately *not* routed through ghostrun's
record/replay interceptor (``interceptor.py``): a search needs a different
completion each round to have anything to search over, so caching identical
requests would defeat the point. Recording/replaying the *finished* prompt is
what a normal ``@ghostrun.record`` test does once crafting is done.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import get_config
from ..judge import Judge, get_judge
from .errors import CraftError
from .modules import Predict
from .optimizers import BayesianSearch, BootstrapFewShot, Optimizer, judge_grader, metric_grader
from .providers import LLMClient
from .signatures import Signature

PROMPTS_SUBDIR = "prompts"

Metric = Callable[[Dict[str, Any], Dict[str, Any]], bool]


@dataclass
class CraftedPrompt:
    name: str
    spec: str
    instructions: str
    criterion: Optional[str]
    model: str
    examples: List[Dict[str, Any]] = field(default_factory=list)
    crafted_at: str = ""
    # Set only when `craft(..., budget=...)` ran candidate comparison:
    # holdout_score is the winning candidate's pass rate on rows held out of
    # the demo pool (None if budget wasn't used, or too few examples existed
    # to hold any out). candidates_tried is always >= 1.
    holdout_score: Optional[float] = None
    candidates_tried: int = 1
    budget: Optional[int] = None
    # How many instruction phrasings BayesianSearch actually had to choose
    # from (1 if budget wasn't used, or if the instruction-proposal meta-call
    # failed both attempts and fell back to just the original).
    instruction_candidates: int = 1
    # What the search actually spent, tracked by LLMClient -- None if a
    # custom client without usage-tracking was passed in.
    tokens_used: Optional[int] = None
    estimated_cost_usd: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "spec": self.spec,
            "instructions": self.instructions,
            "criterion": self.criterion,
            "model": self.model,
            "examples": self.examples,
            "crafted_at": self.crafted_at,
            "holdout_score": self.holdout_score,
            "candidates_tried": self.candidates_tried,
            "budget": self.budget,
            "instruction_candidates": self.instruction_candidates,
            "tokens_used": self.tokens_used,
            "estimated_cost_usd": self.estimated_cost_usd,
        }

    @classmethod
    def load(cls, path: Path) -> "CraftedPrompt":
        with Path(path).open("r", encoding="utf-8") as fh:
            return cls(**json.load(fh))


def prompts_dir(cache_dir: Optional[str] = None) -> Path:
    return Path(cache_dir or get_config().cache_dir) / PROMPTS_SUBDIR


def _load_examples(path: Path) -> List[Dict[str, Any]]:
    examples: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CraftError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise CraftError(f"{path}:{lineno}: expected a JSON object, got {type(row).__name__}")
            examples.append(row)
    if not examples:
        raise CraftError(f"{path}: no examples found (one JSON object per line expected)")
    return examples


def craft(
    name: str,
    spec: str,
    examples_path: str,
    criterion: Optional[str] = None,
    *,
    metric: Optional[Metric] = None,
    model: str,
    judge: Optional[Judge] = None,
    client: Optional[LLMClient] = None,
    module: Optional[Predict] = None,
    optimizer: Optional[Optimizer] = None,
    max_examples: int = 4,
    max_attempts: int = 1,
    budget: Optional[int] = None,
    holdout_ratio: float = 0.3,
    holdout_sample_size: Optional[int] = None,
    min_interval: float = 0.0,
    resume: bool = False,
    cache_dir: Optional[str] = None,
) -> CraftedPrompt:
    """Search ``examples_path`` for a prompt (instructions + worked examples)
    that passes grading. Saves the result to
    ``<cache_dir>/prompts/<name>.json`` and returns it.

    Grading: pass exactly one of ``criterion`` (judge-graded, free-form) or
    ``metric`` (``(prediction, row) -> bool``, gold-graded -- use when
    ``examples_path`` rows already carry the correct answer).

    Which ``Optimizer`` runs depends on ``budget``:

    - ``budget=None`` (default) -- ``BootstrapFewShot``: one greedy pass,
      accepting the first reply per row that passes, retrying up to
      ``max_attempts`` times. Only the demos vary; instructions are untouched.
    - ``budget=N`` -- ``BayesianSearch``: proposes alternative instruction
      phrasings, then runs TPE-sampled trials over instruction choice and
      demo-bootstrapping temperature, scored against a held-out slice of
      ``examples_path``, keeping the best-scoring trial. ``holdout_sample_size``
      caps how many held-out rows each trial scores against, trading a
      noisier per-trial signal for more trials at the same budget -- see
      ``BayesianSearch``'s docstring. ``resume=True`` persists trials to
      ``<cache_dir>/prompts/<name>.study.sqlite3`` (via optuna's own storage)
      so a `craft()` run interrupted partway through can be re-run with the
      same arguments and continue instead of starting the search over.

    Pass ``optimizer=`` directly to use a different one, or a
    differently-configured instance of either. ``module`` defaults to
    ``Predict(Signature.parse(spec))``; pass a ``ChainOfThought`` (or any
    other ``Module``) to craft a different kind of prompt. ``min_interval``
    (seconds) paces the default client's calls -- only applies when
    ``client`` isn't passed in yourself.
    """
    if (criterion is None) == (metric is None):
        raise CraftError("pass exactly one of criterion= or metric=")

    parsed_signature = Signature.parse(spec)
    rows = _load_examples(Path(examples_path))
    resolved_client = client or LLMClient(model, min_interval=min_interval)
    resolved_module = module or Predict(parsed_signature)
    grade = metric_grader(metric) if metric is not None else judge_grader(judge or get_judge(), criterion)

    out_dir = prompts_dir(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)  # BayesianSearch's sqlite storage needs this to exist first

    resolved_optimizer = optimizer or (
        BootstrapFewShot(max_examples=max_examples, max_attempts=max_attempts)
        if budget is None
        else BayesianSearch(
            budget=budget, max_examples=max_examples, max_attempts=max_attempts,
            holdout_ratio=holdout_ratio, holdout_sample_size=holdout_sample_size,
            storage_path=str(out_dir / f"{name}.study.sqlite3") if resume else None,
            study_name=name if resume else None,
        )
    )

    compiled = resolved_optimizer.compile(resolved_module, rows, grade, resolved_client)

    result = CraftedPrompt(
        name=name,
        spec=spec,
        instructions=compiled.instructions,
        criterion=criterion,
        model=model,
        examples=compiled.examples,
        crafted_at=datetime.now(timezone.utc).isoformat(),
        holdout_score=compiled.holdout_score,
        candidates_tried=compiled.candidates_tried,
        budget=budget,
        instruction_candidates=compiled.instruction_candidates,
        tokens_used=getattr(resolved_client, "total_tokens", None),
        estimated_cost_usd=getattr(resolved_client, "total_cost", None),
    )

    out_path = out_dir / f"{name}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(result.to_json(), fh, indent=2, ensure_ascii=False)

    return result


__all__ = ["CraftedPrompt", "craft", "prompts_dir", "Metric"]

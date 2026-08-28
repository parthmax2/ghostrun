"""Optimizers: strategies for turning worked examples into a finished prompt
(instructions + demos) for a ``Module``.

``BootstrapFewShot`` is a single greedy pass -- ``craft()``'s original
algorithm, formalized as a class: accept the first reply per row the judge
(or a gold-based metric) passes, in order, up to a cap.

``BayesianSearch`` is real search, not just retries: it proposes several
phrasings of the instructions (via one meta LLM call), then runs
TPE-sampled trials (via `optuna <https://optuna.org>`_) over *both* which
instruction phrasing to use *and* how much to vary the demo-bootstrapping
temperature, scoring each trial's finished prompt against a held-out slice
of the examples and keeping the best-scoring trial. This is the same shape
of thing DSPy's ``MIPROv2`` does (search over instructions and demos, scored
against held-out data) -- reimplemented natively against ghostrun's own
``Signature``/``Module``/judge, using optuna as the search library rather
than ghostrun hand-rolling a Bayesian optimizer.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import optuna
from optuna.samplers import TPESampler

from ..judge import Judge
from .errors import CraftError, ParseError
from .modules import Predict
from .providers import LLMClient

# A grader scores one prediction against the row it came from (which carries
# whatever the row originally had -- gold labels included, if any) and
# returns pass/fail. `judge_grader` and `metric_grader` build one from
# ghostrun's judge or a user-supplied gold-comparison function, respectively;
# `_bootstrap`/`_score_holdout` only ever see this uniform shape.
GradeFn = Callable[[Dict[str, Any], Dict[str, Any]], bool]


def judge_grader(judge: Judge, criterion: str) -> GradeFn:
    """The original grading path: an LLM judge decides pass/fail against a
    free-form criterion, without needing (or seeing) gold labels."""

    def grade(prediction: Dict[str, Any], row: Dict[str, Any]) -> bool:
        text = "\n".join(f"{k}: {v}" for k, v in prediction.items())
        return judge.grade(text, criterion).passed

    return grade


def metric_grader(metric: Callable[[Dict[str, Any], Dict[str, Any]], bool]) -> GradeFn:
    """Wraps a user metric ``(prediction, row) -> bool`` -- e.g. exact-match
    against gold labels already present in the row, the way DSPy's metrics
    normally work for classification/extraction tasks. No judge call, no
    judge latency/cost, and (for a task with real ground truth) more
    accurate than asking a second LLM to guess whether the first one is
    right."""
    return metric


@dataclass
class CompileResult:
    instructions: str
    examples: List[Dict[str, Any]]
    holdout_score: Optional[float] = None
    candidates_tried: int = 1
    instruction_candidates: int = 1


def _row_inputs(module: Predict, row: Dict[str, Any]) -> Dict[str, Any]:
    signature = module.signature
    inputs = {f.name: row[f.name] for f in signature.inputs if f.name in row}
    if len(inputs) != len(signature.inputs):
        missing = [f.name for f in signature.inputs if f.name not in row]
        raise CraftError(f"example {row!r} is missing input field(s) {missing}")
    return inputs


def _bootstrap(
    module: Predict, rows: List[Dict[str, Any]], grade: GradeFn,
    client: LLMClient, max_examples: int, max_attempts: int, temperature_floor: float = 0.0,
) -> List[Dict[str, Any]]:
    """One greedy pass: accept the first reply per row that ``grade`` passes,
    retrying up to ``max_attempts`` times at a higher temperature."""
    accepted: List[Dict[str, Any]] = []
    for row in rows:
        if len(accepted) >= max_examples:
            break
        inputs = _row_inputs(module, row)
        module.demos = accepted
        for attempt in range(max_attempts):
            temperature = min(1.0, temperature_floor if attempt == 0 else 1.0)
            try:
                prediction = module.forward(client, temperature=temperature, **inputs)
            except ParseError:
                continue
            if grade(dict(prediction), row):
                accepted.append({**inputs, **prediction})
                break
    return accepted


def _score_holdout(
    module: Predict, examples: List[Dict[str, Any]], holdout: List[Dict[str, Any]],
    grade: GradeFn, client: LLMClient,
) -> float:
    """Run the finished prompt (fixed instructions + examples, temperature 0)
    against rows the search never saw, and return the pass rate."""
    if not holdout:
        return float(len(examples))
    module.demos = examples
    passed = 0
    for row in holdout:
        inputs = _row_inputs(module, row)
        try:
            prediction = module.forward(client, temperature=0.0, **inputs)
        except ParseError:
            continue
        if grade(dict(prediction), row):
            passed += 1
    return passed / len(holdout)


def split_holdout(rows: List[Dict[str, Any]], ratio: float) -> Tuple[list, list]:
    """Reserve a tail slice of ``rows`` for held-out scoring, leaving at least
    2 rows in the demo pool. Too few rows to split meaningfully (< 4) skips
    holdout entirely."""
    if len(rows) < 4:
        return rows, []
    n_holdout = min(max(1, round(len(rows) * ratio)), len(rows) - 2)
    return rows[:-n_holdout], rows[-n_holdout:]


class Optimizer(ABC):
    @abstractmethod
    def compile(
        self, module: Predict, rows: List[Dict[str, Any]], grade: GradeFn, client: LLMClient,
    ) -> CompileResult: ...


class BootstrapFewShot(Optimizer):
    """A single greedy pass over every row -- ``craft()``'s original,
    unchanged algorithm. No held-out evaluation: whatever ``grade`` accepts
    during the one pass is what gets saved."""

    def __init__(self, max_examples: int = 4, max_attempts: int = 1):
        self.max_examples = max_examples
        self.max_attempts = max_attempts

    def compile(self, module, rows, grade, client) -> CompileResult:
        examples = _bootstrap(module, rows, grade, client, self.max_examples, self.max_attempts)
        return CompileResult(instructions=module.signature.instructions, examples=examples)


_INSTRUCTION_PROMPT = (
    "You are helping refine the system instructions for an LLM prompt.\n\n"
    "Current instructions:\n{instructions}\n\n"
    "The prompt's job: given {input_names}, produce {output_names}.\n"
    "{grading_note}\n\n"
    "Propose {n} alternative phrasings of the instructions that might do "
    "better against that grading. Reply with a JSON array of "
    "{n} strings, nothing else."
)


class BayesianSearch(Optimizer):
    """Search over instruction phrasing *and* demo selection, scored against
    a held-out slice, via optuna's TPE sampler.

    ``budget`` is the total number of model calls to spend: one meta-call to
    propose ``n_instructions`` instruction candidates, then as many trials as
    the remaining budget affords. Each trial costs up to ``max_examples *
    max_attempts`` bootstrap calls plus however many holdout rows it scores
    -- ``holdout_sample_size`` caps that per-trial (instead of scoring the
    *entire* holdout on every single trial), which is what makes a modest
    budget buy several trials instead of one: at the default (``None``, all
    of holdout every trial), a large holdout dominates the per-trial cost
    and a realistic budget affords only one or two trials -- barely a
    search at all. Capping it trades a noisier per-trial score for enough
    trials to actually explore the space; every accepted trial's *saved*
    demos are still real, ungraded-by-sampling accepted examples -- only the
    ranking signal is sampled.
    """

    def __init__(self, budget: int, max_examples: int = 4, max_attempts: int = 1,
                holdout_ratio: float = 0.3, holdout_sample_size: Optional[int] = None,
                n_instructions: int = 3, seed: int = 0,
                storage_path: Optional[str] = None, study_name: Optional[str] = None):
        if budget < 1:
            raise CraftError(f"budget must be >= 1, got {budget}")
        self.budget = budget
        self.max_examples = max_examples
        self.max_attempts = max_attempts
        self.holdout_ratio = holdout_ratio
        self.holdout_sample_size = holdout_sample_size
        self.n_instructions = max(1, n_instructions)
        self.seed = seed
        # Persisting trials to a sqlite study (optuna's own storage mechanism,
        # not something ghostrun reimplements) means a `craft()` run killed
        # partway through -- a network blip, a rate limit, Ctrl+C -- can be
        # re-run with the same storage_path/study_name and pick up from the
        # trials already recorded instead of starting the search over.
        self.storage_path = storage_path
        self.study_name = study_name

    def _propose_instructions(self, module: Predict, grading_note: str,
                              client: LLMClient) -> Tuple[List[str], bool]:
        """One meta-call (retried once on a malformed reply) asking the model
        for alternative instruction phrasings. Falls back to just the
        original instructions if both attempts fail -- a failed proposal
        step should narrow the search, not crash it. Returns
        ``(pool, used_fallback)`` so the caller can tell the two apart."""
        signature = module.signature
        prompt = _INSTRUCTION_PROMPT.format(
            instructions=signature.instructions,
            input_names=", ".join(f.name for f in signature.inputs),
            output_names=", ".join(f.name for f in signature.outputs),
            grading_note=grading_note,
            n=self.n_instructions,
        )
        candidates: List[str] = []
        for _ in range(2):  # one retry: a malformed JSON reply is usually a fluke
            try:
                raw = client.complete("You propose prompt instructions as JSON.",
                                      [{"role": "user", "content": prompt}], temperature=0.7)
                parsed = json.loads(raw)
                if not isinstance(parsed, list) or not all(isinstance(c, str) for c in parsed):
                    raise ValueError("expected a JSON array of strings")
                candidates = parsed
                break
            except Exception:
                continue
        pool = [signature.instructions] + [c for c in candidates if c.strip()]
        seen = set()
        deduped = []
        for c in pool:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        return deduped, len(deduped) == 1

    def compile(self, module, rows, grade, client) -> CompileResult:
        demo_pool, holdout = split_holdout(rows, self.holdout_ratio)
        scored_holdout = (
            holdout if self.holdout_sample_size is None else holdout[:self.holdout_sample_size]
        )
        grading_note = "Predictions are graded against a held-out set of examples."
        instruction_pool, _fell_back = self._propose_instructions(module, grading_note, client)

        cost_per_trial = max(1, self.max_examples * self.max_attempts + len(scored_holdout))
        meta_cost = 1  # the instruction-proposal call
        n_trials = max(1, (self.budget - meta_cost) // cost_per_trial)

        original_instructions = module.signature.instructions

        def objective(trial: optuna.Trial) -> float:
            instr_idx = trial.suggest_categorical("instruction_idx", list(range(len(instruction_pool))))
            temperature_floor = trial.suggest_float("temperature_floor", 0.0, 1.0)
            module.signature.instructions = instruction_pool[instr_idx]
            examples = _bootstrap(module, demo_pool, grade, client,
                                  self.max_examples, self.max_attempts,
                                  temperature_floor=temperature_floor)
            score = _score_holdout(module, examples, scored_holdout, grade, client)
            trial.set_user_attr("examples", examples)
            trial.set_user_attr("instructions", instruction_pool[instr_idx])
            return score

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        storage = f"sqlite:///{self.storage_path}" if self.storage_path else None
        study = optuna.create_study(
            direction="maximize", sampler=TPESampler(seed=self.seed),
            storage=storage, study_name=self.study_name, load_if_exists=bool(storage),
        )
        already_run = len(study.trials)
        remaining = max(0, n_trials - already_run)
        if remaining:
            study.optimize(objective, n_trials=remaining)

        module.signature.instructions = original_instructions  # restore; caller reads the result, not this mutation
        best = study.best_trial
        return CompileResult(
            instructions=best.user_attrs["instructions"],
            examples=best.user_attrs["examples"],
            holdout_score=best.value if scored_holdout else None,
            candidates_tried=len(study.trials),
            instruction_candidates=len(instruction_pool),
        )


__all__ = [
    "Optimizer", "BootstrapFewShot", "BayesianSearch", "CompileResult", "split_holdout",
    "GradeFn", "judge_grader", "metric_grader",
]

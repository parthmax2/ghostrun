"""Modules: a signature becomes a runnable unit by pairing it with an
adapter and calling it against an ``LLMClient``. ``Predict`` is the base
case (one call in, one call out); ``ChainOfThought`` is a ``Predict`` whose
signature has a ``reasoning`` field prepended to the outputs, so the model
thinks before answering.

This is the layer ``optimize.py``'s bootstrapping search runs against --
searching now means "try different values for ``module.demos``", not
"hand-build chat messages inline". It's also the seam later phases (an
optimizer hierarchy, multi-step composed programs, retrieval/agent modules)
build on: anything that exposes ``.forward(client, **inputs) -> Prediction``
plugs into the same search loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .adapters import Adapter, DelimiterAdapter
from .errors import ParseError
from .providers import LLMClient
from .signatures import Signature


class Prediction(dict):
    """The typed output of a module call. Dict-like (so
    ``"\\n".join(f"{k}: {v}" for k, v in prediction.items())`` keeps working
    for judge grading) with attribute access for convenience."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class Module(ABC):
    """Base class for a runnable signature. ``demos`` is mutable state an
    optimizer sets between calls -- see ``optimize.py``."""

    def __init__(self, signature: Signature, adapter: Optional[Adapter] = None):
        self.signature = signature
        self.adapter = adapter or DelimiterAdapter()
        self.demos: List[Dict[str, Any]] = []

    @abstractmethod
    def forward(self, client: LLMClient, *, temperature: float = 0.0, **inputs: Any) -> Prediction: ...

    def __call__(self, client: LLMClient, *, temperature: float = 0.0, **inputs: Any) -> Prediction:
        return self.forward(client, temperature=temperature, **inputs)


class Predict(Module):
    """One call: signature + demos + inputs -> parsed, typed outputs.

    ``max_repair_attempts`` (default 0, matching prior behavior exactly):
    when a reply fails to parse/validate, instead of raising immediately,
    re-ask the model up to that many times with the parse error appended to
    the conversation ("that reply didn't match the required format: ...").
    Most malformed replies are one nudge away from valid -- this trades one
    extra call for not hard-failing a whole search/request on a single bad
    token from the model.
    """

    def __init__(self, signature: Signature, adapter: Optional[Adapter] = None,
                max_repair_attempts: int = 0):
        super().__init__(signature, adapter)
        self.max_repair_attempts = max_repair_attempts

    def forward(self, client: LLMClient, *, temperature: float = 0.0, **inputs: Any) -> Prediction:
        system = self.adapter.system_message(self.signature)
        messages = self.adapter.build_messages(self.signature, self.demos, inputs)

        attempt = 0
        while True:
            raw = client.complete(system, messages, temperature=temperature)
            try:
                outputs = self.adapter.parse(self.signature, raw)
                return Prediction(outputs)
            except ParseError as exc:
                attempt += 1
                if attempt > self.max_repair_attempts:
                    raise
                messages = [
                    *messages,
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": (
                        f"That reply didn't match the required format: {exc}. "
                        f"Please reply again, following the exact field format."
                    )},
                ]


class ChainOfThought(Predict):
    """A ``Predict`` whose signature gets a ``reasoning`` output field
    prepended, so the model reasons before producing the real outputs --
    same idea as DSPy's module of the same name, reimplemented natively
    against ghostrun's own ``Signature``/``Adapter``."""

    def __init__(self, signature: Signature, adapter: Optional[Adapter] = None,
                max_repair_attempts: int = 0):
        super().__init__(signature.with_reasoning(), adapter, max_repair_attempts)


__all__ = ["Module", "Predict", "ChainOfThought", "Prediction"]

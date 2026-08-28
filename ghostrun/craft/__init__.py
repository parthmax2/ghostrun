"""``ghostrun craft`` -- ghostrun's native prompt-building framework.

Public surface, layered the way DSPy's is (signatures -> adapters -> modules
-> a search that runs them), but native to ghostrun and wired to its own
judge rather than an external dependency:

- ``signatures``: ``Signature`` / ``SigField`` -- a prompt's typed
  input/output contract, parsed from a string like ``"question -> answer"``.
- ``adapters``: ``Adapter`` / ``DelimiterAdapter`` -- pluggable templating:
  signature + examples + inputs -> chat messages, and a reply -> typed fields.
- ``modules``: ``Module`` / ``Predict`` / ``ChainOfThought`` -- a signature
  paired with an adapter becomes something callable against an LLM client.
- ``providers``: ``LLMClient`` -- litellm-backed, many providers, retries,
  streaming; the client the search calls directly, uncached, for real
  variation.
- ``optimizers``: ``Optimizer`` / ``BootstrapFewShot`` / ``BayesianSearch`` --
  strategies for turning worked examples into a finished prompt.
  ``BootstrapFewShot`` is a single greedy pass over demos only.
  ``BayesianSearch`` proposes instruction candidates and TPE-searches (via
  optuna) over instruction choice *and* demo-bootstrapping temperature,
  scored against a held-out slice.
- ``optimize``: ``craft()`` / ``CraftedPrompt`` -- picks an ``Optimizer``
  (``BootstrapFewShot`` by default, ``BayesianSearch`` when ``budget=`` is
  set) and runs it against a ``Module``, grading results with ghostrun's own
  judge and saving the winner.

- ``programs``: ``RAG`` / ``Agent`` -- composed Modules, the first concrete
  examples of Modules calling other Modules. ``RAG`` retrieves passages (via
  a retriever callable you supply) before answering; ``Agent`` runs a
  ReAct-style tool loop, executing tools locally between model steps.
  Neither is wired into ``craft()``'s search yet -- bootstrapping per-step
  examples for a composed program is a further follow-up.
"""

from __future__ import annotations

from .adapters import Adapter, DelimiterAdapter
from .errors import CraftError, ParseError, ProviderError, SignatureError
from .modules import ChainOfThought, Module, Predict, Prediction
from .optimize import CraftedPrompt, craft, prompts_dir
from .optimizers import BayesianSearch, BootstrapFewShot, CompileResult, Optimizer
from .programs import RAG, Agent, Tool
from .providers import LLMClient
from .signatures import SigField, Signature, is_structured, register_model

__all__ = [
    "CraftError", "SignatureError", "ParseError", "ProviderError",
    "Signature", "SigField", "register_model", "is_structured",
    "Adapter", "DelimiterAdapter",
    "Module", "Predict", "ChainOfThought", "Prediction",
    "RAG", "Agent", "Tool",
    "LLMClient",
    "Optimizer", "BootstrapFewShot", "BayesianSearch", "CompileResult",
    "CraftedPrompt", "craft", "prompts_dir",
]

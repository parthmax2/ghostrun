"""Composable multi-step programs: ``Module``s that call other ``Module``s.

``RAG`` retrieves supporting passages before answering (retrieval-augmented
generation) via a user-supplied retriever callable -- ghostrun doesn't ship
its own vector store; it gives whatever retriever you already have (FAISS,
Chroma, a keyword search, an HTTP call) a ``Module``-shaped interface so it
composes with the rest of this package.

``Agent`` runs a ReAct-style tool loop: at each step the model either calls
one of the given tools (executed locally, its result fed back as an
"observation") or finishes with the signature's real outputs, up to
``max_steps``.

Neither is wired into ``craft()``'s search in this phase -- bootstrapping
few-shot examples *for each step of a composed program*, not just one flat
signature, is real additional work, tracked as a follow-up rather than
implemented here. Both are usable directly today: build one, call
``.forward(client, **inputs)``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .adapters import Adapter
from .errors import CraftError, ParseError
from .modules import ChainOfThought, Module, Predict, Prediction
from .providers import LLMClient
from .signatures import SigField, Signature, is_structured

Retriever = Callable[[str, int], List[str]]


class RAG(Module):
    """Retrieve passages for the signature's first input field, then answer
    with them folded into a ``context`` field.

    ``retriever(query, k) -> list[str]`` is any callable you already have.
    """

    def __init__(self, signature: Signature, retriever: Retriever, k: int = 3,
                adapter: Optional[Adapter] = None, reasoning: bool = False):
        if not signature.inputs:
            raise CraftError("RAG needs a signature with at least one input field")
        self.signature = signature
        self.retriever = retriever
        self.k = k
        context_signature = signature.with_context()
        module_cls = ChainOfThought if reasoning else Predict
        self.answer_module = module_cls(context_signature, adapter)
        self.demos: List[Dict[str, Any]] = []

    def forward(self, client: LLMClient, *, temperature: float = 0.0, **inputs: Any) -> Prediction:
        query_field = self.signature.inputs[0].name
        query = str(inputs[query_field])
        passages = self.retriever(query, self.k)
        context = "\n\n".join(passages)
        self.answer_module.demos = self.demos
        return self.answer_module.forward(client, temperature=temperature, context=context, **inputs)


@dataclass
class Tool:
    name: str
    func: Callable[[str], Any]
    description: str = ""


class Agent(Module):
    """ReAct-style tool loop. At each step the model produces ``thought``,
    ``action`` (a tool name or ``"finish"``), and ``action_input``; a real
    tool call runs locally and its result is appended to a scratchpad fed
    back next step, until the model finishes or ``max_steps`` is reached."""

    def __init__(self, signature: Signature, tools: Optional[List[Tool]] = None,
                adapter: Optional[Adapter] = None, max_steps: int = 5):
        self.signature = signature
        self.tools: Dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.max_steps = max_steps
        self.demos: List[Dict[str, Any]] = []

        # `action` is deliberately plain `str`, not a `Literal` of known tool
        # names: a `Literal` would make pydantic *reject* an unrecognized
        # action at parse time, before `forward()` ever gets a chance to
        # handle it as "unknown tool" gracefully (see that branch below).
        # Valid names are still communicated to the model via instructions.
        step_outputs = [
            SigField("thought", str, desc="reasoning about what to do next"),
            SigField("action", str, desc="a tool name, or 'finish' to produce the final answer"),
            SigField("action_input", str,
                     desc="the tool's argument, or (if action='finish') the final answer"),
        ]
        step_inputs = [*signature.inputs,
                      SigField("scratchpad", str, desc="prior thought/action/observation steps")]
        self._step_signature = Signature(
            raw=signature.raw, inputs=step_inputs, outputs=step_outputs,
            instructions=self._build_instructions(signature),
        )
        self._step_module = Predict(self._step_signature, adapter)

    def _build_instructions(self, signature: Signature) -> str:
        tool_lines = "\n".join(f"- {t.name}: {t.description}" for t in self.tools.values()) or "(none)"
        out_names = ", ".join(f.name for f in signature.outputs)
        finish_desc = (
            f"a JSON object with keys {out_names}" if len(signature.outputs) > 1 else "the final answer"
        )
        return (
            f"{signature.instructions}\n\n"
            f"You can use these tools:\n{tool_lines}\n\n"
            f"At each step, think, then either call one tool (action = its name, "
            f"action_input = its argument) or finish (action = 'finish', "
            f"action_input = {finish_desc})."
        )

    def forward(self, client: LLMClient, *, temperature: float = 0.0, **inputs: Any) -> Prediction:
        scratchpad = ""
        self._step_module.demos = self.demos
        for _ in range(self.max_steps):
            step = self._step_module.forward(client, temperature=temperature,
                                              scratchpad=scratchpad, **inputs)
            if step.action == "finish":
                return self._finish(step.action_input)
            tool = self.tools.get(step.action)
            if tool is None:
                observation = f"Unknown tool {step.action!r}. Available: {list(self.tools)}"
            else:
                try:
                    observation = str(tool.func(step.action_input))
                except Exception as exc:
                    observation = f"Tool error: {exc}"
            scratchpad += (
                f"\nThought: {step.thought}\nAction: {step.action}[{step.action_input}]\n"
                f"Observation: {observation}"
            )
        raise CraftError(f"agent did not finish within {self.max_steps} steps")

    def _finish(self, action_input: str) -> Prediction:
        if len(self.signature.outputs) == 1:
            raw = {self.signature.outputs[0].name: action_input}
        else:
            try:
                parsed = json.loads(action_input)
            except json.JSONDecodeError as exc:
                raise ParseError(
                    f"agent finish action_input must be a JSON object with keys "
                    f"{[f.name for f in self.signature.outputs]}: {exc}"
                ) from exc
            raw = {}
            for f in self.signature.outputs:
                if f.name not in parsed:
                    raise ParseError(f"agent finish JSON is missing field {f.name!r}")
                value = parsed[f.name]
                raw[f.name] = json.dumps(value) if is_structured(f.annotation) else str(value)
        return Prediction(self.signature.coerce_outputs(raw))


__all__ = ["RAG", "Agent", "Tool", "Retriever"]

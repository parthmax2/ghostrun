"""Typed signatures: a prompt's input/output contract, parsed from a string
like ``"question -> answer"`` and backed by a dynamically-built pydantic
model so field types are validated and coerced the same way pydantic does
everywhere else, instead of ghostrun hand-rolling type coercion a second time.

Supported field types, written after a field name as ``name: type``
(default ``str`` if omitted):

    str, int, float, bool                    -- scalar, rendered as plain text
    Literal["a", "b", "c"]                    -- scalar, constrained to a set
    list[str], list[int], dict[str, int], ... -- structured, rendered as JSON
    <a registered pydantic.BaseModel name>     -- structured, rendered as JSON

"Structured" fields (anything that isn't a bare scalar/Literal) are
represented as JSON on the wire -- see ``adapters.py`` -- because there's no
sane way to fit a nested object or a list into a single line of a text
delimiter protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union, get_origin

import pydantic

from .errors import ParseError, SignatureError

# The only names a type expression may reference. Evaluated with
# ``__builtins__`` stripped, so a spec string can express `list[str]` or
# `Literal["a","b"]` without being able to reach arbitrary Python.
_TYPE_NAMESPACE: Dict[str, Any] = {
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "List": List, "dict": dict, "Dict": Dict,
    "Literal": Literal, "Optional": Optional, "Union": Union, "Tuple": Tuple,
}

_registered_models: Dict[str, Type[pydantic.BaseModel]] = {}


def register_model(model: Type[pydantic.BaseModel]) -> Type[pydantic.BaseModel]:
    """Make a pydantic model usable by name inside a signature's type
    expressions, e.g. after ``register_model(LineItem)``, a field can be
    declared ``items: list[LineItem]``."""
    _registered_models[model.__name__] = model
    return model


def _parse_type(expr: str) -> Any:
    expr = expr.strip()
    if not expr:
        return str
    namespace = {**_TYPE_NAMESPACE, **_registered_models, "__builtins__": {}}
    try:
        return eval(expr, {"__builtins__": {}}, namespace)  # noqa: S307 -- restricted namespace
    except Exception as exc:
        raise SignatureError(f"unrecognized field type {expr!r}: {exc}") from exc


def is_structured(annotation: Any) -> bool:
    """True for anything that can't be rendered as a plain-text scalar:
    list/dict/tuple, or a pydantic model. Literal and str/int/float/bool are
    scalar even though Literal is technically a typing construct."""
    origin = get_origin(annotation)
    if origin in (list, dict, tuple):
        return True
    return isinstance(annotation, type) and issubclass(annotation, pydantic.BaseModel)


def _split_top_level(text: str, sep: str) -> List[str]:
    """Split on ``sep`` at bracket depth 0, so ``Literal["a,b"]`` or
    ``list[str]`` don't get split on the comma/colon inside them."""
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


@dataclass(frozen=True)
class SigField:
    name: str
    annotation: Any = str
    desc: str = ""

    @property
    def type_repr(self) -> str:
        return getattr(self.annotation, "__name__", None) or str(self.annotation)


class Signature:
    """A prompt's input/output contract. Build with ``Signature("inputs -> outputs")``
    or ``Signature.parse(...)``; ``.with_reasoning()`` derives a copy with a
    ``reasoning`` field prepended to the outputs (used by ``modules.ChainOfThought``)."""

    def __init__(self, raw: str, inputs: Optional[List[SigField]] = None,
                 outputs: Optional[List[SigField]] = None,
                 instructions: str = ""):
        if inputs is None or outputs is None:
            parsed = self.parse(raw, instructions=instructions)
            self.raw = parsed.raw
            self.inputs = parsed.inputs
            self.outputs = parsed.outputs
            self.instructions = parsed.instructions
            self._model = parsed._model
            return

        self.raw = raw
        self.inputs = inputs
        self.outputs = outputs
        self.instructions = instructions or self._default_instructions()
        self._model = pydantic.create_model(
            "Outputs", **{f.name: (f.annotation, ...) for f in outputs}
        )

    def _default_instructions(self) -> str:
        in_names = ", ".join(f.name for f in self.inputs)
        out_names = ", ".join(f.name for f in self.outputs)
        return f"Given {in_names}, produce {out_names}."

    @classmethod
    def parse(cls, text: str, instructions: str = "") -> "Signature":
        if "->" not in text:
            raise SignatureError(
                f"signature must contain '->', e.g. \"question -> answer\" (got {text!r})"
            )
        left, right = text.split("->", 1)
        inputs = [cls._parse_field(chunk) for chunk in _split_top_level(left, ",") if chunk.strip()]
        outputs = [cls._parse_field(chunk) for chunk in _split_top_level(right, ",") if chunk.strip()]
        if not inputs:
            raise SignatureError(f"signature needs at least one input field (got {text!r})")
        if not outputs:
            raise SignatureError(f"signature needs at least one output field (got {text!r})")
        names = [f.name for f in inputs + outputs]
        if len(names) != len(set(names)):
            raise SignatureError(f"signature has a duplicate field name (got {text!r})")
        return cls(raw=text.strip(), inputs=inputs, outputs=outputs, instructions=instructions)

    @staticmethod
    def _parse_field(chunk: str) -> SigField:
        chunk = chunk.strip()
        if ":" not in chunk:
            name, type_expr = chunk, ""
        else:
            parts = _split_top_level(chunk, ":")
            name, type_expr = parts[0].strip(), ":".join(parts[1:]).strip()
        if not name.isidentifier():
            raise SignatureError(f"field name {name!r} must be a valid identifier")
        annotation = _parse_type(type_expr)
        return SigField(name=name, annotation=annotation)

    def with_reasoning(self, field_name: str = "reasoning") -> "Signature":
        if any(f.name == field_name for f in self.outputs):
            return self
        reasoning = SigField(name=field_name, annotation=str,
                             desc="step-by-step reasoning before the final answer")
        return Signature(
            raw=self.raw, inputs=self.inputs, outputs=[reasoning, *self.outputs],
            instructions=self.instructions,
        )

    def with_context(self, field_name: str = "context") -> "Signature":
        """A copy with a ``context: str`` input field appended (used by
        ``programs.RAG`` to fold retrieved passages in)."""
        if any(f.name == field_name for f in self.inputs):
            return self
        context_field = SigField(name=field_name, annotation=str,
                                 desc="retrieved supporting passages")
        return Signature(
            raw=self.raw, inputs=[*self.inputs, context_field],
            outputs=self.outputs, instructions=self.instructions,
        )

    def coerce_outputs(self, raw: Dict[str, str]) -> Dict[str, Any]:
        """Turn the adapter's raw per-field text into typed values, validated
        by the signature's pydantic model. Structured fields (list/dict/model)
        are expected to already be JSON text; scalars are parsed directly."""
        import json

        prepared: Dict[str, Any] = {}
        for f in self.outputs:
            text = raw[f.name]
            if is_structured(f.annotation):
                try:
                    prepared[f.name] = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ParseError(
                        f"field {f.name!r} expects JSON for type {f.type_repr}, "
                        f"got {text[:120]!r}: {exc}"
                    ) from exc
            elif f.annotation is bool:
                prepared[f.name] = text.strip().lower() in ("true", "yes", "1")
            else:
                prepared[f.name] = text
        try:
            validated = self._model(**prepared)
        except pydantic.ValidationError as exc:
            raise ParseError(f"output failed validation: {exc}") from exc
        return validated.model_dump()


__all__ = ["Signature", "SigField", "register_model", "is_structured"]

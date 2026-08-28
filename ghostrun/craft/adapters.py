"""Adapters: turn a ``Signature`` + examples + inputs into chat messages, and
a raw model reply back into typed field values. Pluggable so the wire format
isn't locked to one template -- ``modules.py`` takes an adapter instance
rather than hard-coding a format, the way it used to when this was all one
function in ``craft.py``.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .errors import ParseError
from .signatures import Signature, SigField, is_structured


class Adapter(ABC):
    """Formats a signature into a system message + chat turns, and parses a
    reply back into the signature's typed output fields."""

    @abstractmethod
    def system_message(self, signature: Signature) -> str: ...

    @abstractmethod
    def build_messages(self, signature: Signature, examples: List[Dict[str, Any]],
                       inputs: Dict[str, Any]) -> List[dict]: ...

    @abstractmethod
    def parse(self, signature: Signature, raw: str) -> Dict[str, Any]: ...


def _render_value(f: SigField, value: Any) -> str:
    if is_structured(f.annotation):
        return json.dumps(value)
    return str(value)


class DelimiterAdapter(Adapter):
    """Default adapter: each field starts its own line reading
    ``>>> field_name`` followed by the value. Structured fields (list/dict/
    nested model) are rendered and parsed as JSON on that line; everything
    else is plain text."""

    FIELD_MARK = ">>>"

    def __init__(self):
        self._field_re = re.compile(rf"^{re.escape(self.FIELD_MARK)} (\w+)\s*$", re.MULTILINE)

    def _field_list(self, fields: List[SigField]) -> str:
        return "\n".join(f"- {f.name} ({f.type_repr})" for f in fields)

    def system_message(self, signature: Signature) -> str:
        return (
            f"{signature.instructions}\n\n"
            f"You will receive:\n{self._field_list(signature.inputs)}\n\n"
            f"Respond with exactly these fields, in this order, each starting with its "
            f"own line reading '{self.FIELD_MARK} field_name' followed by the value "
            f"(structured fields -- lists, objects -- as JSON on that line):\n"
            f"{self._field_list(signature.outputs)}\n\n"
            f"Write nothing before the first '{self.FIELD_MARK}' line."
        )

    def _render_fields(self, fields: List[SigField], values: Dict[str, Any]) -> str:
        return "\n".join(f"{self.FIELD_MARK} {f.name}\n{_render_value(f, values[f.name])}"
                         for f in fields)

    def build_messages(self, signature: Signature, examples: List[Dict[str, Any]],
                       inputs: Dict[str, Any]) -> List[dict]:
        messages: List[dict] = []
        for ex in examples:
            messages.append({"role": "user", "content": self._render_fields(signature.inputs, ex)})
            messages.append({"role": "assistant", "content": self._render_fields(signature.outputs, ex)})
        messages.append({"role": "user", "content": self._render_fields(signature.inputs, inputs)})
        return messages

    def parse(self, signature: Signature, raw: str) -> Dict[str, Any]:
        matches = list(self._field_re.finditer(raw))
        if not matches:
            raise ParseError(
                f"model reply had no '{self.FIELD_MARK} field_name' markers: {raw[:200]!r}"
            )
        spans: Dict[str, str] = {}
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
            spans[m.group(1)] = raw[m.end():end].strip()
        for f in signature.outputs:
            if f.name not in spans:
                raise ParseError(f"model reply is missing field {f.name!r}: {raw[:200]!r}")
        return signature.coerce_outputs(spans)


__all__ = ["Adapter", "DelimiterAdapter"]

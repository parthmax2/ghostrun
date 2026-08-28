"""Shared exceptions for the ``ghostrun craft`` framework."""

from __future__ import annotations


class CraftError(RuntimeError):
    """Base class for craft-specific failures (bad signature, bad model output, ...)."""


class SignatureError(CraftError):
    """A signature string didn't parse, or its fields failed validation setup."""


class ParseError(CraftError):
    """A model reply didn't match the expected field structure, or failed
    type/schema validation once parsed."""


class ProviderError(CraftError):
    """The LLM call itself failed (missing key, HTTP error, unsupported provider)."""


__all__ = ["CraftError", "SignatureError", "ParseError", "ProviderError"]

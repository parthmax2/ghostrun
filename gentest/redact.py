"""Redaction of secrets before anything is written to the cache.

The README encourages committing `.gentest_cache/` so prompt changes show up as
reviewable diffs — which makes it a genuine leak risk if raw payloads land on
disk. This module scrubs credentials on the way in.

Scope, deliberately:

* **Request headers** are never stored at all (that's where `Authorization`
  lives), so there is nothing to redact.
* **Response headers** are scrubbed of auth/cookie/identity fields.
* **Request bodies** are scrubbed of secret-looking keys. Bodies are stored for
  human review only — the cache key is computed from the *original* bytes — so
  redacting here cannot affect replay behavior.
* **Response bodies are stored verbatim, by design.** They are what gets
  replayed to your code; rewriting them would corrupt the thing under test.
  If model output itself is sensitive, don't commit the cache.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

MASK = "[REDACTED]"

# Header names dropped/masked from stored responses.
SENSITIVE_HEADERS = frozenset({
    "authorization",
    "proxy-authorization",
    "api-key",
    "x-api-key",
    "cookie",
    "set-cookie",
    "x-auth-token",
    "openai-organization",
    "anthropic-organization-id",
})

# Body keys whose values are masked, matched case-insensitively as substrings so
# `openai_api_key`, `X-Api-Key`, `refresh_token` all hit.
SENSITIVE_KEY_PARTS = (
    "api_key", "apikey", "api-key",
    "authorization", "auth_token", "access_token", "refresh_token",
    "secret", "password", "passwd", "credential", "private_key",
    "session_token", "bearer",
)

# Bare names that are sensitive on their own but too short to substring-match
# safely (e.g. "token" would otherwise swallow "max_tokens").
SENSITIVE_KEY_EXACT = frozenset({
    "token", "key", "auth", "secret", "password", "pwd", "credentials",
})

# Known-benign keys that must never be masked, even if they look sensitive.
# Masking `max_tokens` would make cache files actively misleading.
SAFE_KEYS = frozenset({
    "max_tokens", "max_completion_tokens", "total_tokens", "prompt_tokens",
    "completion_tokens", "token_count", "tokens", "n_tokens", "logit_bias",
    "public_key", "keys",
})

# Value-level patterns for credentials that appear in free text rather than in a
# conveniently-named field.
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),        # OpenAI-style
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}\b"),    # Anthropic-style
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),    # GitHub tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),              # AWS access key id
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE),
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in SAFE_KEYS:
        return False
    if lowered in SENSITIVE_KEY_EXACT:
        return True
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_headers(headers: dict) -> dict:
    return {
        k: (MASK if k.lower() in SENSITIVE_HEADERS else v)
        for k, v in headers.items()
    }


def redact_text(value: str) -> str:
    for pattern in SECRET_VALUE_PATTERNS:
        value = pattern.sub(MASK, value)
    return value


def redact_value(value: Any, extra_keys: Iterable[str] = ()) -> Any:
    """Recursively mask secrets in a decoded JSON structure (or string)."""
    extra = tuple(k.lower() for k in extra_keys)

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                key = str(k)
                if _is_sensitive_key(key) or key.lower() in extra:
                    out[k] = MASK
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(node, list):
            return [_walk(item) for item in node]
        if isinstance(node, str):
            return redact_text(node)
        return node

    return _walk(value)

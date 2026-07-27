"""On-disk record/replay cache for intercepted LLM HTTP calls.

Each cache entry is a single JSON file named by a stable hash of the request
(method + URL + body). The body includes the model name, so different models or
prompts never collide. Files are human-readable so a diff shows exactly what
changed between prompt versions.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .redact import redact_headers, redact_text, redact_value


class CacheMiss(RuntimeError):
    """Raised in replay mode when no cached entry exists for a request or verdict."""


@dataclass
class CachedResponse:
    status_code: int
    headers: dict
    body: bytes  # raw response bytes, verbatim from the provider

    def to_json(self) -> dict:
        return {
            "status_code": self.status_code,
            # Auth/cookie/identity headers never reach disk.
            "headers": redact_headers(self.headers),
            "body": self.body.decode("utf-8", errors="replace"),
        }

    @classmethod
    def from_json(cls, data: dict) -> "CachedResponse":
        return cls(
            status_code=int(data["status_code"]),
            headers=dict(data.get("headers", {})),
            body=data["body"].encode("utf-8"),
        )


def request_key(method: str, url: str, body: bytes) -> str:
    """Deterministic hash for a request.

    The body is normalized via JSON round-trip with sorted keys when possible so
    that semantically identical payloads (key ordering, whitespace) map to the
    same key. Non-JSON bodies are hashed as-is.
    """
    hasher = hashlib.sha256()
    hasher.update(method.upper().encode("utf-8"))
    hasher.update(b"\n")
    hasher.update(url.encode("utf-8"))
    hasher.update(b"\n")
    hasher.update(_normalize_body(body))
    return hasher.hexdigest()[:32]


def _normalize_body(body: bytes) -> bytes:
    if not body:
        return b""
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body
    return json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")


class Cache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    def _path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def has(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def get(self, key: str) -> Optional[CachedResponse]:
        path = self._path_for(key)
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return CachedResponse.from_json(data["response"])

    def put(self, key: str, method: str, url: str, request_body: bytes, response: CachedResponse) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Store a readable copy of the request alongside the response so the
        # cache file is self-documenting when reviewed in a diff.
        #
        # The request body and response headers are redacted on the way in --
        # the cache is meant to be committable. The response *body* is stored
        # verbatim because it is what gets replayed to the code under test.
        # The cache key is derived from the original bytes, so redaction here
        # can never change replay behavior.
        record = {
            "request": {
                "method": method,
                "url": redact_text(url),
                "body": redact_value(_safe_text(request_body)),
            },
            "response": response.to_json(),
        }
        _atomic_write_json(self._path_for(key), record)


def verdict_key(backend: str, model: str, text: str, criterion: str, votes: int = 1) -> str:
    """Deterministic key for a judge verdict.

    The judge's identity (backend + model) is part of the key, so switching
    judge models correctly invalidates previously cached verdicts rather than
    silently reusing another model's opinion. ``votes`` is part of the key too:
    a majority-of-5 verdict carries a different confidence than a single grade,
    so raising judge.votes must not silently reuse an old N=1 cache entry.
    """
    hasher = hashlib.sha256()
    for part in (backend, model, text, criterion):
        hasher.update(part.encode("utf-8"))
        hasher.update(b"\x00")  # unambiguous separator
    hasher.update(str(int(votes)).encode("utf-8"))
    return hasher.hexdigest()[:32]


class KVCache:
    """Tiny JSON key-value store on disk, used for judge verdicts."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    def _path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def has(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def get(self, key: str) -> Optional[dict]:
        path = self._path_for(key)
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def put(self, key: str, payload: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self._path_for(key), payload)


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write via a unique temp file + atomic rename.

    Parallel test workers (``pytest -n``) and threads can target the same key
    concurrently. Writing in place lets a reader observe a half-written file and
    fail with a JSON decode error; ``os.replace`` makes the swap atomic.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # atomic on POSIX and Windows


def _safe_text(body: bytes) -> object:
    if not body:
        return ""
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")

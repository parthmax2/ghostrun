"""Local Ollama judge — the privacy-first default.

Talks to a locally running Ollama daemon at ``/api/chat``. Never leaves the
machine. Failure modes (daemon down, model not pulled) raise a clear, actionable
:class:`JudgeUnavailable` rather than hanging or surfacing a raw 404.
"""

from __future__ import annotations

import json
from typing import Tuple

import httpx

from .base import Grade, build_user_prompt, SYSTEM_PROMPT


class JudgeUnavailable(RuntimeError):
    """The judge backend could not be reached or is misconfigured."""


class OllamaJudge:
    def __init__(self, model: str, base_url: str = "http://localhost:11434",
                 timeout: float = 60.0):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self, probe_timeout: float = 2.0) -> Tuple[bool, str]:
        """Cheap readiness check: is the daemon up and the model pulled?

        Used by ``gentest doctor`` and by anything (like the bundled example's
        conftest) that wants to skip gracefully instead of raising. Uses a
        short timeout by default since this is meant to fail fast, not wait
        for the grading timeout.
        """
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=probe_timeout)
        except httpx.HTTPError as exc:
            return False, (f"Could not reach Ollama at {self.base_url} ({exc}). "
                           f"Is it running? Start it with `ollama serve`.")
        if resp.status_code != 200:
            return False, f"Ollama returned HTTP {resp.status_code} from {self.base_url}."
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        if not any(self.model in name for name in names):
            return False, (f"Model {self.model!r} is not pulled. "
                           f"Run: ollama pull {self.model}")
        return True, f"Ollama reachable at {self.base_url}, model {self.model!r} is pulled."

    def grade(self, text: str, criterion: str) -> Grade:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(text, criterion)},
            ],
            "stream": False,
            # Keep grading deterministic-ish for stable test outcomes.
            "options": {"temperature": 0},
        }
        url = f"{self.base_url}/api/chat"
        try:
            resp = httpx.post(url, json=payload, timeout=self.timeout)
        except httpx.ConnectError as exc:
            raise JudgeUnavailable(
                f"Could not reach Ollama at {self.base_url}. Is it running? "
                f"Start it with `ollama serve`. Original error: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise JudgeUnavailable(
                f"Ollama timed out after {self.timeout}s grading with model "
                f"{self.model!r}. Try a smaller model or raise judge.timeout."
            ) from exc

        if resp.status_code == 404:
            raise JudgeUnavailable(
                f"Ollama model {self.model!r} is not available. "
                f"Pull it first: `ollama pull {self.model}`."
            )
        if resp.status_code >= 400:
            raise JudgeUnavailable(
                f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        content = (data.get("message") or {}).get("content", "")
        if not content:
            raise JudgeUnavailable(
                f"Ollama returned an empty judgement: {json.dumps(data)[:200]}"
            )
        return Grade.parse(content)

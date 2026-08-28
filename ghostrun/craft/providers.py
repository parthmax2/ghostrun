"""LLM client for the search itself: fresh, uncached calls -- see
``optimize.py``'s module docstring for why record/replay doesn't apply here.

litellm-backed, so `craft` reaches dozens of providers, retries, and
streaming for free instead of ghostrun hand-rolling an HTTP client per
provider. ghostrun's own ``"provider:model"`` string (e.g.
``"anthropic:claude-haiku-4-5"``) is the public surface -- litellm is an
implementation detail translated to internally, not something callers need
to know litellm's own model-string conventions for.
"""

from __future__ import annotations

import os
import time
from typing import Iterator, List, Optional

import litellm

from .errors import ProviderError

# ghostrun provider name -> (litellm model prefix, API key env var or None).
# The env var is checked proactively for a clear, stable error message before
# ever calling litellm; providers with non-key auth (a local daemon, cloud
# IAM credentials) are left as None and surface litellm's own error instead.
_PROVIDERS = {
    "openai": ("", "OPENAI_API_KEY"),
    "anthropic": ("anthropic/", "ANTHROPIC_API_KEY"),
    "gemini": ("gemini/", "GEMINI_API_KEY"),
    "groq": ("groq/", "GROQ_API_KEY"),
    "mistral": ("mistral/", "MISTRAL_API_KEY"),
    "cohere": ("cohere/", "COHERE_API_KEY"),
    "deepseek": ("deepseek/", "DEEPSEEK_API_KEY"),
    "xai": ("xai/", "XAI_API_KEY"),
    "perplexity": ("perplexity/", "PERPLEXITYAI_API_KEY"),
    "openrouter": ("openrouter/", "OPENROUTER_API_KEY"),
    "together": ("together_ai/", "TOGETHER_AI_API_KEY"),
    "fireworks": ("fireworks_ai/", "FIREWORKS_AI_API_KEY"),
    "azure": ("azure/", None),      # AZURE_API_KEY + AZURE_API_BASE + AZURE_API_VERSION
    "bedrock": ("bedrock/", None),  # AWS credential chain, not a single API key
    "ollama": ("ollama/", None),    # local daemon, no key
}


class LLMClient:
    """``min_interval`` proactively paces calls (sleeping before a call if the
    previous one finished less than that many seconds ago) instead of only
    reacting after a 429 -- free/low tiers on some providers (observed:
    Gemini) enforce requests-per-minute limits tight enough that a search
    making back-to-back calls trips them well before ``num_retries`` would
    exhaust itself. Default 0 (no pacing) preserves prior behavior.

    Every call's token usage and cost (via ``litellm.completion_cost``, when
    the provider/model has pricing data) accumulate on ``self.total_tokens``
    / ``self.total_cost`` -- read after a `craft()` run to see what it
    actually spent, surfaced in `CraftedPrompt`.
    """

    def __init__(self, model: str, timeout: float = 60.0, num_retries: int = 2,
                min_interval: float = 0.0):
        provider, sep, bare_model = model.partition(":")
        if not sep or not bare_model:
            raise ProviderError(
                f"model must be \"provider:model\", e.g. \"openai:gpt-4o-mini\" "
                f"or \"anthropic:claude-haiku-4-5\" (got {model!r})"
            )
        if provider not in _PROVIDERS:
            raise ProviderError(
                f"unsupported provider {provider!r}; expected one of {sorted(_PROVIDERS)}"
            )
        self.provider = provider
        self.model = bare_model
        self.timeout = timeout
        self.num_retries = num_retries
        self.min_interval = min_interval
        prefix, self._api_key_env = _PROVIDERS[provider]
        self.litellm_model = f"{prefix}{bare_model}"

        self.call_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self._last_call_at: Optional[float] = None

    def _check_api_key(self) -> None:
        if self._api_key_env and not os.environ.get(self._api_key_env):
            raise ProviderError(f"{self._api_key_env} is not set.")

    def _pace(self) -> None:
        if not self.min_interval or self._last_call_at is None:
            return
        wait = self.min_interval - (time.time() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)

    def _track_usage(self, resp) -> None:
        self.call_count += 1
        self._last_call_at = time.time()
        usage = getattr(resp, "usage", None)
        if usage is not None:
            self.total_tokens += getattr(usage, "total_tokens", 0) or 0
        try:
            cost = litellm.completion_cost(completion_response=resp)
        except Exception:
            cost = None  # no pricing data for this model/provider -- not fatal
        if cost:
            self.total_cost += cost

    def complete(self, system: str, messages: List[dict], temperature: float = 0.0) -> str:
        self._check_api_key()
        self._pace()
        try:
            resp = litellm.completion(
                model=self.litellm_model,
                messages=[{"role": "system", "content": system}, *messages],
                temperature=temperature,
                timeout=self.timeout,
                num_retries=self.num_retries,
            )
        except Exception as exc:
            raise ProviderError(f"{self.provider} call failed: {exc}") from exc
        self._track_usage(resp)
        return resp.choices[0].message.content or ""

    def stream(self, system: str, messages: List[dict], temperature: float = 0.0) -> Iterator[str]:
        """Yield text chunks as they arrive. Not used by `craft()`'s search
        (which needs the complete text to grade), but available for building
        a streaming UI on top of a crafted or hand-written prompt."""
        self._check_api_key()
        self._pace()
        try:
            stream = litellm.completion(
                model=self.litellm_model,
                messages=[{"role": "system", "content": system}, *messages],
                temperature=temperature,
                timeout=self.timeout,
                num_retries=self.num_retries,
                stream=True,
            )
            self.call_count += 1
            self._last_call_at = time.time()
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise ProviderError(f"{self.provider} call failed: {exc}") from exc


__all__ = ["LLMClient"]

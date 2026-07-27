"""A tiny 'customer support' app that calls an LLM over HTTP.

This stands in for real user code. It uses httpx to POST to the OpenAI
chat-completions endpoint exactly like the official SDK does under the hood, so
GenTest's transport-layer interceptor records and replays it transparently.

In a real project you'd call `openai.OpenAI().chat.completions.create(...)`; the
raw httpx call here keeps the example dependency-free while exercising the same
code path GenTest hooks.
"""

from __future__ import annotations

import os

import httpx

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are an empathetic customer support agent for an online store. "
    "Apologize for any inconvenience, explain the refund policy clearly, and "
    "never argue with the customer."
)


def generate_reply(customer_message: str, model: str = "gpt-4o-mini") -> str:
    """Ask the LLM to draft a support reply and return the text."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-not-needed-when-replaying")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": customer_message},
        ],
        "temperature": 0.7,
    }
    resp = httpx.post(
        OPENAI_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

"""Thin wrapper around the Groq SDK with rate-limit-aware retries.

We use Llama 3.3 70B Versatile on the free tier:
- 30 requests/min, 6000 tokens/min, 100k tokens/day (approx)
- This wrapper retries on rate-limit errors with exponential backoff.

Two helpers:
- chat_json(): for scorer/critic/email-classifier — uses response_format json_object
- chat_text(): for improver — returns raw text (delimiter-based parsing)
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from groq import Groq, RateLimitError, APIError

log = logging.getLogger(__name__)

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
_API_KEY = os.getenv("GROQ_API_KEY")

_client: Groq | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not _API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=_API_KEY)
    return _client


def _call_with_retry(messages: list[dict], *, json_mode: bool, max_retries: int = 5,
                     temperature: float = 0.2, max_tokens: int = 4096) -> str:
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    delay = 4.0
    for attempt in range(max_retries):
        try:
            resp = get_client().chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except RateLimitError as e:
            wait = getattr(e, "retry_after", None) or delay
            log.warning("Groq rate-limited (attempt %d/%d), sleeping %.1fs",
                        attempt + 1, max_retries, wait)
            time.sleep(wait)
            delay = min(delay * 2, 60)
        except APIError as e:
            # Transient 5xx — same backoff
            if attempt == max_retries - 1:
                raise
            log.warning("Groq API error (%s), retrying in %.1fs", e, delay)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise RuntimeError("Groq call exhausted retries")


def chat_json(system: str, user: str, **kwargs) -> dict:
    raw = _call_with_retry(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True, **kwargs,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSON-mode usually guarantees parseable output, but salvage if it doesn't
        log.error("Groq returned non-JSON despite json_mode: %s", raw[:500])
        raise


def chat_text(system: str, user: str, **kwargs) -> str:
    return _call_with_retry(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=False, **kwargs,
    )

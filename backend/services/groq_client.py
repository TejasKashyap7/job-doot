"""Thin wrapper around the Groq SDK with rate-limit-aware retries and per-user
key rotation (multi-user — see .claude/specs/multi-user/approach.md).

Used for resume TAILORING only (critic/improver) — scoring runs on the shared
local Ollama instance (local_llm_client.py), so no Groq quota is involved there.

Callers pass a list of API keys (a user's GroqKey rows, in priority order). On a
rate-limit/quota error we distinguish two cases:
  - short retry_after (a few seconds) => transient TPM/RPM limit, retry the SAME key
  - no retry_after, or a long one     => treat as exhausted for this session, rotate
    to the NEXT key immediately rather than sleeping through it
Once a key works, we remember its index (per key-list) so the next call starts
there instead of re-trying exhausted keys from the front every time.
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
_ENV_API_KEY = os.getenv("GROQ_API_KEY")  # fallback when no explicit key list is passed

# A retry_after above this is treated as "this key is done for now" — rotate
# rather than block the whole tailoring pass sleeping for it.
ROTATE_THRESHOLD_SEC = 30.0

_client_cache: dict[str, Groq] = {}
_key_index_cache: dict[tuple[str, ...], int] = {}


def _get_client(key: str) -> Groq:
    if key not in _client_cache:
        _client_cache[key] = Groq(api_key=key)
    return _client_cache[key]


def _call_with_retry(messages: list[dict], *, json_mode: bool, api_keys: list[str] | None = None,
                     max_retries: int = 5, temperature: float = 0.2, max_tokens: int = 4096) -> str:
    keys = [k for k in (api_keys or ([_ENV_API_KEY] if _ENV_API_KEY else [])) if k]
    if not keys:
        raise RuntimeError("No Groq API key available")

    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    cache_key = tuple(keys)
    start_idx = _key_index_cache.get(cache_key, 0) % len(keys)
    last_err: Exception | None = None

    for offset in range(len(keys)):
        idx = (start_idx + offset) % len(keys)
        key = keys[idx]
        client = _get_client(key)
        delay = 4.0
        for attempt in range(max_retries):
            try:
                resp = client.chat.completions.create(**kwargs)
                _key_index_cache[cache_key] = idx  # remember the key that worked
                return resp.choices[0].message.content or ""
            except RateLimitError as e:
                wait = getattr(e, "retry_after", None)
                if wait is None or wait > ROTATE_THRESHOLD_SEC:
                    log.warning("Groq key %d/%d looks exhausted (retry_after=%s) — rotating",
                                idx + 1, len(keys), wait)
                    last_err = e
                    break  # stop retrying this key, try the next one
                log.warning("Groq rate-limited on key %d/%d, sleeping %.1fs (attempt %d/%d)",
                            idx + 1, len(keys), wait, attempt + 1, max_retries)
                time.sleep(wait)
            except APIError as e:
                if attempt == max_retries - 1:
                    last_err = e
                    break
                log.warning("Groq API error (%s) on key %d/%d, retrying in %.1fs",
                            e, idx + 1, len(keys), delay)
                time.sleep(delay)
                delay = min(delay * 2, 60)
        else:
            continue  # exhausted retries on this key without a rotate signal — try next anyway
    raise RuntimeError(f"Groq call exhausted all {len(keys)} key(s): {last_err}")


def chat_json(system: str, user: str, *, api_keys: list[str] | None = None, **kwargs) -> dict:
    raw = _call_with_retry(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True, api_keys=api_keys, **kwargs,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSON-mode usually guarantees parseable output, but salvage if it doesn't
        log.error("Groq returned non-JSON despite json_mode: %s", raw[:500])
        raise


def chat_text(system: str, user: str, *, api_keys: list[str] | None = None, **kwargs) -> str:
    return _call_with_retry(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=False, api_keys=api_keys, **kwargs,
    )

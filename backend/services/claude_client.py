"""Claude-backed LLM client — Vasu's instance only.

Drop-in for services.groq_client / services.local_llm_client: same
`chat_json(system, user) -> dict` and `chat_text(system, user) -> str`, so the
three callers (critic, improver, scorer) swap by changing one import line.

Instead of calling Groq or Ollama directly, this posts to the host shim
(tools/claude_shim.py) which runs `claude -p` on Vasu's subscription. See
.claude/specs/claude-llm/approach.md.

Groq/Ollama-specific kwargs (api_keys, temperature) are accepted and ignored so
call sites don't need rewriting. `model` selects "haiku" (default, cheap) or
"sonnet" (tailoring quality).
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

SHIM_URL = os.getenv("CLAUDE_SHIM_URL", "http://host.docker.internal:8099")
SHIM_TOKEN = os.getenv("CLAUDE_SHIM_TOKEN", "")
DEFAULT_MODEL = os.getenv("CLAUDE_DEFAULT_MODEL", "haiku")
TIMEOUT = int(os.getenv("CLAUDE_CLIENT_TIMEOUT", "200"))


def _call(system: str, user: str, *, want_json: bool, model: str | None,
          max_retries: int = 3, **_ignored: Any) -> str:
    """POST to the shim. _ignored swallows api_keys/temperature/max_tokens etc."""
    payload = {
        "system": system,
        "user": user,
        "json": want_json,
        "model": model or DEFAULT_MODEL,
    }
    headers = {"X-Shim-Token": SHIM_TOKEN} if SHIM_TOKEN else {}
    delay = 3.0
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = requests.post(f"{SHIM_URL}/chat", json=payload, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()["text"]
        except Exception as e:
            last_err = e
            log.warning("claude shim call failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError(f"claude shim exhausted retries: {last_err}")


def _salvage_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # strip ``` fences / leading prose, then take the outermost {...}
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("```", 2)[1] if "```" in s[3:] else s.strip("`")
            s = s.replace("json", "", 1).strip() if s.lstrip().startswith("json") else s
        i, j = s.find("{"), s.rfind("}")
        if i != -1 and j != -1 and j > i:
            return json.loads(s[i:j + 1])
        raise


def chat_json(system: str, user: str, *, model: str | None = None, **kwargs) -> dict:
    raw = _call(system, user, want_json=True, model=model, **kwargs)
    try:
        return _salvage_json(raw)
    except json.JSONDecodeError:
        log.error("claude returned non-JSON: %s", raw[:500])
        raise


def chat_text(system: str, user: str, *, model: str | None = None, **kwargs) -> str:
    return _call(system, user, want_json=False, model=model, **kwargs)

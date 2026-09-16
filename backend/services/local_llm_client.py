"""Thin wrapper around a local Ollama instance (Gemma 3 4B) running on the Pi host.

Mirrors services.groq_client's chat_json/chat_text interface so callers can swap
providers by changing one import. Runs outside this container — reached via
host.docker.internal (mapped to the host gateway in docker-compose.yml).
No rate limits since it's local; retries here only cover transient issues
(Ollama restarting, model still loading).
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
BASE_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")


def _call_with_retry(messages: list[dict], *, json_mode: bool, max_retries: int = 3,
                     temperature: float = 0.2, max_tokens: int = 4096) -> str:
    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"

    delay = 2.0
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            last_err = e
            log.warning("Ollama call failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError(f"Ollama call exhausted retries: {last_err}")


def chat_json(system: str, user: str, **kwargs) -> dict:
    raw = _call_with_retry(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True, **kwargs,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.error("Ollama returned non-JSON despite format=json: %s", raw[:500])
        raise


def chat_text(system: str, user: str, **kwargs) -> str:
    return _call_with_retry(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=False, **kwargs,
    )

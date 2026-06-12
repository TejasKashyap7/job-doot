"""Tiny Telegram client over plain HTTP. No SDK needed."""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send(text: str, *, parse_mode: str | None = None, silent: bool = False) -> bool:
    """Returns True on 2xx. Logs and swallows errors so callers never crash on a flaky Telegram."""
    if not _TOKEN or not _CHAT_ID:
        log.warning("Telegram not configured — skipping message")
        return False
    payload: dict = {"chat_id": _CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if silent:
        payload["disable_notification"] = True
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            json=payload, timeout=10,
        )
        if not r.ok:
            log.error("Telegram %d: %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as e:
        log.error("Telegram send failed: %s", e)
        return False

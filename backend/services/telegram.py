"""Tiny Telegram client over plain HTTP. No SDK needed."""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send(text: str, *, parse_mode: str | None = None, silent: bool = False,
         token: str | None = None, chat_id: str | None = None) -> bool:
    """Returns True on 2xx. Logs and swallows errors so callers never crash on a flaky Telegram.

    Defaults to the admin/system channel (env vars) for operational alerts —
    scoring failures, deploy status, LinkedIn cookie issues. Pass `token`/`chat_id`
    explicitly to send to a specific user's own bot instead (multi-user, optional
    per user — see .claude/specs/multi-user/approach.md). `send_to_user()` below is
    the usual way callers do that.
    """
    use_token = token or _TOKEN
    use_chat_id = chat_id or _CHAT_ID
    if not use_token or not use_chat_id:
        log.warning("Telegram not configured — skipping message")
        return False
    payload: dict = {"chat_id": use_chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if silent:
        payload["disable_notification"] = True
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{use_token}/sendMessage",
            json=payload, timeout=10,
        )
        if not r.ok:
            log.error("Telegram %d: %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as e:
        log.error("Telegram send failed: %s", e)
        return False


def send_to_user(user, text: str, *, parse_mode: str | None = None, silent: bool = False) -> bool:
    """Send to a specific user's own Telegram, if they've connected one. No-op
    (returns False, no log spam) if they haven't — Telegram is optional per user."""
    if not user.telegram_enabled or not user.telegram_bot_token or not user.telegram_chat_id:
        return False
    return send(text, parse_mode=parse_mode, silent=silent,
                token=user.telegram_bot_token, chat_id=user.telegram_chat_id)

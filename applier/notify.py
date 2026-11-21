"""Telegram alerts, using the notify user's own bot (multi-user: creds live on the users row)."""
import logging

import requests

from .backend import telegram_creds

log = logging.getLogger(__name__)
_creds_cache: dict = {}


def send(cfg, text: str) -> None:
    key = cfg["notify_user_id"]
    if key not in _creds_cache:
        _creds_cache[key] = telegram_creds(cfg)
    c = _creds_cache[key]
    if not c or not c.get("token") or not c.get("chat_id"):
        log.info("Telegram not configured; message was: %s", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{c['token']}/sendMessage",
            json={"chat_id": c["chat_id"], "text": text[:4000]},
            timeout=20,
        )
    except Exception as exc:
        log.warning("Telegram send failed: %s", exc)

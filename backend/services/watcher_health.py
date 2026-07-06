"""Cross-container liveness for the gmail-watcher (Flaw 15).

The watcher runs in a separate container, so the backend can't see it directly. Instead
the watcher writes an epoch timestamp to `data/watcher_last_seen.txt` each poll cycle
(shared volume); the backend reads it here for the dashboard health light + the daily
heartbeat. No web server on the watcher needed.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def _marker_path() -> Path:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/jobs.db")
    return Path(db_url.split("///")[-1]).parent / "watcher_last_seen.txt"


def watcher_status() -> dict:
    """{'state': 'running'|'down', 'label': str, 'age_sec': int|None}.
    'down' when the watcher hasn't checked in within a few poll intervals, or never has."""
    poll = int(os.getenv("GMAIL_POLL_SEC", "7200"))
    threshold = max(3 * poll, 3600)  # a few missed polls => treat as down
    try:
        last = int(float(_marker_path().read_text().strip()))
    except (FileNotFoundError, ValueError, OSError):
        return {"state": "down", "label": "no signal", "age_sec": None}
    age = int(time.time()) - last
    if age <= threshold:
        return {"state": "running", "label": "running", "age_sec": age}
    return {"state": "down", "label": f"stale ({age // 3600}h)", "age_sec": age}

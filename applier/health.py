"""Last-slot health for the phone widget. The backend's /api/summary reads
DATA/HEALTH.json read-only. Spec: .claude/specs/dashboard/phone-widget.md
→ "Applier errors on the widget"."""
import json
import os
from datetime import datetime

from .config import DATA

FILE = DATA / "HEALTH.json"

OK, CRASHED, LOGGED_OUT = "ok", "crashed", "claude_logged_out"

writes = 0  # bumped on every record(); the daemon uses it to see if a slot reported itself

_LOGIN_MARKERS = ("failed to authenticate", "oauth session expired", "not logged in",
                  "invalid api key", "please run /login")


def is_login_error(text: str | None) -> bool:
    t = (text or "").lower()
    return any(m in t for m in _LOGIN_MARKERS)


def read() -> dict:
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return {}


def record(result: str, message: str = "", detail: str = "") -> None:
    """Never raises: health reporting must not break a slot."""
    global writes
    writes += 1
    try:
        prev = read()
        streak = 0 if result == OK else (prev.get("streak", 0) + 1 if prev.get("result") == result else 1)
        data = {"at": datetime.now().isoformat(timespec="seconds"), "result": result,
                "message": message[:40], "detail": detail[:300], "streak": streak}
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, FILE)
    except Exception:
        pass

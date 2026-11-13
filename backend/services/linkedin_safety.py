"""LinkedIn safety card on Today — read-only from data/applier/applier.db.
Spec: .claude/specs/dashboard/approach.md -> "LinkedIn safety card"; the applier writes
account_checks / daily_activity (apply-agent approach.md "LinkedIn account health check")."""
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

APPLIER_DIR = Path(os.getenv("APPLIER_DATA_DIR", "/app/data/applier"))

IST = ZoneInfo("Asia/Kolkata")   # the applier writes local (IST) naive times; the container may be UTC


def _now() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)


_WORDS = {"ok": "No warnings", "note": "Notice", "warning": "Warning", "error": "Check couldn't run"}


def _ago(ts: str) -> str:
    try:
        mins = int((_now() - datetime.fromisoformat(ts)).total_seconds() // 60)
    except (TypeError, ValueError):
        return ""
    return "just now" if mins < 1 else f"{mins} min ago" if mins < 60 else \
        f"{mins // 60} h ago" if mins < 1440 else f"{mins // 1440} d ago"


def card() -> dict | None:
    db = APPLIER_DIR / "applier.db"
    if not db.exists():
        return None
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
    try:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "account_checks" not in tables:
            return {"checked": False}
        last = c.execute("SELECT checked_at, status, signals FROM account_checks ORDER BY id DESC LIMIT 1").fetchone()
        first_day = c.execute("SELECT min(day) FROM account_checks").fetchone()[0]
        warn_days = {r[0] for r in c.execute("SELECT DISTINCT day FROM account_checks WHERE status='warning'")}
        applied = dict(c.execute("SELECT date(created_at), count(*) FROM attempts WHERE status='applied' "
                                 "GROUP BY 1").fetchall())
        views = dict(c.execute("SELECT day, views FROM daily_activity").fetchall()) \
            if "daily_activity" in tables else {}
    finally:
        c.close()

    today = _now().date()
    # clean days in a row: back from today until a warning day (or the first checked day)
    streak, d = 0, today
    while first_day and d.isoformat() >= first_day and d.isoformat() not in warn_days:
        streak += 1
        d -= timedelta(days=1)
    # proven-safe ceiling: most applications in one day with no warning that day or the next
    safe = [(n, day) for day, n in applied.items()
            if day not in warn_days
            and (date.fromisoformat(day) + timedelta(days=1)).isoformat() not in warn_days]
    ceiling = max(safe) if safe else (0, None)
    t = today.isoformat()
    return {
        "checked": bool(last),
        "status": last[1] if last else "none",
        "status_text": _WORDS.get(last[1], last[1]) if last else "Not checked yet",
        "signals": (last[2] or "") if last else "",
        "ago": _ago(last[0]) if last else "",
        "clean_days": streak,
        "applied_today": applied.get(t, 0),
        "views_today": views.get(t, 0),
        "ceiling": ceiling[0],
        "ceiling_day": date.fromisoformat(ceiling[1]).strftime("%-d %b") if ceiling[1] else "",
    }

"""In-app notification centre (the bell). Spec: .claude/specs/notifications/approach.md

user_id=None → system event (admins see it); user_id=N → that user's own event.
Writers must never break the caller: every public writer swallows its own errors.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import or_

from database.db import SessionLocal
from database.models import Notification
from services.problem_tags import TAGS, classify, clean_why, plain_reason, tag_info, url_of

log = logging.getLogger(__name__)

KEEP_PER_AUDIENCE = 200
APPLIER_DIR = Path(os.getenv("APPLIER_DATA_DIR", "/app/data/applier"))
OWNER_USER_ID = int(os.getenv("SUMMARY_USER_ID", "1"))


# ---------- write ----------

def notify(user_id: int | None, key: str, level: str, title: str,
           detail: str = "", fix: str = "", action_url: str | None = None,
           tag: str | None = None, tech: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(Notification(user_id=user_id, key=key, level=level, title=title[:300],
                            detail=detail or None, fix=fix or None, action_url=action_url,
                            tag=tag, tech=tech or None))
        db.flush()
        # prune: keep the newest KEEP_PER_AUDIENCE for this audience
        q = db.query(Notification.id).filter(
            Notification.user_id.is_(None) if user_id is None else Notification.user_id == user_id)
        old = [r.id for r in q.order_by(Notification.id.desc()).offset(KEEP_PER_AUDIENCE).all()]
        if old:
            db.query(Notification).filter(Notification.id.in_(old)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("notify failed (%s)", key)
    finally:
        db.close()


# ---------- read (per viewer) ----------

def _visible(q, user):
    if user.is_admin:
        return q.filter(or_(Notification.user_id.is_(None), Notification.user_id == user.id))
    return q.filter(Notification.user_id == user.id)


def unread_count(user) -> int:
    if not user:
        return 0
    db = SessionLocal()
    try:
        return _visible(db.query(Notification), user).filter(Notification.read_at.is_(None)).count()
    except Exception:
        return 0
    finally:
        db.close()


def list_for(db, user, limit: int = 100) -> list[Notification]:
    return (_visible(db.query(Notification), user)
            .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).all())


def mark_all_read(db, user) -> None:
    _visible(db.query(Notification), user).filter(Notification.read_at.is_(None)) \
        .update({Notification.read_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()


def clear_all(db, user) -> None:
    _visible(db.query(Notification), user).delete(synchronize_session=False)
    db.commit()


# ---------- applier watcher (scheduler job, every 5 min) ----------
# The applier runs on the Pi host (~/job-doot-applier) and is NOT modified; we read its
# mounted data dir and turn new rows / pause-flag flips into notifications.

APPLIER_KEYS = ("applier_failed", "applier_needs_you")
GROUP = {"applier_failed": "Couldn't apply", "applier_needs_you": "Needs you"}


def _tag_value(detail: str) -> str:
    """Stored tag: the key, or "new:<Label as Claude wrote it>" for a new kind."""
    key, label = classify(detail)
    return f"new:{label}" if key.startswith("new:") else key


def _title(title: str | None, company: str | None) -> str:
    role = (title or "").strip()
    role = role if len(role) <= 60 else role[:58].rstrip() + "\u2026"
    return " \u2014 ".join(x for x in (company, role) if x) or "a job"


def applier_event(status: str, detail: str, title: str | None, company: str | None,
                  url: str | None) -> dict:
    """Everything a bell row needs for one failed / needs-you attempt (spec: wording rules)."""
    tag = _tag_value(detail)
    info = tag_info(tag.lower() if tag.startswith("new:") else tag, tag.removeprefix("new:"))
    return {"key": "applier_needs_you" if detail.startswith("needs_human:") else "applier_failed",
            "title": _title(title, company), "detail": plain_reason(detail), "fix": info.next,
            "action_url": url_of(detail) or url, "tag": tag, "tech": detail}


def _state_path() -> Path:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/jobs.db")
    return Path(db_url.split("///", 1)[-1]).parent / "notify_state.json"


def _load_state() -> dict | None:
    try:
        return json.loads(_state_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_state(s: dict) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s))


def _where(t: str | None, c: str | None) -> str:
    return " @ ".join(x for x in (t, c) if x) or "a job"


def watch_applier() -> None:
    try:
        _watch_applier()
    except Exception:
        log.exception("applier watcher failed")


def _watch_applier() -> None:
    pause_file = APPLIER_DIR / "PAUSED"
    paused = pause_file.exists()
    reason = (pause_file.read_text().strip()[:200] or "paused") if paused else ""
    rows, max_id, recent_fail = [], 0, []
    db_path = APPLIER_DIR / "applier.db"
    if db_path.exists():
        c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='attempts'").fetchone():
                max_id = c.execute("SELECT coalesce(max(id),0) FROM attempts").fetchone()[0]
                state = _load_state()
                since = state["last_attempt_id"] if state else max_id
                rows = c.execute(
                    "SELECT id, status, detail, title, company, url FROM attempts "
                    "WHERE id > ? ORDER BY id", (since,)).fetchall()
                recent_fail = c.execute(
                    "SELECT detail, title, company FROM attempts WHERE status='failed' "
                    "ORDER BY id DESC LIMIT 3").fetchall()
        finally:
            c.close()

    state = _load_state()
    first_run = state is None
    was_paused = bool(state and state.get("paused"))

    if not first_run:
        for _id, st, detail, title, company, url in rows:
            detail = detail or ""
            if st == "failed" or detail.startswith("needs_human:"):
                ev = applier_event(st, detail, title, company, url)
                notify(OWNER_USER_ID, ev.pop("key"), "warning", ev.pop("title"), **ev)

    if paused and (first_run or not was_paused):
        reasons = [tag_info(*classify(d or "")).label for d, t, co in recent_fail]
        lines = [f"• {_where(t, co)}" for d, t, co in recent_fail]
        # same explanation for every job? say it once
        if reasons and len(set(reasons)) == 1:
            lines.append(f"\nWhat happened: {reasons[0]}")
        else:
            lines = [f"{l} — {r}" for l, r in zip(lines, reasons)]
        notify(OWNER_USER_ID, "applier_paused", "error", f"Applier paused: {reason}",
               detail=("Last failures:\n" + "\n".join(lines)) if lines else "",
               fix="It won't apply to anything until resumed. On the Pi: "
                   "cd ~/job-doot-applier && python -m applier.run resume")
    elif was_paused and not paused:
        notify(OWNER_USER_ID, "applier_resumed", "success", "Applier resumed",
               detail="The pause flag was cleared; applying continues at the next slot.")

    _save_state({"last_attempt_id": max_id, "paused": paused})


# ---------- one-time backfill: tag + re-word existing applier notifications ----------

_OLD_WRAPPERS = ("What happened: ", "Haiku looked at the page and gave up. In its own words: ")
_OLD_TAILS = (" Open the job and apply by hand if you want it.",)
_OLD_FIXED = ("The company site asks you to sign in", "This company uses an application system",
              "The site showed a CAPTCHA", "The site asked for card", "The applier couldn't find",
              "A fixed script (not the AI)", "Claude (the AI that answers", "The applier program itself",
              "The LinkedIn Easy Apply window")


def _old_title(title: str) -> str:
    for pre in ("Couldn't apply: ", "Needs you: "):
        if title.startswith(pre):
            role, _, company = title[len(pre):].rpartition(" @ ")
            return _title(role or None, company or None) if role else title[len(pre):]
    return title


def backfill_tags() -> int:
    """Idempotent: only rows with tag IS NULL. Spec: notifications/approach.md (problem tags)."""
    db = SessionLocal()
    n = 0
    try:
        rows = db.query(Notification).filter(Notification.key.in_(APPLIER_KEYS),
                                             Notification.tag.is_(None)).all()
        for r in rows:
            raw = r.detail or ""
            text = raw
            for w in _OLD_WRAPPERS:
                text = text.replace(w, "", 1)
            for t in _OLD_TAILS:
                text = text.replace(t, "")
            text = text.strip().strip("“”").strip()
            prefix = "needs_human:" if r.key == "applier_needs_you" else ""
            tag = _tag_value(prefix + text)
            r.tag = tag
            r.tech = raw or None
            r.title = _old_title(r.title or "")
            r.detail = "" if text.startswith(_OLD_FIXED) else clean_why(text)
            r.fix = tag_info(tag.lower() if tag.startswith("new:") else tag, tag.removeprefix("new:")).next
            n += 1
        db.commit()
    except Exception:
        db.rollback()
        log.exception("notification tag backfill failed")
    finally:
        db.close()
    return n

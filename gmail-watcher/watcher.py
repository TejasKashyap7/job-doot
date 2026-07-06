"""Gmail watcher — polls inbox every 15 minutes, classifies unread mail via Groq,
writes email_log row, fires Telegram for REAL_RESPONSE, marks SPAM_TRAP /
AUTO_REJECTION as read, ignores NEUTRAL.

Runs as its own container (separate from backend) so an OAuth/Gmail crash
doesn't take down the dashboard. Shares the SQLite DB via a volume mount.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from groq import Groq, RateLimitError, APIError
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gmail-watcher")

# ---------- Config ----------
POLL_INTERVAL = int(os.getenv("GMAIL_POLL_SEC", "7200"))  # 2 hours
MAX_RESULTS = int(os.getenv("GMAIL_MAX_RESULTS", "50"))
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "/app/data/token.json")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/jobs.db")
# Cross-container liveness (Flaw 15): the backend heartbeat + dashboard read this file to
# show whether the watcher is alive. Written each poll cycle to the shared data volume.
WATCHER_HEARTBEAT_PATH = Path(DATABASE_URL.split("///")[-1]).parent / "watcher_last_seen.txt"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]

EMAIL_CLASSIFIER_SYSTEM = """Classify this email as one of exactly four categories.
Output JSON only.

Categories:
- REAL_RESPONSE: Genuine recruiter or company reply. Interview invite, assessment scheduled, HR call request, offer discussion, follow up on application.
- SPAM_TRAP: Fake "you are hired" emails, asks for money, registration fees, unclear company, naukri/shine/monster automated spam, too good to be true offers.
- AUTO_REJECTION: Automated rejection, "we went with another candidate", "position filled", "not moving forward".
- NEUTRAL: Job alerts, newsletters, platform notifications, anything that needs no action.

Red flags for SPAM_TRAP: asking for money, no real company name, "pay to get hired", vague promises, sender domains that look suspicious, naukri/shine/timesjobs sender patterns.

OUTPUT:
{"category": "REAL_RESPONSE/SPAM_TRAP/AUTO_REJECTION/NEUTRAL", "confidence": "high/medium/low", "reason": "one line"}
"""


# ---------- Minimal email_log ORM (mirrors backend.database.models.EmailLog) ----------
# KEEP IN SYNC WITH backend/database/models.py EmailLog — same table, separate definition.
# If you add/remove columns in models.py, update this class too.
Base = declarative_base()

class EmailLog(Base):
    __tablename__ = "email_log"
    id = Column(Integer, primary_key=True)
    gmail_msg_id = Column(String, unique=True, index=True)
    sender = Column(String)
    subject = Column(String)
    body_snippet = Column(Text)
    category = Column(String, index=True)
    confidence = Column(String)
    reason = Column(String)
    received_at = Column(DateTime, default=datetime.utcnow)
    alerted = Column(Boolean, default=False)


_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


# ---------- Helpers ----------
def gmail_client() -> "googleapiclient.discovery.Resource":
    p = Path(TOKEN_PATH)
    if not p.exists():
        raise FileNotFoundError(f"{TOKEN_PATH} missing — run tools/oauth_bootstrap.py")
    creds = Credentials.from_authorized_user_file(str(p), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        p.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def extract_body_snippet(msg: dict, max_chars: int = 2000) -> str:
    snippet = msg.get("snippet", "") or ""
    payload = msg.get("payload", {}) or {}

    def _walk(p):
        if p.get("mimeType", "").startswith("text/plain"):
            data = p.get("body", {}).get("data")
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                except Exception:
                    return ""
        for child in p.get("parts", []) or []:
            r = _walk(child)
            if r:
                return r
        return ""

    body = _walk(payload) or snippet
    return body[:max_chars]


def telegram_send(text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log.warning("Telegram not configured — skipping alert")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": text}, timeout=10,
        )
        if not r.ok:
            log.error("Telegram %d: %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        log.error("Telegram send failed: %s", e)


# ---------- Groq classifier with retry ----------
_groq: Groq | None = None

def groq() -> Groq:
    global _groq
    if _groq is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set")
        _groq = Groq(api_key=GROQ_API_KEY)
    return _groq


def classify(sender: str, subject: str, body_snippet: str) -> dict:
    user = (
        f"EMAIL:\nSender: {sender}\nSubject: {subject}\n"
        f"Body: {body_snippet}"
    )
    delay = 4.0
    for attempt in range(5):
        try:
            resp = groq().chat.completions.create(
                model=GROQ_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": EMAIL_CLASSIFIER_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.1, max_tokens=200,
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except RateLimitError as e:
            wait = getattr(e, "retry_after", None) or delay
            log.warning("Groq 429 (attempt %d), sleeping %.1fs", attempt + 1, wait)
            time.sleep(wait); delay = min(delay * 2, 60)
        except APIError as e:
            log.warning("Groq API err: %s", e)
            time.sleep(delay); delay = min(delay * 2, 60)
    return {"category": "NEUTRAL", "confidence": "low", "reason": "groq exhausted retries"}


# ---------- Action ----------
def handle_message(svc, msg_id: str) -> None:
    db = SessionLocal()
    try:
        if db.query(EmailLog.id).filter(EmailLog.gmail_msg_id == msg_id).first():
            return  # already processed in a prior poll

        msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
        sender = header(msg["payload"], "From")
        subject = header(msg["payload"], "Subject")
        body = extract_body_snippet(msg)

        result = classify(sender, subject, body)
        category = (result.get("category") or "NEUTRAL").upper().strip()
        if category not in {"REAL_RESPONSE", "SPAM_TRAP", "AUTO_REJECTION", "NEUTRAL"}:
            category = "NEUTRAL"

        log.info("msg %s → %s (%s)", msg_id, category, sender[:60])

        if category == "NEUTRAL":
            return  # spec: don't even log

        row = EmailLog(
            gmail_msg_id=msg_id, sender=sender, subject=subject,
            body_snippet=body[:1000],
            category=category,
            confidence=result.get("confidence", ""),
            reason=result.get("reason", ""),
            alerted=False,
        )
        db.add(row); db.commit()

        if category == "REAL_RESPONSE":
            telegram_send(
                "🔔 REAL RESPONSE RECEIVED\n\n"
                f"From: {sender}\n"
                f"Subject: {subject}\n\n"
                f"{body[:600]}\n\n"
                "Check your email for full details."
            )
            row.alerted = True; db.commit()

        if category in {"SPAM_TRAP", "AUTO_REJECTION"}:
            try:
                svc.users().messages().modify(
                    userId="me", id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()
            except HttpError as e:
                log.error("Failed to mark %s read: %s", msg_id, e)
    finally:
        db.close()


def retry_unalerted() -> None:
    """Re-send Telegram alerts for REAL_RESPONSE emails logged but never alerted (e.g. Telegram was down)."""
    db = SessionLocal()
    try:
        pending = db.query(EmailLog).filter(
            EmailLog.category == "REAL_RESPONSE",
            EmailLog.alerted == False,
        ).all()
        if not pending:
            return
        log.info("retry_unalerted: %d email(s) pending re-alert", len(pending))
        for row in pending:
            telegram_send(
                "🔔 REAL RESPONSE (RETRY ALERT)\n\n"
                f"From: {row.sender}\n"
                f"Subject: {row.subject}\n\n"
                f"{(row.body_snippet or '')[:600]}\n\n"
                "Check your email for full details."
            )
            row.alerted = True
            db.commit()
    finally:
        db.close()


def poll_once(svc) -> None:
    retry_unalerted()
    log.info("poll: listing UNREAD inbox messages")
    try:
        resp = svc.users().messages().list(
            userId="me", q="is:unread in:inbox", maxResults=MAX_RESULTS,
        ).execute()
    except HttpError as e:
        log.error("Gmail list failed: %s", e)
        return
    messages = resp.get("messages", []) or []
    log.info("poll: %d unread to process", len(messages))
    for m in messages:
        try:
            handle_message(svc, m["id"])
        except Exception:
            log.exception("handle_message failed for %s", m["id"])
        time.sleep(2)  # gentle on Groq TPM


def _touch_heartbeat() -> None:
    """Mark the watcher alive for the backend heartbeat + dashboard light (Flaw 15)."""
    try:
        WATCHER_HEARTBEAT_PATH.write_text(str(int(time.time())))
    except OSError:
        log.warning("could not write watcher heartbeat", exc_info=True)


def main() -> None:
    Base.metadata.create_all(_engine)  # safe — backend will have created table already
    log.info("gmail-watcher starting (poll every %ds)", POLL_INTERVAL)
    while True:
        try:
            svc = gmail_client()
            poll_once(svc)
        except Exception:
            log.exception("poll cycle crashed — sleeping then retrying")
        _touch_heartbeat()  # loop is alive, even if this cycle errored
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

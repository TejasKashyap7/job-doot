"""Read a one-time email verification code from the applicant's Gmail over IMAP, so the
off-site applier can clear company-site "enter the code we emailed you" walls with no human.

Uses a Gmail App Password (gmail_address / gmail_app_password in the profile YAML). Only the
normal INBOX is read; codes Gmail files as Spam are not visible (by design / security).
Spec: enabling autonomous off-site account creation + OTP (2026-11-22)."""
import email
import email.header
import email.utils
import imaplib
import logging
import re
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("applier.otp")

IMAP_HOST = "imap.gmail.com"
_CODE = re.compile(r"(?<![0-9A-Za-z])(\d{4,8})(?![0-9A-Za-z])")       # a standalone 4-8 digit run
_HINT = re.compile(r"\b(code|verif\w*|otp|one[-\s]?time|passcode|confirm\w*|security)\b", re.I)


def _decode(part) -> str:
    try:
        return (part.get_payload(decode=True) or b"").decode(
            part.get_content_charset() or "utf-8", errors="ignore")
    except Exception:
        return ""


def _text(msg) -> str:
    if msg.is_multipart():
        return " ".join(_decode(p) for p in msg.walk()
                        if p.get_content_type() in ("text/plain", "text/html"))
    return _decode(msg)


def _code_from(msg) -> str | None:
    try:
        subject = str(email.header.make_header(email.header.decode_header(msg.get("Subject", ""))))
    except Exception:
        subject = msg.get("Subject", "")
    blob = f"{subject}\n{_text(msg)}"
    if not _HINT.search(blob):
        return None
    text = re.sub(r"<[^>]+>", " ", blob)                             # drop HTML so markup ints don't match
    for m in _CODE.finditer(text):                                   # prefer a code sitting next to a hint word
        if _HINT.search(text[max(0, m.start() - 45): m.end() + 45]):
            return m.group(1)
    m = _CODE.search(text)
    return m.group(1) if m else None


def _poll_once(user: str, pw: str, imap_since: str, after: datetime) -> str | None:
    M = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        M.login(user, pw)
        M.select("INBOX")
        typ, data = M.search(None, "SINCE", imap_since)
        if typ != "OK" or not data or not data[0]:
            return None
        for mid in reversed(data[0].split()[-30:]):                  # newest first, bounded
            typ, md = M.fetch(mid, "(RFC822)")
            if typ != "OK" or not md or not md[0]:
                continue
            msg = email.message_from_bytes(md[0][1])
            try:
                when = email.utils.parsedate_to_datetime(msg.get("Date"))
                if when and when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
            except Exception:
                when = None
            if when and when < after:
                continue
            code = _code_from(msg)
            if code:
                return code
        return None
    finally:
        try:
            M.logout()
        except Exception:
            pass


def fetch_code(cfg: dict, since: float, wait_s: int = 120, poll_s: int = 6) -> str:
    """Return the newest email verification code that arrived (roughly) after `since` (epoch
    seconds). Polls the inbox for up to wait_s because the email lands a few seconds late."""
    user, pw = cfg.get("gmail_address"), cfg.get("gmail_app_password")
    if not user or not pw:
        raise RuntimeError("no gmail_app_password set — cannot read the email verification code")
    after = datetime.fromtimestamp(since, tz=timezone.utc) - timedelta(seconds=45)
    imap_since = (after - timedelta(days=1)).strftime("%d-%b-%Y")     # IMAP SINCE is day-granular
    deadline = time.time() + wait_s
    while True:
        try:
            code = _poll_once(user, pw, imap_since, after)
            if code:
                log.info("otp: read verification code from inbox")
                return code
        except Exception as exc:
            log.warning("otp: inbox read failed: %s", exc)
        if time.time() >= deadline:
            raise RuntimeError(f"no verification code arrived in the inbox within {wait_s}s")
        time.sleep(poll_s)

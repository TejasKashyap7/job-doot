"""Twice-daily LinkedIn account health check — READ-ONLY (opens pages, never clicks or types).
Spec: .claude/specs/apply-agent/approach.md -> "LinkedIn account health check"."""
import logging
from datetime import datetime

from . import notify, safety, store
from .browser import Session
from .human import pause

log = logging.getLogger(__name__)

FEED = "https://www.linkedin.com/feed/"
NOTIFICATIONS = "https://www.linkedin.com/notifications/?filter=all"

_WALL_URLS = ("/checkpoint", "/authwall", "/login", "/uas/", "/signup")
# Strong = the account itself is restricted / challenged / rate-limited -> pause everything.
_STRONG = ("your account has been restricted", "account is restricted", "temporarily restricted",
           "account has been suspended", "unusual activity on your account", "we've noticed unusual",
           "we noticed unusual", "verify your identity", "confirm your identity", "quick security check",
           "security verification", "commercial use limit", "easy apply limit", "reached the daily limit",
           "you've reached the limit", "too many requests")
# Weak = worth knowing, not a reason to stop (e.g. LinkedIn's own security notices).
_WEAK = ("new sign-in", "unrecognized sign-in", "unrecognised sign-in", "password was changed",
         "suspicious", "security alert")

_BANNERS_JS = """() => Array.from(document.querySelectorAll(
  '[role=alert], .artdeco-global-alert, .global-alert, [data-test-global-alert], .artdeco-toast-item'))
  .map(e => e.innerText).join('\\n').slice(0, 4000)"""
_NOTIF_JS = """() => Array.from(document.querySelectorAll(
  'article, .nt-card, [data-urn*="notification"], .notification-card'))
  .slice(0, 40).map(e => e.innerText).join('\\n').slice(0, 12000)"""


def _scan(text: str) -> tuple[list[str], list[str]]:
    low = (text or "").lower()
    strong = [s for s in _STRONG if s in low]
    weak = [w for w in _WEAK if w in low and not any(w in s for s in strong)]
    return strong, weak


def _wall(url: str) -> str | None:
    u = url.lower()
    return next((w for w in _WALL_URLS if w in u), None)


def inspect(page) -> tuple[str, list[str]]:
    """-> (status, signals). status: ok | note | warning."""
    strong, weak = [], []
    for url, js in ((FEED, _BANNERS_JS), (NOTIFICATIONS, _NOTIF_JS)):
        page.goto(url, wait_until="domcontentloaded")
        pause(4, 8)                              # let it render like a person would wait
        if (w := _wall(page.url)):
            return "warning", [f"sent to a LinkedIn {w.strip('/')} page instead of {url.split('/')[3]}"]
        try:
            s, k = _scan(page.evaluate(js))
            strong += s
            weak += k
        except Exception:
            log.warning("could not read %s", url, exc_info=True)
    if strong:
        return "warning", sorted(set(strong))
    if weak:
        return "note", sorted(set(weak))
    return "ok", []


def run_check(cfg) -> str:
    """One check: record it; warning -> pause applying; warning/note -> one Telegram message."""
    conn = store.connect()
    day = datetime.now().strftime("%Y-%m-%d")
    try:
        with Session(cfg) as page:
            status, signals = inspect(page)
    except Exception as exc:
        log.exception("LinkedIn health check failed")
        status, signals = "error", [f"{type(exc).__name__}: {(str(exc).splitlines() or [''])[0][:200]}"]
    store.record_account_check(conn, status, signals, cfg["name"], day)
    log.info("LinkedIn health check: %s %s", status, signals)
    who = cfg["name"]
    if status == "warning":
        safety.pause(f"linkedin:{'; '.join(signals)[:150]}")
        notify.send(cfg, f"\U0001F6D1 LinkedIn warning on {who}'s account: {'; '.join(signals)}.\n"
                         "All applying is paused until you resume it.")
    elif status == "note":
        notify.send(cfg, f"⚠️ LinkedIn notice on {who}'s account: {'; '.join(signals)}. "
                         "Applying continues; watch for more.")
    return status

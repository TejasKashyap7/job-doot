"""Stop signals. Any hit pauses ALL applying until Tejas removes the pause flag."""
from .config import DATA

PAUSE_FLAG = DATA / "PAUSED"

_URL_STOPS = ("/checkpoint", "/authwall", "/login", "/uas/login", "/signup")
_TEXT_STOPS = (
    "unusual activity", "security verification", "quick security check",
    "verify you're a human", "verify you are a human", "account has been restricted",
    "account is restricted", "temporarily restricted", "easy apply limit",
    "reached the daily limit", "you've reached the limit", "too many requests",
)


def check(page) -> str | None:
    url = page.url.lower()
    for s in _URL_STOPS:
        if s in url:
            return f"url:{s}"
    try:
        text = page.inner_text("body", timeout=5000).lower()
    except Exception:
        return None
    for s in _TEXT_STOPS:
        if s in text:
            return f"text:{s}"
    return None


def is_paused() -> str | None:
    return PAUSE_FLAG.read_text().strip() if PAUSE_FLAG.exists() else None


def pause(reason: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    PAUSE_FLAG.write_text(reason + "\n")

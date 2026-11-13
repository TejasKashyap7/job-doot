"""One classifier for every applier problem: the bell and the /needs-you page both use it,
so they always agree. Spec: .claude/specs/notifications/approach.md -> "Problem tags + plain
wording", .claude/specs/dashboard/needs-you.md.

Input is the applier's attempt `detail` ("needs_human:<why> | <url>", "site:<why> | <url>",
"brain:<err>", "offsite_stuck", ...) or, for old notifications, their stored text.
Order: rules on the text/URL -> the "[Label]" Claude put in front of its reason -> "Other".
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Tag:
    key: str
    label: str
    color: str
    means: str   # what this problem is, in very simple words
    next: str    # what happens next (automation first, never "do it by hand")


GREY = "#8a8486"
_MOVED_ON = "Nothing to do — it skipped this job and moved on to the next one."

TAGS = {t.key: t for t in [
    # --- Needs you ---
    Tag("account_wall", "Account / sign-in wall", "#3987e5",
        "The company's own website wants you to log in or make an account before it shows the "
        "application form. The applier isn't allowed to create accounts yet.",
        _MOVED_ON + " Creating accounts (and reading their email codes) gets automated when we "
                    "switch to your real account."),
    Tag("email_code", "Email verification code", "#d95926",
        "The website emailed a code and wants it typed in before it lets the application continue.",
        _MOVED_ON + " Reading these codes from the inbox gets automated together with account "
                    "creation."),
    Tag("captcha", "CAPTCHA", "#199e70",
        "The website showed a “prove you're human” puzzle (a CAPTCHA). The applier never "
        "solves these.",
        _MOVED_ON),
    Tag("profile_mismatch", "Profile doesn't fit", "#c98500",
        "The job or its form demands something the profile doesn't have, such as years of work "
        "experience or a specific degree, so Claude didn't apply.",
        _MOVED_ON),
    Tag("wrong_page", "Wrong page / no form", "#d55181",
        "The applier ended up on the wrong page (another job, a job list, or a page without any "
        "form) and couldn't find this job's application.",
        _MOVED_ON + " If this keeps happening it's an applier bug worth fixing."),
    Tag("duplicate", "Maybe already applied", "#008300",
        "It looked like this job had already been applied to, so it stopped to avoid applying twice.",
        "Nothing to do."),
    Tag("payment", "Payment page", "#9085e9",
        "The website asked for card or payment details. The applier never pays for anything.",
        _MOVED_ON),
    # --- Couldn't apply ---
    Tag("page_stuck", "Page stuck", GREY,
        "The page stopped reacting (often a cookie banner or pop-up was in the way), so after a "
        "few tries the applier gave up on it.",
        _MOVED_ON + " If one website keeps doing this, the applier needs a fix for it."),
    Tag("field_wont_fill", "Form field won't fill", GREY,
        "One box on the form wouldn't keep the answer (for example a date picker that kept "
        "resetting), so the form couldn't be sent.",
        _MOVED_ON + " Repeats on the same website mean the applier needs a fix for that field."),
    Tag("led_away", "Led away from the job", GREY,
        "The Apply button sent the applier to a different website or a general job list instead "
        "of this job's form.",
        _MOVED_ON),
    Tag("claude_login", "Claude logged out", GREY,
        "Claude (the AI that reads the forms) was logged out on the Pi, so nothing could be "
        "filled in.",
        "The widget turns red when this happens; Claude needs logging in again on the Pi. The job "
        "is retried after that."),
    Tag("claude_limit", "Claude usage limit", GREY,
        "Claude's usage limit was reached, so applying paused until the limit resets.",
        "Nothing to do — it continues by itself after the reset."),
    Tag("claude_error", "Claude error", GREY,
        "Claude (the AI that reads the forms) replied with something the applier couldn't use.",
        _MOVED_ON + " The job gets one more try later."),
    Tag("applier_bug", "Applier bug", GREY,
        "The applier program itself crashed on this job — a bug on our side, not the website's.",
        _MOVED_ON + " Worth a fix if it repeats."),
    Tag("old_script", "Old script (retired)", GREY,
        "This came from the old fixed script that clicked without the AI seeing the page. That "
        "script has been replaced.",
        "Nothing to do."),
    Tag("other", "Other", GREY,
        "Something the applier hasn't seen before.",
        _MOVED_ON),
]}

NEEDS_YOU_ORDER = ["account_wall", "email_code", "captcha", "profile_mismatch", "wrong_page",
                   "duplicate", "payment"]

_RETIRED = ("offsite_no_submit_button", "offsite_stuck", "offsite_too_many_pages", "stuck",
            "too_many_steps", "no_primary_button")

_LOGIN = ("failed to authenticate", "oauth session expired", "not logged in", "please run /login",
          "invalid api key")
_LIMIT = ("usage limit", "weekly limit", "hit your", "\"api_error_status\":429", "quota")

# (tag, markers) — first hit wins. Loop / stuck phrases come before the content words because
# the applier writes them itself and its "I was on: <page>" summary can contain anything.
_RULES = [
    ("captcha", ("captcha", "recaptcha", "robot check", "type the text in the image",
                 "prove you're human", "verify you are human")),
    ("email_code", ("verification code", "verify your email", "one-time code", "otp",
                    "code from your inbox", "verification email", "email code")),
    ("payment", ("payment", "card details", "credit card")),
    ("duplicate", ("already been submitted", "already applied", "duplicate application",
                   "apply twice")),
    ("page_stuck", ("round in circles", "stayed exactly the same", "same state", "page stayed")),
    ("old_script", ("a fixed script (not the ai)",)),
    ("applier_bug", ("crashed on this job", "easy apply window didn't open")),
    ("account_wall", ("sign in", "sign-in", "signin", "log in", "log-in", "login", "create an account",
                      "create accounts", "an account", "candidate account", "register and apply",
                      "sign up", "sign-up", "signup", "account-based ats", "passport.amazon.jobs")),
    ("field_wont_fill", ("keeps resetting", "kept resetting", "keep its value", "keep the value",
                         "won't keep", "will not keep", "will not pick", "won't pick",
                         "did not accept", "won't accept", "not accepted", "refused the answers")),
    ("led_away", ("taking me away", "away from the job", "general job-listing", "general job list",
                  "lists other job openings", "outside this application", "separate sap",
                  "sent me to a separate")),
    ("wrong_page", ("different job", "no application form", "job-search box", "search box",
                    "not the application form", "couldn't find an application")),
    ("profile_mismatch", ("years of", "years' experience", "phd", "degree", "no work experience",
                          "doesn't match the profile", "does not match", "don't meet",
                          "relocate", "experience section")),
    ("page_stuck", ("loaded only partly", "could not be clicked", "not responding", "timeout")),
]

_LABEL = re.compile(r"^\s*\[([^\]\n]{2,40})\]\s*")


def _split(detail: str) -> tuple[str, str, str, str | None]:
    """detail -> (code, why, label, url)"""
    detail = (detail or "").strip()
    url = None
    if " | " in detail:
        head, tail = detail.rsplit(" | ", 1)
        if tail.strip().startswith("http"):
            detail, url = head, tail.strip()
    code, sep, why = detail.partition(":")
    if not sep and detail and " " not in detail:
        code, why = detail, ""           # bare code, e.g. "modal_missing"
    elif not sep or " " in code.strip():
        code, why = "", detail           # plain text (old notification), not "code:..."
    label = ""
    m = _LABEL.match(why)
    if m:
        label, why = m.group(1).strip(), why[m.end():]
    return code.strip(), why.strip(), label, url


def classify(detail: str) -> tuple[str, str]:
    """-> (tag key, label). New kinds: the label Claude wrote becomes the tag ("new:<label>")."""
    code, why, label, url = _split(detail)
    low = f"{why} {url or ''}".lower()
    if code == "brain" or "claude exit" in low:
        if any(m in low for m in _LOGIN):
            return "claude_login", TAGS["claude_login"].label
        if any(m in low for m in _LIMIT):
            return "claude_limit", TAGS["claude_limit"].label
        return "claude_error", TAGS["claude_error"].label
    if code == "quota":
        return "claude_limit", TAGS["claude_limit"].label
    if code in ("crash", "modal_missing"):
        return "applier_bug", TAGS["applier_bug"].label
    if code in _RETIRED:
        return "old_script", TAGS["old_script"].label
    if code == "captcha" or low.startswith("captcha"):
        return "captcha", TAGS["captcha"].label
    for key, markers in _RULES:
        if any(m in low for m in markers):
            return key, TAGS[key].label
    if label:
        known = next((t for t in TAGS.values() if t.label.lower() == label.lower()), None)
        if known:
            return known.key, known.label
        return f"new:{label.lower()}", label
    return "other", TAGS["other"].label


def tag_info(key: str, label: str = "") -> Tag:
    if key in TAGS:
        return TAGS[key]
    return Tag(key, label or key.removeprefix("new:").capitalize(), GREY,
               "A kind of problem the applier hasn't seen before; this label is Claude's own "
               "description of it.", _MOVED_ON)


# ---------- wording ----------

_TECH_LINE = re.compile(r"(locator\.|call log|timeout \d+ms|traceback|playwright|_impl\.|"
                        r"exception:|error:|- attempting|waiting for )", re.I)
_TECH_BITS = [
    (re.compile(r"\s*Last things I did:.*$", re.S | re.I), ""),
    (re.compile(r"\s*✓\s*clicked\s*\[\d+\][^.]*", re.I), ""),
    (re.compile(r"\s*\[\d+\]"), ""),
    (re.compile(r"\b(check|click|type|select|key)\s+\d+\b", re.I), ""),
]


def clean_why(why: str, limit: int = 280) -> str:
    """Claude's reason, minus jargon and logs, cut on a sentence boundary."""
    text = why or ""
    for rx, rep in _TECH_BITS:
        text = rx.sub(rep, text)
    lines = [l for l in text.splitlines() if l.strip() and not _TECH_LINE.search(l)]
    text = " ".join(" ".join(lines).split()).replace("Haiku", "Claude")
    text = text.strip(" .;:-") + ("." if text and not text.rstrip().endswith((".", "!", "?")) else "")
    if len(text) > limit:
        cut = text[:limit]
        stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = (cut[:stop + 1] if stop > 80 else cut.rsplit(" ", 1)[0] + "…")
    return text


def plain_reason(detail: str) -> str:
    """What Claude saw, cleaned — empty when the reason is just a code (the tag says it all)."""
    code, why, _label, _url = _split(detail)
    if code in _RETIRED or code in ("crash", "modal_missing", "brain", "quota"):
        return ""
    if why.lower() in ("account / sign-in required", "account-based ats", "no application form found") \
            or why.lower().startswith("captcha"):
        return ""
    return clean_why(why)


def url_of(detail: str) -> str | None:
    return _split(detail)[3]


_SITES = [("myworkdayjobs", "Workday"), ("successfactors", "SAP SuccessFactors"), ("sapsf", "SAP SuccessFactors"),
          ("taleo", "Oracle Taleo"), ("amazon.jobs", "Amazon"), ("careers.microsoft", "Microsoft"),
          ("infosys", "Infosys"), ("icims", "iCIMS"), ("brassring", "Brassring"), ("dayforce", "Dayforce"),
          ("peoplestrong", "PeopleStrong"), ("smartrecruiters", "SmartRecruiters"), ("greenhouse", "Greenhouse"),
          ("lever.co", "Lever"), ("zohorecruit", "Zoho Recruit"), ("applytojob", "JazzHR"), ("darwinbox", "Darwinbox"),
          ("ycombinator", "Y Combinator"), ("linkedin.com", "LinkedIn")]


def site_of(url: str | None) -> str:
    """Hiring system / website behind a job link — for 'how do we automate accounts later'."""
    if not url:
        return "Unknown"
    host = re.sub(r"^https?://", "", url.lower()).split("/")[0]
    for marker, name in _SITES:
        if marker in host:
            return name
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host or "Unknown"

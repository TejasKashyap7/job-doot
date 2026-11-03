"""Naukri batch + LinkedIn drip scraper.

Naukri:  daily batch at 06:00 IST via APScheduler (replaces load_csv).
LinkedIn: background daemon thread, one keyword search every 15–45 min.
Activity: 0–2 PYMK connections (9am–1pm) + 0–2 post likes (6pm–9pm), via APScheduler date jobs.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Job
from services.ingest import ingest_rows
from services.telegram import send as tg_send
import services.alerts as alerts_svc
# NOTE: this module (the scrapers) deliberately does NOT import the scorer/tailor.
# Scraping is a pure producer — the LLM never runs here. See scraper/approach.md.

log = logging.getLogger(__name__)

KEYWORDS = [
    # core AI/ML engineering
    "AI Engineer", "Machine Learning Engineer", "Deep Learning Engineer",
    "Computer Vision Engineer", "LLM Engineer", "GenAI Engineer", "NLP Engineer",
    # research / R&D — the roles Tejas actually targets (rubric filters applied/consulting)
    "AI Research Engineer", "Machine Learning Researcher", "Research Scientist",
    "Applied Scientist", "Deep Learning Research", "LLM Research",
    "Foundation Model", "AI Agent Engineer", "Agentic AI",
]
LOCATIONS = ["Gurgaon", "Delhi", "Noida", "Pune", "Remote"]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

NAUKRI_BASE = "https://www.naukri.com/jobapi/v3/search"
LI_BASE = "https://www.linkedin.com"
LI_VOYAGER = "https://www.linkedin.com/voyager/api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cookies_path() -> Path:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/jobs.db")
    return Path(db_url.split("///")[-1]).parent / "li_cookies.json"


def _job_hash(title: str, company: str, apply_url: str, description: str) -> str:
    """Mirror of ingest.py _hash_job — must stay in sync."""
    return hashlib.sha256(
        f"{title.strip()}|{company.strip()}|{apply_url.strip()}|{description.strip()[:200]}".encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# Section A — Naukri batch scraper
# ---------------------------------------------------------------------------

def _naukri_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "appid": "109",
        "systemcountrycode": "101003",
        "Accept": "application/json",
    })
    return s


def _naukri_search(session: requests.Session, keyword: str, location: str, retries: int = 3) -> list[dict]:
    params = {
        "noOfResults": 20,
        "urlType": "search_by_keyword",
        "searchType": "adv",
        "keyword": keyword,
        "location": location,
        "experienceMin": 0,
        "experienceMax": 3,
    }
    delay = 5
    for attempt in range(retries):
        try:
            resp = session.get(NAUKRI_BASE, params=params, timeout=20)
            if resp.status_code in (429, 503):
                log.warning("Naukri %d for %s/%s — backoff %ds", resp.status_code, keyword, location, delay)
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            if attempt == retries - 1:
                log.error("Naukri search failed for %s/%s: %s", keyword, location, exc)
                return []
            time.sleep(delay)
            delay *= 2
    else:
        return []

    jobs = data.get("jobDetails") or data.get("jobs") or []
    rows = []
    for job in jobs:
        title = (job.get("title") or "").strip()
        company = (job.get("companyName") or "").strip()
        if not title or not company:
            continue
        jd_url = job.get("jdURL") or ""
        if not jd_url:
            log.warning("Naukri: missing jdURL for %s @ %s", title, company)
        apply_url = f"https://www.naukri.com{jd_url}"
        salary = (job.get("salary") or "").strip()
        key_skills = job.get("keySkills") or []
        if isinstance(key_skills, list):
            key_skills = " ".join(key_skills)
        raw_description = f"{job.get('jobDesc') or ''} {key_skills}".strip()
        remote_flag = "remote" in location.lower() or bool(re.search(r"\bremote\b", raw_description, re.I))
        rows.append({
            "title": title,
            "company": company,
            "location": location,
            "salary": salary,
            "apply_url": apply_url,
            "raw_description": raw_description,
            "remote_flag": remote_flag,
            "easy_apply": False,
        })
    return rows


def scrape_naukri(db: Session) -> dict:
    """Fetch all keyword × location combos from Naukri and ingest. Returns {inserted, skipped}."""
    session = _naukri_session()
    all_rows: list[dict] = []
    fetched_count = 0

    for keyword in KEYWORDS:
        for location in LOCATIONS:
            rows = _naukri_search(session, keyword, location)
            fetched_count += len(rows)
            all_rows.extend(rows)
            time.sleep(random.uniform(2, 5))

    log.info("Naukri: fetched %d raw rows across %d combos", fetched_count, len(KEYWORDS) * len(LOCATIONS))

    if fetched_count == 0 and db.query(Job).count() > 0:
        tg_send("⚠️ Naukri returned 0 jobs today — API may have changed. Check Pi logs.")

    return ingest_rows(db, all_rows)


# ---------------------------------------------------------------------------
# Section B — LinkedIn session management
# ---------------------------------------------------------------------------

def _load_li_at() -> str | None:
    path = _cookies_path()
    try:
        data = json.loads(path.read_text())
        return data.get("li_at") or None
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return None


def has_li_at() -> bool:
    """Is a LinkedIn session cookie currently on disk? (value not exposed)"""
    return _load_li_at() is not None


def save_li_at(li_at: str) -> Path:
    """Write the LinkedIn session cookie to the same file the drip loop reads.
    The running loop re-reads it on its next tick, so the scraper resumes on its
    own. Returns the path written."""
    value = (li_at or "").strip()
    if not value:
        raise ValueError("empty li_at value")
    path = _cookies_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"li_at": value}))
    try:
        path.chmod(0o600)  # it's a session secret
    except OSError:
        pass
    return path


def _is_expired(resp: requests.Response) -> bool:
    expired = "linkedin.com/login" in resp.url or resp.status_code == 401
    if expired:
        tg_send(
            "⚠️ LinkedIn cookie expired — scraper paused. "
            "Extract li_at from dummy account and update data/li_cookies.json."
        )
        alerts_svc.set_alert(
            "linkedin_cookie_expired",
            "error",
            "LinkedIn scraper paused — session cookie expired.",
            "Log into the dummy LinkedIn account, extract li_at cookie, paste into data/li_cookies.json.",
        )
    return expired


def _build_linkedin_session() -> requests.Session | None:
    li_at = _load_li_at()
    if not li_at:
        log.error("LinkedIn: li_at cookie not found at %s", _cookies_path())
        alerts_svc.set_alert(
            "linkedin_cookie_expired",
            "error",
            "LinkedIn scraper paused — li_at cookie file missing or invalid.",
            "Create data/li_cookies.json with {\"li_at\": \"<cookie value>\"}.",
        )
        return None

    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "x-restli-protocol-version": "2.0.0",
        "x-li-lang": "en_US",
        "Cookie": f"li_at={li_at}",
    })
    try:
        resp = s.get(LI_BASE + "/", allow_redirects=True, timeout=15)
    except Exception as exc:
        # Network/DNS failure, not a cookie problem — a distinct alert so we don't
        # send the user to re-paste a cookie when the real issue is connectivity.
        log.error("LinkedIn: homepage fetch failed: %s", exc)
        alerts_svc.set_alert(
            "linkedin_network_error",
            "warning",
            f"LinkedIn scraper hit a network error building its session: {exc}",
            "Usually transient (DNS/connectivity on the Pi) — retries automatically. "
            "If this persists for hours, check the Pi's network/DNS.",
        )
        return None

    if _is_expired(resp):
        return None

    alerts_svc.clear_alert("linkedin_network_error")
    jsid = s.cookies.get("JSESSIONID", "")
    s.headers.update({"csrf-token": jsid})
    log.info("LinkedIn session built (JSESSIONID=%s...)", jsid[:8])
    return s


def _refresh_jsessionid(session: requests.Session) -> bool:
    try:
        resp = session.get(LI_BASE + "/", allow_redirects=True, timeout=15)
    except Exception:
        return False
    if "linkedin.com/login" in resp.url:
        return False
    jsid = session.cookies.get("JSESSIONID", "")
    session.headers.update({"csrf-token": jsid})
    return True


# ---------------------------------------------------------------------------
# Section C — LinkedIn job drip
# ---------------------------------------------------------------------------

# LinkedIn drip pacing — ban-safety knobs. Tune conservatively for a brand-new,
# zero-connection dummy account. Widened from the original 15–45 min after real
# traffic looked too fast (2026-07-05).
LI_JOBS_PER_SEARCH = 3                          # job pages fetched per keyword search
LI_FETCH_DELAY_RANGE = (20, 75)                 # sec between job-detail fetches (human clicking)
LI_STARTUP_JITTER_RANGE = (30, 120)             # sec before the very first search after (re)connect
LI_SEARCH_INTERVAL_RANGE = (30 * 60, 90 * 60)   # sec between searches (was 15–45 min)
# Active hours (IST): no overnight/late-night fetching — 24/7 activity is a bot tell
# for a brand-new account. Fetch only between these hours; sleep through the night.
LI_ACTIVE_START_HOUR = 8    # start at 08:00 IST
LI_ACTIVE_END_HOUR = 23     # stop after 23:00 IST
LI_TZ = "Asia/Kolkata"


def _next_sleep() -> float:
    return random.uniform(*LI_SEARCH_INTERVAL_RANGE)


def _seconds_until_active_window() -> float:
    """0 if we're inside active hours (08:00–23:00 IST); otherwise seconds to sleep
    until the next window opens. Keeps the account on a human, diurnal rhythm."""
    now = datetime.now(ZoneInfo(LI_TZ))
    if LI_ACTIVE_START_HOUR <= now.hour < LI_ACTIVE_END_HOUR:
        return 0.0
    target = now.replace(hour=LI_ACTIVE_START_HOUR,
                         minute=random.randint(0, 25), second=0, microsecond=0)
    if now.hour >= LI_ACTIVE_END_HOUR:      # late evening → next morning
        target += timedelta(days=1)
    return max(0.0, (target - now).total_seconds())


def _extract_job_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for m in re.finditer(r"jobPosting:(\d{8,})|/jobs/view/(?:[^\"'?#\s]*?-)?(\d{8,})", text):
        job_url = f"{LI_BASE}/jobs/view/{m.group(1) or m.group(2)}/"
        if job_url not in seen:
            seen.add(job_url)
            urls.append(job_url)
            if len(urls) >= LI_JOBS_PER_SEARCH:
                break
    return urls


def _linkedin_search(session: requests.Session, keyword: str) -> list[str]:
    """Job URLs for one keyword (India, past 24h).

    2026-11: LinkedIn's redesigned search page (/jobs/search-results/) no longer puts
    job ids in the HTML, which silently zeroed this spy from 2026-10-07. The guest
    search endpoint still returns job cards with ids, so it's the primary source; the
    logged-in page regex stays as a fallback.
    """
    q = requests.utils.quote(keyword)
    guest = (f"{LI_BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search"
             f"?keywords={q}&location=India&f_TPR=r86400&start=0")
    try:
        resp = session.get(guest, timeout=20)
        if resp.status_code == 200:
            urls = _extract_job_urls(resp.text)
            if urls:
                return urls
        else:
            log.info("LinkedIn guest search HTTP %s — trying the page", resp.status_code)
    except Exception as exc:
        log.warning("LinkedIn guest search failed: %s — trying the page", exc)

    url = f"{LI_BASE}/jobs/search?keywords={q}&location=India&f_TPR=r86400&count=10"
    try:
        resp = session.get(url, allow_redirects=True, timeout=20)
    except Exception as exc:
        log.warning("LinkedIn search request failed: %s", exc)
        return []
    if "linkedin.com/login" in resp.url:
        _is_expired(resp)
        return []
    return _extract_job_urls(resp.text)


def _linkedin_fetch_job(session: requests.Session, url: str) -> dict | None:
    try:
        resp = session.get(url, allow_redirects=True, timeout=20)
    except Exception as exc:
        log.warning("LinkedIn fetch failed for %s: %s", url, exc)
        return None

    if "linkedin.com/login" in resp.url or resp.status_code == 401:
        _is_expired(resp)
        return None

    # 2026-06: the logged-in /jobs/view/ page is a JS shell with no parseable
    # markup. The jobs-guest API returns a clean HTML fragment instead.
    m = re.search(r"/jobs/view/(\d+)", url)
    if m:
        guest_url = f"{LI_BASE}/jobs-guest/jobs/api/jobPosting/{m.group(1)}"
        try:
            g = session.get(guest_url, timeout=20)
            if g.status_code == 200 and len(g.text) > 1000:
                resp = g
        except Exception as exc:
            log.warning("LinkedIn guest fetch failed for %s: %s — using page response", url, exc)

    soup = BeautifulSoup(resp.text, "lxml")

    title_tag = (
        soup.select_one("h2.top-card-layout__title") or
        soup.select_one("h1.top-card-layout__title") or
        soup.find("h1")
    )
    title = title_tag.get_text(strip=True) if title_tag else ""

    company_tag = (
        soup.select_one("a.topcard__org-name-link") or
        soup.select_one(".topcard__org-name")
    )
    company = company_tag.get_text(strip=True) if company_tag else ""

    if not title or not company:
        return None

    loc_tag = soup.select_one("span.topcard__flavor--bullet")
    location = loc_tag.get_text(strip=True) if loc_tag else ""

    desc_tag = (
        soup.select_one("div.description__text") or
        soup.select_one(".show-more-less-html__markup")
    )
    description = desc_tag.get_text(separator=" ", strip=True) if desc_tag else ""

    remote_flag = bool(re.search(r"\bremote\b", location + " " + description, re.I))

    # Apply type from the guest page (verified 2026-11-03): Easy Apply jobs carry
    # public_jobs_apply-link-onsite, company-site jobs apply-link-offsite.
    if "apply-link-onsite" in resp.text:
        apply_type = "easy"
    elif "apply-link-offsite" in resp.text:
        apply_type = "offsite"
    else:
        apply_type = None

    # Key must be raw_description — drip loop hashes using this key; ingest also resolves it first.
    return {
        "title": title,
        "company": company,
        "location": location,
        "apply_url": url,
        "raw_description": description,
        "remote_flag": remote_flag,
        "salary": "",
        "easy_apply": False,
    }


# ---- Sensor v1 (M10): a spy that keeps returning nothing is "sick" ----
SPY_SICK_AFTER = int(os.getenv("SPY_SICK_AFTER", "3"))
_spy_empty_streak = 0


def _spy_health(keyword: str, links: int, usable: int) -> None:
    """Count consecutive searches that produced no usable job. After SPY_SICK_AFTER in a
    row, raise linkedin_spy_sick (Telegram 🔴 once); the first good search clears it."""
    global _spy_empty_streak
    if usable > 0:
        _spy_empty_streak = 0
        alerts_svc.clear_alert("linkedin_spy_sick")
        return
    _spy_empty_streak += 1
    log.warning("LinkedIn spy: search '%s' gave %d links / 0 usable jobs (%d in a row)",
                keyword, links, _spy_empty_streak)
    if _spy_empty_streak >= SPY_SICK_AFTER:
        where = "search found no job links" if links == 0 else "job pages could not be read"
        alerts_svc.set_alert(
            "linkedin_spy_sick", "error",
            f"LinkedIn spy is sick: {_spy_empty_streak} searches in a row produced 0 jobs ({where}).",
            "LinkedIn probably changed its pages. Needs a repair — open Claude Code on the job-doot repo.",
        )


def linkedin_drip_loop(db_factory) -> None:
    """Runs forever as a daemon thread. Fetches one LinkedIn keyword every 15–45 min."""
    while True:  # OUTER: restart on any crash
        try:
            session = _build_linkedin_session()
            if not session:
                # Was 1h — too slow for the network/DNS blips this most often turns
                # out to be (see .claude/specs, recurring "why no data" incidents).
                # A real cookie-expiry keeps re-alerting every 5 min instead of going
                # silent for an hour at a time.
                log.info("LinkedIn drip: no session — retrying in 5 min")
                time.sleep(300)
                continue

            alerts_svc.clear_alert("linkedin_drip_crashed")

            # Startup jitter — don't fire the instant the cookie loads (bot tell).
            jitter = random.uniform(*LI_STARTUP_JITTER_RANGE)
            log.info("LinkedIn drip: startup jitter %.0fs before first search", jitter)
            time.sleep(jitter)

            kw_queue: list[str] = []

            while True:  # INNER: normal operation
                # No overnight fetching — sleep through the night, resume in the morning.
                off = _seconds_until_active_window()
                if off > 0:
                    log.info("LinkedIn drip: outside active hours — sleeping %.1fh until morning", off / 3600)
                    time.sleep(off)
                    continue

                if not kw_queue:
                    kw_queue = random.sample(KEYWORDS, len(KEYWORDS))

                keyword = kw_queue.pop()
                log.info("LinkedIn drip: searching '%s'", keyword)
                urls = _linkedin_search(session, keyword)
                log.info("LinkedIn drip: '%s' -> %d job links", keyword, len(urls))
                usable = 0

                for i, url in enumerate(urls):
                    # Human-like pause between opening job listings (turns the
                    # per-search burst into paced clicking). Skip before the first.
                    if i > 0:
                        pause = random.uniform(*LI_FETCH_DELAY_RANGE)
                        log.info("LinkedIn drip: %.0fs pause before next job", pause)
                        time.sleep(pause)

                    job_dict = _linkedin_fetch_job(session, url)
                    if not job_dict:
                        continue
                    usable += 1

                    alerts_svc.clear_alert("linkedin_cookie_expired")

                    # PRODUCER: ingest only. No LLM here — scoring/tailoring is the
                    # consumer's job (scheduler.score_and_tailor_job), so a Groq outage
                    # can never slow or stop collection. Jobs wait as 'scraped'.
                    db = db_factory()
                    try:
                        result = ingest_rows(db, [job_dict])
                        if result["inserted"] > 0:
                            log.info("LinkedIn drip: ingested '%s' @ %s (awaiting scoring)",
                                     job_dict.get("title", ""), job_dict.get("company", ""))
                    except Exception:
                        log.exception("Drip: ingest failed for %s", url)
                    finally:
                        db.close()

                _spy_health(keyword, len(urls), usable)

                sleep_sec = _next_sleep()
                log.info("LinkedIn drip: sleeping %.0f min before next search", sleep_sec / 60)
                time.sleep(sleep_sec)

        except Exception as exc:
            log.exception("LinkedIn drip crashed — restarting in 5 min")
            alerts_svc.set_alert(
                "linkedin_drip_crashed",
                "error",
                f"LinkedIn drip thread crashed: {exc}",
                "Restarts automatically every 5 min. If this keeps recurring, check the logs.",
            )
            time.sleep(300)


# ---------------------------------------------------------------------------
# Section D — LinkedIn activity simulation
# ---------------------------------------------------------------------------

def _get_pymk(session: requests.Session) -> list[str]:
    try:
        resp = session.get(f"{LI_VOYAGER}/growth/pymk?count=10", timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("PYMK fetch failed: %s", exc)
        return []

    blocked = {"founder", "cto", "ceo", "vp", "chief", "director", "head of"}
    profile_ids = []
    for item in data.get("elements") or []:
        headline = (item.get("headline") or "").lower()
        if any(b in headline for b in blocked):
            continue
        pid = item.get("profileId") or item.get("miniProfile", {}).get("entityUrn", "")
        if pid:
            profile_ids.append(pid)
    return profile_ids


def _send_connection(session: requests.Session, profile_id: str) -> bool:
    body = {
        "invitee": {
            "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                "profileId": profile_id
            }
        }
    }
    try:
        resp = session.post(f"{LI_VOYAGER}/growth/normInvitations", json=body, timeout=15)
        return resp.status_code == 201
    except Exception as exc:
        log.warning("Connection send failed: %s", exc)
        return False


def _get_feed_posts(session: requests.Session) -> list[str]:
    try:
        resp = session.get(f"{LI_VOYAGER}/feed/updates?count=10&start=0", timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("Feed fetch failed: %s", exc)
        return []

    urns = []
    for item in data.get("elements") or []:
        urn = item.get("entityUrn") or ""
        if urn.startswith("urn:li:activity:"):
            urns.append(urn)
    return urns


def _like_post(session: requests.Session, entity_urn: str) -> bool:
    try:
        resp = session.post(
            f"{LI_VOYAGER}/reactions",
            json={"reactionType": "LIKE", "entityUrn": entity_urn},
            timeout=15,
        )
        return resp.status_code in (200, 201)
    except Exception as exc:
        log.warning("Like failed: %s", exc)
        return False


def do_connections() -> None:
    """APScheduler date job: send 0–2 PYMK connection requests."""
    n = random.randint(0, 2)
    if n == 0:
        return
    session = _build_linkedin_session()
    if not session:
        return
    profiles = _get_pymk(session)
    picks = random.sample(profiles, min(n, len(profiles)))
    for pid in picks:
        ok = _send_connection(session, pid)
        log.info("Connection to %s: %s", pid, "sent" if ok else "failed")
        time.sleep(random.uniform(30, 60))


def do_likes() -> None:
    """APScheduler date job: like 0–2 feed posts."""
    n = random.randint(0, 2)
    if n == 0:
        return
    session = _build_linkedin_session()
    if not session:
        return
    posts = _get_feed_posts(session)
    picks = random.sample(posts, min(n, len(posts)))
    for urn in picks:
        ok = _like_post(session, urn)
        log.info("Like %s: %s", urn, "sent" if ok else "failed")
        time.sleep(random.uniform(20, 40))


def schedule_daily_activity(sched, tz: str) -> None:
    """Schedule today's connection + like jobs at random times within their windows."""
    from apscheduler.triggers.date import DateTrigger  # local import — avoids circular at module level

    tz_obj = ZoneInfo(tz)
    now = datetime.now(tz=tz_obj)
    today = now.date()

    # Connections: 09:00–13:59 IST (spec: 9am–1pm)
    conn_h, conn_m = random.randint(9, 13), random.randint(0, 59)
    conn_time = datetime(today.year, today.month, today.day, conn_h, conn_m, tzinfo=tz_obj)
    if conn_time > now:
        sched.add_job(
            do_connections, trigger="date", run_date=conn_time,
            id=f"connections_{today}", replace_existing=True,
        )
        log.info("Connections scheduled for %02d:%02d IST", conn_h, conn_m)

    # Likes: 18:00–21:59 IST (spec: 6pm–9pm)
    like_h, like_m = random.randint(18, 21), random.randint(0, 59)
    like_time = datetime(today.year, today.month, today.day, like_h, like_m, tzinfo=tz_obj)
    if like_time > now:
        sched.add_job(
            do_likes, trigger="date", run_date=like_time,
            id=f"likes_{today}", replace_existing=True,
        )
        log.info("Likes scheduled for %02d:%02d IST", like_h, like_m)

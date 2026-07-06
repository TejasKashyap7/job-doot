# Scraper — Approach

## Status
BUILT & LIVE — LinkedIn drip active (paced + active-hours, see FLAW-7); Naukri walled
by recaptcha (see FLAW-5/probe). 2026-07-06: **scraping decoupled from the LLM.**

## Producer/consumer decoupling (2026-07-06) — scraping NEVER depends on the LLM
Previously the scrapers were coupled to Groq: the LinkedIn drip scored + tailored each
job *inline*. When the Groq free tier rate-limited, every new job triggered a ~2-min
retry storm before the loop could advance — so throughput collapsed, AND
collected-but-unscored jobs sat at status `scraped` (hidden from the dashboard). That
was the "far fewer than ~24/day" symptom.

Fixed by splitting producers from a single consumer:
- **Producers (NO LLM — run full-speed regardless of Groq):**
  - **LinkedIn drip** — scrape + `ingest_rows` only → jobs land as `scraped`.
  - **Naukri daily 06:00 batch** — `scrape_naukri` only → jobs land as `scraped`.
- **Consumer — `score_and_tailor_job` on a ~20-min interval (APScheduler):** drains the
  `scraped` queue → `score_pending(limit)` then `tailor_pending` (auto-tailor only ≥9).
  Groq-gated: after repeated Groq failures it stops the batch and retries next tick.
- **Result:** a Groq outage can only *delay scoring*, never *reduce jobs collected*.
  Jobs wait as `scraped` (collected + counted). The dashboard shows an
  **"awaiting scoring"** count so collected-unscored jobs are never invisible.
- `services/scraper.py` no longer imports the scorer/tailor — the decoupling is real.

**Future — Naukri moves batch → drip once it's a logged-in source.** Naukri is a
batch today only because the (now-walled) access was the *anonymous* API — no account
to protect. Once the member-cookie trick works (a logged-in dummy Naukri account, like
Hugh Janus for LinkedIn), Naukri inherits the same ban risk and should run as a
**human-paced drip**, exactly like LinkedIn. Under producer/consumer that's just another
producer filling the `scraped` queue — the consumer is unchanged. (Parked to the Naukri
member-cookie test; see [[project-data-sources]].)

## What we're building
A daily keyword-based job scraper that pulls listings from Naukri.com and LinkedIn
without requiring any account login. Output feeds directly into the existing ingest
pipeline as a CSV — no pipeline changes needed.

## Core idea
- User defines a keyword list and location list in config/env
- Scraper runs at 06:00 IST daily (same APScheduler job that already exists)
- Hits each platform's public search for each keyword × location combo
- Normalises results into the exact CSV schema the ingest service already reads
- Writes/overwrites `jobs.csv` at `JOBS_CSV_PATH`
- Existing pipeline: ingest → score → tailor picks it up automatically

## Target platforms

### Naukri.com
- Has an undocumented but stable internal JSON API used by their own frontend
- Endpoint: `https://www.naukri.com/jobapi/v3/search?noOfResults=20&urlType=search_by_keyword&searchType=adv&keyword=<kw>&location=<loc>&experienceMin=0&experienceMax=3`
- Returns structured JSON: title, company, location, salary, JD snippet, apply URL
- No login required, no CAPTCHA on API tier (only on HTML tier)
- Friend's Selenium script was also targeting Naukri — may be reusable as reference

### LinkedIn
- Authenticated via dummy account `li_at` session cookie stored in `data/li_cookies.json`
- No Selenium, no headless browser — plain `requests.Session` with cookie header
- Cookie valid for 1–2 weeks. On expiry the scraper detects a redirect to login,
  sends an alert, and pauses LinkedIn scraping until cookie is refreshed manually
- Full JD available via `https://www.linkedin.com/jobs/view/{job_id}` (returns full
  page HTML; BeautifulSoup extracts the description div)
- **Drip mode — NOT batch:** scrapes one listing at a time throughout the day with
  random waits. See "LinkedIn scraping pattern" section below.

## Two separate scraping modes

### Naukri — daily batch at 06:00 IST
Runs as part of the existing `daily_scrape_job` in `scheduler.py`.
Fetches all keyword × location combos in one go, ingests, scores, tailors.
Naukri's API is stable and low-risk so batch is fine.

### LinkedIn — continuous drip throughout the day
Runs as a separate long-running background thread started at app startup.
Picks one job URL at a time from a rotating queue, fetches the full JD,
ingests immediately, then sleeps a random duration before the next fetch.
This keeps daily volume to ~24 jobs while looking completely human.

## LinkedIn scraping pattern

```python
import random

def _next_sleep() -> float:
    # Uniform 15–45 min — simple, avg ~30 min, no detectable rhythm
    return random.uniform(15 * 60, 45 * 60)
```

Average interval ≈ 30 min → ~48 LinkedIn searches/day.
Uniform distribution — no predictable cadence for LinkedIn's anomaly detection.

## LinkedIn job queue

**Implemented as keyword-only (no location combos).** LinkedIn's job search
with `location=India` already returns India-wide results, so adding 5 location
variants per keyword would produce 5× API calls for the same listings. The
queue rotates through all 9 keywords in random order, reshuffles when exhausted.

```
startup: build randomly-shuffled copy of KEYWORDS list
        ↓
loop forever:
    pop one keyword from queue (reshuffle when empty)
    GET /jobs/search?keywords=<kw>&location=India&f_TPR=r86400
    extract up to 5 job listing URLs from results HTML
    for each listing URL:
        fetch full job page → parse title, company, JD, apply_url
        ingest immediately (status `scraped`) — NO LLM here
    sleep _next_sleep() seconds
    # scoring + tailoring are handled separately by the consumer (score_and_tailor_job)
```

## Data flow (combined)

```
PRODUCERS (no LLM — fill the queue):
    06:00 IST daily:   Naukri batch → ingest (status `scraped`)
    Continuous drip:   one LinkedIn listing → ingest (status `scraped`)

CONSUMER (Groq-gated — drains the queue, every ~20 min):
    score_and_tailor_job → score_pending(limit) → tailor_pending (auto-tailor ≥9 only)
```

Producers never call the LLM, so a Groq outage cannot slow or stop collection —
it can only delay scoring. Jobs wait as `scraped` (collected + counted).

## CSV schema (must match existing ingest)
```
title, company, location, salary, remote_flag, easy_apply, apply_url, raw_description
```
`source_hash` is computed by `ingest.py` from (title + company + apply_url hash) — scraper does not need to set it.

## Keywords (initial set, configurable via env/config)
```
AI Engineer, ML Engineer, Machine Learning Engineer, Deep Learning Engineer,
Computer Vision Engineer, GenAI Engineer, LLM Engineer, NLP Engineer,
AI Research Engineer
```

## Locations (initial set)
```
Gurgaon, Delhi, Noida, Pune, Remote
```

## LinkedIn session bootstrap (JSESSIONID auto-fetch)

LinkedIn's Voyager API (used for activity simulation) requires two cookies:
- `li_at` — authentication, stored in `data/li_cookies.json`, refreshed manually every 1-2 weeks
- `JSESSIONID` — CSRF token for write operations, fetched automatically on startup

On scraper startup, hit LinkedIn's homepage with `li_at` to get a fresh session:
```python
resp = session.get("https://www.linkedin.com/", timeout=15)
# JSESSIONID is now in session.cookies — used as csrf-token header for all POST requests
session.headers.update({"csrf-token": session.cookies.get("JSESSIONID", "")})
```

If the homepage returns a redirect to `/login`, `li_at` has expired — fall through to
the cookie expiry detection and alert flow below. JSESSIONID is refreshed automatically
on any 401/403 response from the Voyager API during the run.

## LinkedIn daily activity simulation

To make the dummy account look human, two low-volume social actions run daily.
Both are independent — they use separate APScheduler `date` jobs scheduled at
random times within their respective windows. Triggered at midnight each day
to pick a random time for the next day's action.

### Connection requests — 9am to 1pm IST
```
n = randint(0, 2)  # 0 means skip today entirely
time = random time between 09:00 and 13:00 IST
```
Targets: "People You May Know" recommendations from LinkedIn's PYMK feed.
Filters out: founders, CTOs, VPs (title contains "Founder"/"CTO"/"VP"/"Chief").
Picks from mid-level profiles — engineers, analysts, PMs. Looks like a junior person
networking, not a bot farming connections.

Voyager endpoint: `GET /voyager/api/growth/pymk?count=10` → pick n random profiles →
`POST /voyager/api/growth/normInvitations` per profile.

### Post likes — 6pm to 9pm IST
```
n = randint(0, 2)  # 0 means skip today entirely
time = random time between 18:00 and 21:00 IST
```
Likes n posts from the account's feed. Picks randomly from feed items — no targeting,
just engagement. Looks like someone scrolling LinkedIn after work.

Voyager endpoint: `GET /voyager/api/feed/updates?count=10` → pick n random posts →
`POST /voyager/api/reactions` per post with `reactionType: LIKE`.

## LinkedIn cookie expiry detection and alerting

When the li_at cookie expires, LinkedIn redirects any request to `https://www.linkedin.com/login`.
The scraper detects this by checking the final URL of the response (or a redirect to `/login`).

**Detection:**
```python
resp = session.get(url, allow_redirects=True, timeout=15)
if "linkedin.com/login" in resp.url or resp.status_code == 401:
    # cookie expired
    from services.alerts import set_alert
    set_alert(
        "linkedin_cookie_expired",
        "error",
        "LinkedIn scraper paused — session cookie expired.",
        "Extract li_at cookie from dummy account browser session, paste into data/li_cookies.json to resume.",
    )
    log.error("LinkedIn cookie expired — scraper paused")
    return  # stop the current drip loop iteration; scheduler will retry next cycle
```

**Recovery:**
When the scraper successfully fetches a listing (HTTP 200, no login redirect), it clears the alert:
```python
from services.alerts import clear_alert
clear_alert("linkedin_cookie_expired")
```

**Dashboard visibility:**
A sticky red pulsing banner appears at the top of every dashboard page when this alert is active.
The banner shows the message + exact fix instructions. Stays until the scraper clears it.

## Where the code lives
`backend/services/scraper.py` — imported by scheduler.py to replace the `load_csv` call with a `scrape_and_ingest` call. The CSV write is an intermediate step so the existing ingest path is unchanged.

## Rate limiting strategy
- 2s delay between each API call
- Randomised user-agent rotation (small pool of real browser UAs)
- Max 3 retries with exponential backoff on 429/503
- Full run expected to take ~3-4 min for 9 keywords × 6 locations = 54 combos × 2 platforms

## Open flaws
See flaws.md — resolve these before writing any code.

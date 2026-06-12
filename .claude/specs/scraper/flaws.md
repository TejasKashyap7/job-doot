# Scraper — Flaws

---

## FLAW-1: LinkedIn full job description is not accessible without login
**Status: RESOLVED — dummy account + li_at cookie approach**

**Decision:**
Use a dummy LinkedIn account (no real details, created purely for scraping).
Log in once manually, extract the `li_at` session cookie, store it in
`data/li_cookies.json`. Scraper uses this cookie for all LinkedIn requests as
plain HTTP calls — no Selenium, no headless browser.

**Why this works:**
LinkedIn's auth is cookie-based. With a valid `li_at` cookie you get full JDs
via plain `requests.get()` calls, identical to what your browser sends. No
fingerprinting possible because there is no browser — just HTTP.

**Cookie refresh:**
LinkedIn sessions last 1–2 weeks. When expired, the scraper gets a redirect to
the login page, detects it, and sends an alert ("LinkedIn session expired — refresh
li_at cookie"). You log into the dummy account on your phone, extract the cookie
with a browser extension (30 seconds), update `data/li_cookies.json`. Done.

**Dummy account protects you:**
If LinkedIn bans the account → create a new one. Real account never touched.
Reading public job listings is very low-risk behaviour for an account vs Easy Apply.

---

## FLAW-2: LinkedIn blocks headless browsers aggressively
**Status: RESOLVED — resolved together with FLAW-1**

No headless browser is used. Scraper sends plain HTTP requests with the `li_at`
cookie from the dummy account. Plain requests are indistinguishable from a real
user's browser traffic at the HTTP level. No fingerprinting surface exists.

---

## FLAW-3: Keyword × location combos produce duplicate jobs across searches
**Status: RESOLVED — accepted, dedup handles correctness**

**The problem:**
"AI Engineer" in "Delhi" and "AI Engineer" in "Gurgaon" will often return the same
remote-first job that is listed for the entire NCR region. We make 2 API calls and
get the same row twice. source_hash dedup in ingest.py prevents double-insertion,
but the wasted API calls add up (45 combos × 2 platforms = 90 calls for potentially
30 unique jobs).

**Example:**
A Noida company posts "AI Engineer — Remote OK" on Naukri. It shows up in the
Noida search, the Delhi search, and the Gurgaon search. We make 3 Naukri API calls
and get 3 identical rows, but only 1 gets inserted. 2 calls wasted every day for
every such listing.

**Options:**
- **Option A — Accept it.** source_hash dedup already handles correctness. The wasted
  calls are ~10-15s of extra runtime per day. Not worth engineering around now.
- **Option B — Deduplicate in-memory before writing the CSV.** Collect all results first,
  deduplicate by (title + company + apply_url) hash before writing. Reduces API
  calls next run but doesn't help during the current run.
- **Option C — Search by keyword only (no location filter), then filter results by
  location string in the response.** Naukri API supports this. One call per keyword
  instead of per keyword × location. Reduces total calls from 45 to 9.

---

## FLAW-4: No freshness filter — same stale jobs re-fetched daily
**Status: RESOLVED — accepted, dedup is the safety net**

**The problem:**
Without a "posted in last 24h" filter, the scraper pulls the same listings every day.
source_hash dedup prevents re-insertion, but we're still making 90 API calls daily
for jobs we've already seen. Worse, fresh jobs from yesterday are buried under
2-week-old listings in the API response.

**Example:**
A hot "GenAI Engineer" role posted today is on page 3 of Naukri results (sorted by
relevance, not date). Our scraper only fetches page 1. The role never gets scraped.
Meanwhile we process 90 calls worth of 2-week-old listings we already have.

**Options:**
- **Option A — Add `freshness=1` param to Naukri API calls** (Naukri supports "last
  1 day" filter). LinkedIn guest endpoint supports `f_TPR=r86400` (posted in last
  24h). This cuts response size and surfaces genuinely new listings.
- **Option B — Track the latest `apply_url` / listing IDs seen and stop paginating
  once we hit one we already know.** Avoids re-fetching without API-level filtering.
- **Option C — Accept it.** source_hash dedup is the safety net. Optimize later once
  the scraper is proven working.

---

## FLAW-5: Friend's script is not deliverable — need to build our own
**Status: RESOLVED — decision made: build from scratch**

Friend is unable to deliver. We are building our own scraper.
The Naukri JSON API approach does not depend on any Selenium script.
Reference friend's script only if we ever need to fall back to HTML scraping.

**Decision:** Build our own scraper using Naukri JSON API + Indeed public search +
optionally LinkedIn guest API. See approach.md for full platform breakdown.

---

## FLAW-6: Pi IP can get blocked by Naukri/LinkedIn
**Status: LARGELY RESOLVED — dynamic IP + dummy account together reduce risk to near zero**

**Original concern:** Fixed Pi IP gets rate-limited and banned after repeated daily scrapes.

**Why it's mostly resolved:**
- Pi is on a home network with **no static IP** — the ISP rotates the IP every 24h or
  on each router restart. Even if Naukri rate-limits the current IP, the next day it's
  a different one. There is no persistent target for them to ban.
- Scraping will use a **dummy LinkedIn account** (no real details) for any
  account-authenticated requests. If the dummy account gets flagged or banned,
  create a new one. Real LinkedIn account is never touched by the scraper.

**What remains:**
The only surviving risk is a zero-result day going unnoticed. Mitigate with a single
alert: if the scraper returns 0 jobs on a day when it previously returned >0, send
a push notification immediately.

**Remaining action (OPEN):** Add a zero-result alert to the scraper once it's built.
This is a 10-line addition and should be done before Pi deployment.

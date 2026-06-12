# Ingest — Flaws

---

## FLAW-1: Two jobs with the same title, company, and no apply_url hash to the same value
**Status: RESOLVED — `description[:200]` included in hash (`_hash_job` in ingest.py:12)**

**The problem:**
`source_hash = SHA256(f"{title}|{company}|{apply_url}")`. If `apply_url` is empty
(scraper couldn't find one, or the job board doesn't provide it), it becomes an empty
string. Two DIFFERENT job listings from the same company with the same title but
genuinely different roles (e.g., two "AI Engineer" openings at the same startup for
different teams) will produce identical hashes. Only the first one gets inserted.
The second is silently dropped.

**Example:**
Naukri shows "Sarvam AI" posting two "AI Engineer" roles — one for the speech team,
one for the NLP team. Neither listing has an apply_url on the search results page.
Hash for both = `SHA256("AI Engineer|Sarvam AI|")`. First one inserts fine. Second
is detected as a duplicate and skipped. You never see the second role. You miss a
job without knowing it existed.

**Options:**
- **Option A — Include `raw_description` in the hash.** Two different roles will
  almost always have different JD text. Hash becomes `SHA256(title|company|apply_url|description[:500])`.
  Near-zero false collision rate. Small risk: if scraper updates a JD slightly
  (e.g., typo fix), it re-ingests as a new job. Acceptable tradeoff.
- **Option B — Include a `source_url` field** (the URL of the search result page,
  not the apply URL). Each listing has a unique source page URL even without an
  apply deep link. Most scrapers can provide this easily.
- **Option C — Accept it.** Same-title, same-company, no-URL collisions are rare
  enough that it's not worth engineering around. If it ever causes a missed job,
  it'll be re-scraped the next day anyway (source_hash collision means it just
  looks like a duplicate forever).

---

## FLAW-2: CSV column must be named "description" — wrong name = silent empty JD
**Status: RESOLVED — `ingest_rows()` checks 4 aliases: description / job_description / jd / raw_description (ingest.py:33)**

**The problem:**
`ingest_rows()` reads `row.get("description")` to populate `raw_description`.
If the scraper outputs the column with any other name — `job_description`, `jd`,
`desc`, `raw_description`, `details` — `row.get("description")` returns None,
which is stripped to `""` and stored as an empty string. The scorer then runs
with `"(no description provided)"` as input and produces a low-confidence score.
The tailor loop tries to tailor a resume against an empty JD. Everything runs but
produces garbage.

**Example:**
You build the Naukri scraper and the Naukri API response field is called
`jobDescription`. You write it to CSV as `job_description`. Ingest runs fine —
no errors, 70 jobs inserted. But every job has `raw_description=""`. Scorer gives
them all score 3–4 ("borderline, can't tell without JD"). Tailor loop produces
generic resumes. You spend an hour debugging before realising the column name mismatch.

**Options:**
- **Option A — Accept multiple column name aliases in ingest_rows().**
  `description = row.get("description") or row.get("job_description") or row.get("jd") or ""`
  Covers the most common names the scraper might produce.
- **Option B — Validate at ingest time.** If the first row has no `description` field
  at all, log a loud WARNING: "No 'description' column found — jobs will have empty JDs."
  Doesn't fix it but makes it immediately obvious.
- **Option C — Rename the expected column to match whatever the scraper naturally produces**
  and document it in the scraper spec. Single source of truth for the CSV schema.

---

## FLAW-3: Remote flag detection is too naive — location substrings can false-positive
**Status: RESOLVED — using `re.search(r"\bremote\b", loc, re.IGNORECASE)` word-boundary match (ingest.py:44)**

**The problem:**
`remote = "remote" in loc.lower()` — any location string containing the word "remote"
sets `remote_flag=True`. This works for "Remote", "Remote (India)", "Delhi / Remote".
But it also fires for unintended cases like "Remote Sensing Institute, Dehradun" or
a Naukri location field that says "Immediate Joiner / Remote Preferred" where the
job is actually office-based but prefers remote-ready candidates.

**Example:**
Naukri API returns location = `"Remote Sensing Lab, IIT Delhi"` for a hardware
research role. `remote_flag` is set to True. The insights page's remote/on-site
breakdown shows this as a remote role. You filter for remote jobs and this one
appears. Minor, but adds noise to the insights charts.

**Options:**
- **Option A — Check for "remote" as a word boundary, not substring.**
  Use `re.search(r'\bremote\b', loc, re.IGNORECASE)` instead of `in loc.lower()`.
  "Remote Sensing" has "Remote" at word boundary too so this doesn't fully fix it.
- **Option B — Match against specific known patterns** like `"^remote"`, `"/ remote"`,
  `"remote ok"`, `"work from home"` via a small regex list.
- **Option C — Accept it.** Remote Sensing Institute false positives are vanishingly
  rare for AI/ML job searches. The heuristic is good enough.

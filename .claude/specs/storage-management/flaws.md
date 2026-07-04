# Storage Management — Flaws

---

## FLAW-1: Pi SD card write wear — SQLite WAL hammers the card daily
**Status: RESOLVED — Tejas pivoted the Pi to an NVMe SSD (exactly Option A/B below),
for this very reason. Write-wear is no longer a concern. Off-site data backup is now
tracked separately as Flaw 7 in the master flaw.md.**

**The problem:**
SQLite in WAL mode writes to a WAL file first, then checkpoints (flushes) to the main
DB file. The daily 06:00 scrape + score + tailor run writes thousands of rows in a
short burst, which checkpoints a large WAL to the main DB. SD cards have a limited
number of write cycles (typically 10,000–100,000 P/E cycles for cheap cards).
Heavy daily writes shorten card lifespan. A dead SD card = lost DB, lost PDFs,
lost application history.

**Example:**
The pipeline runs for 18 months. The SD card silently develops bad sectors from
write wear. One morning the daily scrape causes a write that hits a bad block.
SQLite DB gets corrupted. You lose all your job history, all your tailored resumes,
all your applied job records. No backup existed.

**Options:**
- **Option A — Move the DB and PDFs to a USB SSD.** A 256GB USB SSD (~₹800) has
  100x the write endurance of an SD card and is plug-and-play on Pi. Mount it at
  `/mnt/ssd`, point `DATABASE_URL` and `PDFS_DIR` there. SD card only runs the OS.
  Best long-term solution.
- **Option B — Pi 5 NVMe HAT.** If you have or plan to buy the official Pi 5 NVMe
  HAT, move everything there. Fastest option, cleanest setup. But costs more.
- **Option C — Keep SD card but add automated DB backup.** Weekly `sqlite3 jobs.db
  .dump > backup.sql` to a separate location (USB drive, another machine, Google
  Drive). If SD card dies, restore from backup. Doesn't prevent wear but prevents
  data loss.

**Recommendation:** Option A (USB SSD) is the cheapest and most practical fix.
Option C should be done regardless as a safety net.

**Resolution (2026-07-03):** Tejas moved the whole Pi to an NVMe SSD — the write-wear
half of this flaw is gone. He also fitted the official Pi 5 power supply for stable
power given the multiple devices attached. The remaining "no backup" half is handled
by Flaw 7 in the master flaw.md: a monthly snapshot of the jobs DATABASE (not the
PDFs, which are regenerable) to a private GitHub repo.

---

## FLAW-2: Cleanup job deleting a PDF you still wanted
**Status: OPEN — low priority but annoying if it happens**

**The problem:**
The cleanup job deletes PDFs for non-applied jobs older than 90 days. But what if
you scored a job 7.5, got a tailored PDF, decided not to apply immediately, and 91
days later want to apply? The PDF is gone. You'd have to re-run the tailor loop to
regenerate it — which costs Groq tokens and takes a few minutes.

**Example:**
You scrape a "GenAI Engineer at Sarvam AI" role in June. Score 8.2, great resume
generated. You postpone applying because you want to finish another application first.
3 months later (September) you go back to it. Cleanup deleted the PDF on day 91.
You have to re-tailor the resume.

**Options:**
- **Option A — Add a `pinned` boolean flag to the Job model.** From the dashboard,
  you can pin any job to exempt it from cleanup. Pinned jobs and their PDFs are
  never deleted regardless of age.
- **Option B — Extend the PDF retention to 180 days** (6 months) instead of 90.
  Doubles the storage cost of PDFs but still manageable (~2.2GB/year instead of
  ~1.1GB). Simple, no UI change needed.
- **Option C — Don't delete PDFs at all, only delete DB rows.** PDFs are flat files
  on disk; even 2 years of them is ~2.2GB which is fine. Delete DB rows on schedule
  but leave PDFs indefinitely. Add a separate manual "clear old PDFs" admin button
  for when you actually care about space.

---

## FLAW-3: No alert if cleanup job fails silently
**Status: OPEN — low priority**

**The problem:**
If the weekly cleanup job crashes (DB locked, disk full, uncaught exception), it
fails silently. The scheduler logs the error but nothing notifies you. Over months
of failed cleanups the DB grows unbounded.

**Example:**
A disk-full error causes the cleanup to fail on week 3. It keeps failing every week
after that because there is no space to write the WAL checkpoint. Logs fill up, DB
gets corrupted. You find out when the dashboard stops loading.

**Options:**
- **Option A — Write a `last_cleanup_ok` timestamp to a config table after each
  successful run.** The dashboard storage stats endpoint checks it and flags if
  last successful cleanup was more than 10 days ago.
- **Option B — Send a push notification on cleanup failure** (same Telegram bot
  used for job alerts). "Weekly cleanup failed — check Pi logs."
- **Option C — Both A and B.** One-time setup, maximum visibility.

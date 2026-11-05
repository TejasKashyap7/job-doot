"""Entry point.

  python -m applier.run once   --profile vishal [--max 2]   # one slot right now
  python -m applier.run daemon --profile vishal              # random slots every day
  python -m applier.run status --profile vishal
  python -m applier.run qa     --profile vishal              # list unanswered questions
  python -m applier.run answer --profile vishal ID "text"    # answer one
  python -m applier.run resume                               # clear the pause flag
  python -m applier.run look   --profile vishal --url URL    # Haiku's plan for a page, no actions
  python -m applier.run try    --profile vishal --job ID     # apply to one job now (ignores pause)
"""
import argparse
import logging
import random
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from . import backend, notify, safety, store
from .browser import Session
from .config import DATA, load_profile
from .easy_apply import apply_to_job
from .human import pause
from .search import SafetyStop, search_jobs

log = logging.getLogger("applier")


def setup_logging():
    DATA.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(DATA / "applier.log", maxBytes=2_000_000, backupCount=3)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[fh, sh])


def _shot(page, job_id):
    try:
        shots = DATA / "shots"
        shots.mkdir(exist_ok=True)
        page.screenshot(path=str(shots / f"{datetime.now():%Y%m%d-%H%M%S}_{job_id}.png"))
        for old in sorted(shots.glob("*.png"))[:-50]:
            old.unlink()
    except Exception:
        pass


def run_slot(cfg, max_apply: int | None = None) -> None:
    if (why := safety.is_paused()):
        log.info("Paused (%s) — skipping slot", why)
        return
    conn = store.connect()
    applicant = cfg["name"]
    excluded = store.excluded_job_ids(conn, applicant)
    target = max_apply or random.randint(1, cfg["max_per_slot"])
    applied = views = crashes = 0
    with Session(cfg) as page:
        if cfg.get("source") == "linkedin_search":
            try:
                found = search_jobs(page, cfg)
            except SafetyStop as stop:
                safety.pause(f"safety:{stop}")
                notify.send(cfg, f"🛑 Applier paused for {applicant} on job search: {stop}")
                return
        else:
            found = backend.candidate_jobs(cfg)
        jobs = [j for j in found if j["id"] not in excluded]
        if not jobs:
            log.info("No eligible jobs left")
            return
        log.info("Slot: target %d application(s), %d candidate jobs (source=%s)",
                 target, len(jobs), cfg.get("source", "db"))
        for job in jobs:
            if applied >= target or views >= cfg["max_views_per_slot"]:
                break
            views += 1
            log.info("Job %s: %s — %s (score %s)", job["id"], job["title"], job["company"], job["score"])
            try:
                status, detail, steps = apply_to_job(page, cfg, conn, job)
            except Exception as exc:
                log.exception("Job %s crashed", job["id"])
                status, detail, steps = "failed", f"crash:{type(exc).__name__}: {exc}"[:300], 0
            log.info("Job %s -> %s (%s)", job["id"], status, detail)
            if status == "failed":
                _shot(page, job["id"])
            store.log_attempt(conn, applicant, job, status, detail, steps)

            if status == "paused":
                safety.pause(detail)
                notify.send(cfg, f"🛑 Applier paused for {applicant}: {detail}\n"
                                 f"Job: {job['title']} — {job['company']}\n"
                                 "Nothing will be applied until the pause flag is cleared.")
                return
            if status == "skipped" and detail.startswith("quota:"):
                log.info("Claude quota exhausted — ending slot; applying resumes after the reset")
                if not (DATA / f"quota-notified-{datetime.now():%Y%m%d}").exists():
                    (DATA / f"quota-notified-{datetime.now():%Y%m%d}").touch()
                    notify.send(cfg, f"⏸️ Applier for {applicant}: Claude usage limit reached "
                                     f"({detail[len('quota:'):]}). Skipping until it resets — no action needed.")
                return
            if status == "applied":
                applied += 1
            if status == "skipped" and detail.startswith("needs_human:"):
                why, _, link = detail[len("needs_human:"):].partition(" | ")
                notify.send(cfg, f"🙋 Needs you — apply by hand ({applicant})\n"
                                 f"{job['title']} — {job['company']}\nWhy: {why.strip()}\n"
                                 f"Link: {link.strip() or job['url']}")
            if status == "skipped" and detail.startswith("question:"):
                notify.send(cfg, f"❓ {applicant} — new form question(s), job skipped until answered:\n"
                                 f"{detail[len('question:'):]}\n({job['title']} — {job['company']})")
            # Failed / needs-you jobs never pause — only LinkedIn safety signals do
            # (status "paused" above). Spec: "No failure-count pause" (2026-11-05).
            if detail.startswith("crash:"):
                crashes += 1
                if crashes >= 2:
                    log.info("Browser crashed twice — ending this slot (not a pause)")
                    break
            if applied < target and views < cfg["max_views_per_slot"]:
                pause(120, 360) if status == "applied" else pause(20, 60)
    log.info("Slot done: %d applied, %d pages viewed", applied, views)


def plan_day(cfg, day) -> list[datetime]:
    tz = ZoneInfo(cfg["timezone"])
    start_h, end_h = cfg["active_hours"]
    n = random.randint(*cfg["slots_per_day"])
    gap = timedelta(minutes=cfg["min_slot_gap_min"])
    for _ in range(200):
        times = sorted(
            datetime(day.year, day.month, day.day, start_h, tzinfo=tz)
            + timedelta(seconds=random.randint(0, (end_h - start_h) * 3600))
            for _ in range(n)
        )
        if all(b - a >= gap for a, b in zip(times, times[1:])):
            return times
    return times


def send_digest(cfg):
    s = store.day_summary(store.connect(), cfg["name"])
    q = store.unanswered(store.connect(), cfg["name"])
    lines = [f"📮 Applier digest — {cfg['name']}",
             f"• Applied: {len(s['applied'])}"]
    lines += [f"   – {a}" for a in s["applied"][:20]]
    lines.append(f"• Skipped: {s['skipped']} | Failed: {len(s['failed'])}")
    lines += [f"   – {f}" for f in s["failed"][:5]]
    if s["needs_human"]:
        lines.append(f"• Need you (CAPTCHA / account / no form) — apply by hand: {len(s['needs_human'])}")
        lines += [f"   – {x}" for x in s["needs_human"][:15]]
    if q:
        lines.append(f"• Questions waiting for you: {len(q)}")
        lines += [f"   #{x['id']}: {x['question']}" for x in q[:10]]
    if (why := safety.is_paused()):
        lines.append(f"• ⚠️ PAUSED: {why}")
    notify.send(cfg, "\n".join(lines))


def daemon(cfg):
    tz = ZoneInfo(cfg["timezone"])
    dh, dm = map(int, cfg["digest_time"].split(":"))
    while True:
        now = datetime.now(tz)
        slots = [t for t in plan_day(cfg, now.date()) if t > now]
        digest = datetime(now.year, now.month, now.day, dh, dm, tzinfo=tz)
        events = sorted([(t, "slot") for t in slots] + ([(digest, "digest")] if digest > now else []))
        log.info("Today's plan: %s", ", ".join(f"{t:%H:%M} {k}" for t, k in events) or "nothing left")
        for t, kind in events:
            wait = (t - datetime.now(tz)).total_seconds()
            if wait > 0:
                time.sleep(wait)
            try:
                run_slot(cfg) if kind == "slot" else send_digest(cfg)
            except Exception:
                log.exception("%s failed", kind)
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=tz) + timedelta(days=1, minutes=5)
        time.sleep(max(0, (tomorrow - datetime.now(tz)).total_seconds()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["once", "daemon", "status", "qa", "answer", "resume", "look", "try"])
    ap.add_argument("--profile", default="vishal")
    ap.add_argument("--max", type=int)
    ap.add_argument("--url")
    ap.add_argument("--job", type=int)
    ap.add_argument("rest", nargs="*")
    a = ap.parse_args()
    setup_logging()
    if a.cmd == "resume":
        safety.PAUSE_FLAG.unlink(missing_ok=True)
        print("pause flag cleared")
        return
    cfg = load_profile(a.profile)
    if a.cmd == "once":
        run_slot(cfg, a.max)
    elif a.cmd == "daemon":
        daemon(cfg)
    elif a.cmd == "status":
        conn = store.connect()
        print(store.day_summary(conn, cfg["name"], hours=24 * 365))
        print("paused:", safety.is_paused())
    elif a.cmd == "qa":
        for q in store.unanswered(store.connect(), cfg["name"]):
            print(f"#{q['id']} [{q['field_type']}] {q['question']}" + (f"  options: {q['options']}" if q['options'] else ""))
    elif a.cmd == "answer":
        store.answer(store.connect(), int(a.rest[0]), " ".join(a.rest[1:]))
        print("saved")
    elif a.cmd == "look":
        look(cfg, a.url)
    elif a.cmd == "try":
        try_job(cfg, a.job)


def look(cfg, url: str) -> None:
    """Dry run: open a page, show what Haiku sees and what it WOULD do. No clicks."""
    from . import snapshot
    from .brain import next_actions
    with Session(cfg) as page:
        page.goto(url, wait_until="domcontentloaded")
        pause(4, 6)
        snap = snapshot.take(page)
        rendered = snapshot.render(snap)
        print(rendered)
        print("---- errors:", snap["errors"], "| dialog:", snap["dialog"])
        plan = next_actions(cfg, snap, rendered, {"title": "(test)", "company": "(test)"},
                            store.answered(store.connect(), cfg["name"]), [], scope=
                            "You may follow the job's 'Apply' link to the company's own careers site.")
        print("---- HAIKU PLAN:", plan)


def try_job(cfg, job_id: int) -> None:
    """Apply to one job right now (manual test; ignores the pause flag and exclusions)."""
    jobs = {j["id"]: j for j in backend.candidate_jobs({**cfg, "min_score": 0, "include_offsite": True})}
    job = jobs.get(job_id)
    if not job:
        print("job not found:", job_id)
        return
    conn = store.connect()
    with Session(cfg) as page:
        log.info("TRY job %s: %s — %s", job["id"], job["title"], job["company"])
        try:
            status, detail, steps = apply_to_job(page, cfg, conn, job)
        except Exception as exc:
            log.exception("Job %s crashed", job["id"])
            status, detail, steps = "failed", f"crash:{type(exc).__name__}: {exc}"[:300], 0
        log.info("Job %s -> %s (%s)", job["id"], status, detail)
        store.log_attempt(conn, cfg["name"], job, status, detail, steps)


if __name__ == "__main__":
    main()

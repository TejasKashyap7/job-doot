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
import re
import argparse
import logging
import math
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from . import account_health, backend, health, notify, safety, store
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


def run_slot(cfg, max_apply: int | None = None, max_views: int | None = None) -> None:
    if (why := safety.is_paused()):
        log.info("Paused (%s) — skipping slot", why)
        return
    conn = store.connect()
    applicant = cfg["name"]
    excluded = store.excluded_job_ids(conn, applicant)
    target = max_apply or random.randint(1, cfg["max_per_slot"])
    view_cap = max_views or cfg["max_views_per_slot"]
    applied = views = crashes = 0

    def searched():
        try:
            return search_jobs(page, cfg)
        except SafetyStop as stop:
            safety.pause(f"safety:{stop}")
            notify.send(cfg, f"🛑 Applier paused for {applicant} on job search: {stop}")
            return None

    def batches():
        """Fetched jobs first; then (topup_search) Easy Apply search results while under target.
        Spec: apply-agent/approach.md "Volume test"."""
        if cfg.get("source") == "linkedin_search":
            yield searched()
            return
        yield backend.candidate_jobs(cfg)
        if cfg.get("topup_search"):
            for _ in range(cfg["topup_searches"]):
                if applied >= target or views >= view_cap:
                    return
                log.info("Out of fetched jobs at %d/%d — topping up from LinkedIn search", applied, target)
                yield searched()

    with Session(cfg) as page:
        seen = store.tried_keys(conn, applicant, excluded)
        tried = set()      # job ids opened in this slot (search batches can repeat a job)
        for found in batches():
            if found is None:      # safety stop on the search page — everything is paused
                return
            jobs = [j for j in found if j["id"] not in excluded and j["id"] not in tried]
            if not jobs:
                log.info("No eligible jobs in this batch")
                continue
            log.info("Slot: target %d application(s), %d candidate jobs (source=%s)",
                     target, len(jobs), jobs[0].get("keyword") and "search" or cfg.get("source", "db"))
            for job in jobs:
                if applied >= target or views >= view_cap:
                    break
                key = store.job_key(job["title"], job["company"])
                if job["title"] and seen.get(key, job["id"]) != job["id"]:
                    log.info("Job %s: same as job %s (%s — %s), skipping duplicate",
                             job["id"], seen[key], job["title"], job["company"])
                    continue
                seen[key] = job["id"]
                tried.add(job["id"])
                views += 1
                log.info("Job %s: %s — %s (score %s)", job["id"], job["title"], job["company"], job["score"])
                try:
                    status, detail, steps = apply_to_job(page, cfg, conn, job)
                except Exception as exc:
                    log.exception("Job %s crashed", job["id"])
                    status, detail, steps = "failed", f"crash:{type(exc).__name__}: {exc}"[:300], 0
                log.info("Job %s -> %s (%s)", job["id"], status, detail)
                if status == "failed" and detail.startswith("brain:") and health.is_login_error(detail):
                    # Not the job's fault: don't log the attempt (it stays eligible), stop here,
                    # and say so on the widget. The first slot after a re-login just works.
                    log.warning("Claude is logged out on the Pi — ending slot, job %s left for later", job["id"])
                    health.record(health.LOGGED_OUT, "Claude logged out (Pi)", detail[len("brain:"):])
                    flag = DATA / f"login-notified-{datetime.now():%Y%m%d}"
                    if not flag.exists():
                        flag.touch()
                        notify.send(cfg, f"🔑 Applier for {applicant}: Claude is logged out on the Pi, "
                                         "so nothing can be applied.\nFix: ssh tejas@pi5 → claude → /login")
                    return
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
                    # Red on the widget (spec dashboard/phone-widget.md, claude_quota, 2026-11-24)
                    why = detail[len("quota:"):].strip()
                    m = re.search(r"resets\s+([^()]+?)\s*(\(|$)", why)
                    health.record(health.QUOTA, "Claude limit hit" + (f" · resets {m.group(1)}" if m else ""), why)
                    if not (DATA / f"quota-notified-{datetime.now():%Y%m%d}").exists():
                        (DATA / f"quota-notified-{datetime.now():%Y%m%d}").touch()
                        notify.send(cfg, f"🔴 Applier for {applicant} stopped: Claude usage limit hit ({why}). "
                                         "Nothing is applied until it resets. To keep applying now, log the Pi's "
                                         "claude in to another account: ssh tejas@pi5 → ~/.local/bin/claude → /login")
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
                if applied < target and views < view_cap:
                    pause(120, 360) if status == "applied" else pause(20, 60)
    store.add_views(conn, datetime.now().strftime("%Y-%m-%d"), views)   # LinkedIn safety volume log
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


def fixed_target(cfg, day) -> int | None:
    """Volume test: n from `daily_targets` [[from, to, n], ...] (IST dates, inclusive) covering
    `day`, else None. Spec: apply-agent/approach.md "Volume test"."""
    for lo, hi, n in cfg.get("daily_targets") or []:
        if str(lo) <= day.isoformat() <= str(hi):
            extra = 0
            if cfg.get("daily_extra"):   # e.g. [1, 5]: random bonus, fixed for the whole day
                a, b = cfg["daily_extra"]
                extra = random.Random(f"{cfg['name']}:{day.isoformat()}").randint(int(a), int(b))
            return int(n) + extra
    return None


def has_target(cfg, day) -> bool:
    return fixed_target(cfg, day) is not None or cfg.get("daily_target") == "fetched"


def today_progress(cfg) -> tuple[int, int, str] | None:
    """(target today, applied today, what the target is), IST day. Target = fixed volume-test
    number for today, else jobs fetched today (daily_target: fetched). None when neither applies
    or the backend can't be read (then slots use old pacing).
    Spec: apply-agent/assumption.md + approach.md "Test mode" / "Volume test"."""
    tz = ZoneInfo(cfg["timezone"])
    midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    target, label = fixed_target(cfg, midnight.date()), "fixed"
    if target is None:
        if cfg.get("daily_target") != "fetched":
            return None
        label = "fetched"
        try:
            target = backend.fetched_since(
                cfg, midnight.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds"))
        except Exception:
            log.exception("could not read today's fetched count — using normal pacing")
            return None
    applied = store.applied_since(store.connect(), cfg["name"],
                                  midnight.replace(tzinfo=None).isoformat(timespec="seconds"))
    return target, applied, label


def slot_size(cfg, kind: str, slots_left: int) -> tuple[int | None, int | None]:
    """(applications, page views) for this slot. (None, None) = normal 1-2 pacing.
    (0, 0) = today's target already met."""
    prog = today_progress(cfg)
    if prog is None:
        return None, None
    target, applied, label = prog
    remaining = max(0, target - applied)
    log.info("Today: target %d (%s), applied %d, remaining %d, slots left %d",
             target, label, applied, remaining, slots_left)
    if remaining == 0:
        return 0, 0
    if kind == "sweep":
        return remaining, cfg["sweep_max_views"]
    n = max(1, math.ceil(remaining / max(1, slots_left)))
    return n, max(cfg["max_views_per_slot"], 5 * n)


def _at(day, hhmm: str, tz) -> datetime:
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), tz)


def catchup_slots(cfg, now) -> list[datetime]:
    """6 PM rule: under target => extra slots every random catchup_gap_min until catchup_end."""
    prog = today_progress(cfg)
    if prog is None or prog[1] >= prog[0]:
        log.info("Catch-up check: target met or no target — no extra slots")
        return []
    end = _at(now.date(), cfg["catchup_end"], now.tzinfo)
    out, t = [], now
    while True:
        t += timedelta(minutes=random.uniform(*cfg["catchup_gap_min"]))
        if t >= end:
            break
        out.append(t)
    log.info("Catch-up: %d/%d applied — adding %d slot(s): %s", prog[1], prog[0], len(out),
             ", ".join(f"{x:%H:%M}" for x in out))
    return out


def daemon(cfg):
    tz = ZoneInfo(cfg["timezone"])
    dh, dm = map(int, cfg["digest_time"].split(":"))
    while True:
        now = datetime.now(tz)
        slots = [t for t in plan_day(cfg, now.date()) if t > now]
        digest = datetime(now.year, now.month, now.day, dh, dm, tzinfo=tz)
        events = [(t, "slot") for t in slots] + ([(digest, "digest")] if digest > now else [])
        for lo, hi in cfg["health_check_windows"]:   # read-only LinkedIn account check
            t0 = datetime.combine(now.date(), datetime.strptime(lo, "%H:%M").time(), tz)
            t1 = datetime.combine(now.date(), datetime.strptime(hi, "%H:%M").time(), tz)
            t = t0 + timedelta(seconds=random.randint(0, max(0, int((t1 - t0).total_seconds()))))
            if t > now:
                events.append((t, "check"))
        if has_target(cfg, now.date()):
            sh, sm = map(int, cfg["sweep_time"].split(":"))
            sweep = datetime(now.year, now.month, now.day, sh, sm, tzinfo=tz)
            if sweep > now:
                events.append((sweep, "sweep"))
            if cfg.get("catchup_time"):
                ct = _at(now.date(), cfg["catchup_time"], tz)
                if ct > now:
                    events.append((ct, "catchup"))
                elif now < _at(now.date(), cfg["catchup_end"], tz):   # restarted after 18:00
                    events.append((now + timedelta(minutes=1), "catchup"))
        events.sort()
        log.info("Today's plan: %s", ", ".join(f"{t:%H:%M} {k}" for t, k in events) or "nothing left")
        while events:
            t, kind = events.pop(0)
            wait = (t - datetime.now(tz)).total_seconds()
            if wait > 0:
                time.sleep(wait)
            try:
                if kind in ("slot", "sweep"):
                    n, views = slot_size(cfg, kind, 1 + sum(k in ("slot", "sweep") for _, k in events))
                    if n == 0:
                        log.info("Today's target already met — skipping %s", kind)
                        continue
                    before = health.writes
                    run_slot(cfg, n, views)
                    if health.writes == before:  # slot didn't report an error itself
                        health.record(health.OK)
                elif kind == "catchup":
                    events += [(x, "slot") for x in catchup_slots(cfg, datetime.now(tz))]
                    events.sort()
                elif kind == "check":
                    account_health.run_check(cfg)
                else:
                    send_digest(cfg)
                    try:   # shared question bank, once a day (spec question-bank/spec.md)
                        from . import qbank
                        log.info(qbank.sync(cfg))
                    except Exception:
                        log.exception("qbank sync failed — will retry tomorrow")
                    try:   # suggested answers for the owner's Answers tab (local only)
                        from . import suggest
                        if cfg.get("suggest_for"):
                            log.info("suggestions made: %d", suggest.run(cfg, cfg["suggest_for"]))
                    except Exception:
                        log.exception("answer suggestions failed — will retry tomorrow")
            except Exception as exc:
                log.exception("%s failed", kind)
                if kind in ("slot", "sweep"):
                    first = (str(exc).splitlines() or [""])[0]
                    health.record(health.CRASHED, f"crashed {datetime.now():%H:%M}",
                                  f"{type(exc).__name__}: {first}")
                    # Whatever got stuck, a fresh process clears it: exit non-zero and
                    # systemd (Restart=on-failure) restarts us and re-plans the day.
                    # Spec: apply-agent/flaws.md FLAW-1, option C.
                    log.error("Slot crashed — exiting so systemd restarts the applier clean")
                    sys.exit(1)
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=tz) + timedelta(days=1, minutes=5)
        time.sleep(max(0, (tomorrow - datetime.now(tz)).total_seconds()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["once", "daemon", "status", "qa", "answer", "resume", "look", "try", "check"])
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
    elif a.cmd == "check":
        print(account_health.run_check(cfg))
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

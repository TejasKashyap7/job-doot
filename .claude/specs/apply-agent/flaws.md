# Apply Agent — Flaws

---

## FLAW-1: One failed browser connection breaks every later slot until the applier is restarted
**Status: OPEN — fix written (Options A + B, Tejas asked for it 2026-11-12); mark RESOLVED only after it is deployed on the Pi and a slot runs clean**

**The problem:**
Each slot opens the browser in three steps (`applier/browser.py` → `Session.__enter__`):
1. make sure Chromium is running with debug port 9223 open,
2. start Playwright (this creates a hidden background "event loop" inside the program),
3. connect Playwright to Chromium over that port and open a tab.

Shutting Playwright down (`pw.stop()`) only happens in `__exit__`, and Python only
runs `__exit__` if `__enter__` *finished*. If step 3 fails, step 2's event loop is
never shut down. Playwright refuses to start a second one in the same program, and
the daemon is one long-running program that catches the error and keeps going, so
**every later slot dies in under a second** with
`It looks like you are using Playwright Sync API inside the asyncio loop`.
systemd's `Restart=on-failure` never triggers because the program never exits.

**Example (real, 11–12 Nov 2026):**
After the Pi came back from 3 days off, two overdue slots ran back to back. At
16:12 on 11 Nov the second one found port 9223 "open" while Chromium was still
restarting, and the connect got `ECONNREFUSED 127.0.0.1:9223`. From then on, both
remaining slots on 11 Nov and all 8 slots on 12 Nov (10:42 → 19:43) crashed instantly:
0 jobs looked at, 0 applied, 0 alerts. The orphaned Playwright driver (PID 18173,
started 16:12:06) was still running a day later.

**Options:**
- **A. Clean up on a half-finished start** — if anything after step 2 fails, call
  `pw.stop()` before re-raising. One bad connect then costs one slot, not all of them.
- **B. Retry the connect** — try step 3 up to 3 times, 5 s apart, re-checking Chromium
  between tries. This covers the "Chromium is just restarting" race, so the slot usually
  isn't lost at all.
- **C. Self-heal** — after N slot crashes in a row, the daemon exits non-zero so
  systemd restarts it with a clean process. A safety net for any *other* leak.
- **D. Alert** — a whole-slot crash raises one bell + Telegram notification
  (today it is silent; see FLAW-3).

**Decision (Tejas, 2026-11-12):** fix the code now → A + B built. C and D not built yet.

---

## FLAW-2: Claude login on the Pi expires silently, so every brain call fails
**Status: OPEN — needs a human login on the Pi; longer-term choice pending**

**The problem:**
The brain runs `~/.local/bin/claude -p ...` on the Pi with Tejas's subscription login.
When that OAuth session expires and can't refresh, every call returns
`Failed to authenticate: OAuth session expired and could not be refreshed`. Each job
that needs the brain is marked `failed (brain:...)`, one by one, and the cause never
gets a single clear "log in again" alert.

**Example (real, 11 Nov 2026):**
The only slot that ran on 11 Nov found 6 real candidates (L7Commerce ×2, CoffeeBeans,
Manastu Space, Sabre, HGS). All 6 failed with the auth error. Re-tested 12 Nov 20:19:
still expired.

**Options:**
- **A. Log in again** (`claude` → `/login` on the Pi). Quick, but it will expire again.
- **B. Long-lived token** — `claude setup-token` on the Pi, passed to the service as
  `CLAUDE_CODE_OAUTH_TOKEN` (via a git-ignored env file, never committed).
- **C. Detect auth errors** — on an auth failure, stop the slot, pause applying with a
  reason, and send ONE "Claude needs login" alert instead of failing job after job.

---

## FLAW-3: A slot that crashes before reaching any job leaves no notification
**Status: OPEN**

**The problem:**
The bell (`watch_applier`) only turns per-job attempts into notifications. A slot that
dies at startup (FLAW-1) writes no attempt, so nothing shows up in the bell or on Telegram.

**Example (real, 12 Nov 2026):**
8 crashed slots, zero notifications. The problem was found only because Tejas noticed
there were no applications.

**Options:**
- **A.** The daemon records slot crashes, and the bell raises one notification per
  crash streak.
- **B.** The 21:30 digest says "N slots crashed today" with the error's first line.

---

## FLAW-4: After a reboot the day plan uses the wrong clock, so overdue slots fire back to back
**Status: OPEN — low priority**

**The problem:**
The Pi has no RTC battery, so it boots with an old time. The daemon builds the day plan
before NTP corrects the clock. Once the clock jumps forward, every "past" slot runs
immediately, one after another. Back-to-back slots are what caused the Chromium restart
race in FLAW-1, and they look less human.

**Example (real, 11 Nov 2026):**
Boot clock said 8 Nov 16:00, so the plan was "16:39, 17:00". The real time was 11 Nov
~15:56, so both slots fired at once (15:56 and 16:12).

**Options:**
- **A.** Add `After=time-sync.target` + `Wants=time-sync.target` to the user unit (or
  wait for `timedatectl` to say synced before planning).
- **B.** On startup, drop slots that are more than a few minutes overdue instead of running them.

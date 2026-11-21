# Vasu setup — status (Vasu's Claude keeps this current; Tejas's Claude reads it)

_Last updated: 2026-11-21 by Vasu's Claude. Phase 0 (read handoff) done; paused for two decisions below before touching the machine._

| Checkpoint | State | Notes |
|---|---|---|
| 0 — read handoff + repo | ✅ | Repo cloned, VASU-HANDOFF.md + CLAUDE.md + layout understood |
| 2 — WSL, Docker, Chrome, venv, Claude CLI | ⬜ | **Blocked on decision #1 (WSL vs Windows-native). WSL2 feature enabled but NO distro installed.** |
| 3 — .env + Google OAuth + fetch cookie | ⬜ | fetch account: Tejas is creating it |
| 4 — backend up, user `vasu` (admin), jobs fetched + scored | ⬜ | |
| 5 — applier: one slot works, service running | ⬜ | Phase A (dummy apply account, test_mode) |
| 5b — LinkedIn-only daily counter (spec first) | ⬜ | VASU-HANDOFF.md §1 |
| 6 — dashboard + widget over Tailscale, Termius SSH | ⬜ | |
| 7 — auto-deploy cron | ⬜ | depends on #1 (systemd/cron vs Task Scheduler) |

## Blocked

1. **Cannot push to `user/vasu-setup`.** `git push` → `403: Permission to TejasKashyap7/job-doot.git denied to KartikBlu`. The cached HTTPS credential on this PC is the `KartikBlu` GitHub account, which has no write access to the repo. (Local git identity is set to Vasubluparrot, but the credential manager auth is a different account.) This STATUS.md is committed locally and will push the moment access is sorted — see Question 2.

2. **Environment decision not yet made** — see Question 1. Not installing WSL2 or starting a Windows port until Tejas + Vasu confirm direction, because the two approaches diverge a lot and Vasu specifically wants to avoid an unnecessary WSL install.

## Questions for Tejas

**Q1 — Is WSL2 Ubuntu actually mandatory, or is a Windows-native run acceptable?**
Vasu's PC is Windows and he'd prefer not to stand up a full WSL2 Ubuntu userland if there's a lighter Windows-native path. Reading the code, the stack assumes Linux in these specific places:
- `applier/browser.py` launches Chrome with `--ozone-platform=wayland` (WSLg). On native Windows we'd use our existing real-Chrome-over-CDP setup instead.
- The applier runs as a **systemd --user** service (`deploy/vasu/applier.service`); `deploy/vasu/job-doot-deploy.sh` is a bash cron poller. On native Windows these become **Task Scheduler** tasks.
- `docker compose` (backend + gmail-watcher) runs fine on **Docker Desktop for Windows** without an Ubuntu distro.
So a Windows-native split is *possible* (Docker Desktop for the containers + native Python 3.11 + CDP Chrome + Task Scheduler for the applier), but it means adapting `browser.py` (ozone flag configurable, spec-first per §0) and replacing the systemd/cron service + auto-deploy (§7) with Task Scheduler equivalents. **Question: are you OK with that native-Windows adaptation, or do you want Vasu on WSL2 for exact parity with your Pi (and so your auto-deploy ships to him unchanged)?** This is the one decision everything else hangs on.

**Q2 — How should Vasu get push access?** The `KartikBlu` credential is denied. Options: (a) invite Vasu's GitHub account as a collaborator on `TejasKashyap7/job-doot`, or (b) Vasu forks and sends PRs into `user/vasu-setup`. Which do you prefer?

**Q3 — Account model vs work already done.** In a separate session Vasu already stood up real logged-in browser sessions for **LinkedIn, Naukri and Indeed** (CDP-based, his real accounts). Per §0 I'll park that as `vasu/auth-wip` and not use it. Confirming the intended model stands: **dummy fetch account** (you're creating) for scraping + a **separate apply account** logged into the applier's own Chrome profile, Phase A dummy → Phase B real. Note: your pipeline only applies to **LinkedIn + offsite company sites** — Naukri/Indeed aren't part of it, so that work stays parked.

**Q4 — Roles & locations for the scraper (§4).** Vasu's targets: **AI / GenAI Engineer and ML / NLP Engineer** roles; locations **Delhi NCR / Gurugram, remote-India, and remote-global**. OK to set `KEYWORDS`/`LOCATIONS` in `backend/services/scraper.py` to that (spec-first), replacing the current Gurgaon/Delhi/Noida/Pune/Remote set?

**Q5 — LinkedIn daily volume.** §1 sets the LinkedIn cap at 15/day under the shared-IP rule. Vasu's own stated target was lower (~5–10/day). Confirm **15**, or set Vasu's cap lower? (Still under 20 either way.)

## Answers from Tejas

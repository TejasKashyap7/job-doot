# job-doot — Windows setup & recovery runbook

> **Purpose:** rebuild this system on a fresh or rebooted Windows PC from scratch.
> Written and kept current by Vasu's Claude as the setup is performed, so every
> command here is one that was actually run (not theoretical). If you are setting
> up on a new machine, read **Part 0** first, gather everything, then go in order.
>
> **Status legend:** ✅ done & verified · 🔧 in progress · ⬜ not started · ✋ needs a human
>
> _Last updated: 2026-11-21._

---

## Part 0 — What to gather BEFORE you start (the human inputs)

You cannot automate these. Collect them first; the install waits on nothing else.

### 0.1 Accounts & keys (have these ready)
| Thing | Where to get it | Used for |
|---|---|---|
| **GitHub access** | Ask the repo owner (Tejas) to add your GitHub account as a **collaborator** on `TejasKashyap7/job-doot` | pushing your `user/vasu-setup` changes + receiving auto-deploy |
| **Groq API key** | console.groq.com → API Keys | tailoring your resume per job |
| **Telegram bot token + chat ID** | Telegram → @BotFather → `/newbot`; chat ID via the bot | apply alerts + answering screening questions from your phone |
| **Google Cloud OAuth client** (`credentials.json`) | console.cloud.google.com → APIs & Services → Credentials → OAuth client (Desktop) | Gmail watcher (reads job-related mail) |
| **Dummy LinkedIn "fetch" account** | a throwaway account (Tejas provides the `li_at` cookie) | scraping job listings — NOT your real account |
| **Your real LinkedIn "apply" account** | your own login | applying — only switched on at Phase B |
| **Dashboard password** | you choose | logging into the web dashboard |

> Random secrets (`SESSION_SECRET`, `WIDGET_KEY`, `WEBHOOK_SECRET`) are **generated for you** during setup — you don't invent these.

### 0.2 Your resume
- Provide your resume as a **LaTeX `.tex` master** (source of truth) **and** a compiled **PDF**.
  - `.tex` master → used by the tailoring agent to produce a per-job copy (the master is never modified).
  - PDF → uploaded with applications.
- Place them where setup tells you: `.tex` goes in via the dashboard signup; PDF goes to `data/applier/<you>_resume.pdf`.

### 0.3 The intake interview (profile facts — answer truthfully)
Before your dashboard user is created, you complete an **intake interview** (schema in `.claude/specs/multi-user/intake-prompt.md`). Have honest answers ready for:
- **Identity & contact:** name, email, phone, city, LinkedIn/GitHub URLs.
- **Target roles:** e.g. AI / GenAI Engineer, ML / NLP Engineer.
- **Target locations:** e.g. Delhi NCR / Gurugram, remote-India, remote-global.
- **Experience & skills:** real, verifiable against your repos — **don't invent anything** (the agent marks gaps UNFIXABLE rather than fabricating).
- **Education, current role, notice period, current & expected compensation.**
- **Work authorization / sponsorship needs** (for international roles).
- **Standard screening answers** you'll reuse: willing to relocate? years with X? expected CTC? availability? These seed the Q&A bank so the applier doesn't stop to ask twice.

### 0.4 Decisions to confirm
- **LinkedIn daily cap:** must stay **under 20/day** (shared-IP rule). Default **15**.
- **Roles & cities** for the scraper (above) — these replace the repo defaults.

---

## Part 1 — Windows host prep

### 1.1 Check what's already present
```powershell
wsl.exe --version          # WSL kernel/WSLg present?
wsl.exe --list --online    # can reach the distro store?
tailscale version          # Tailscale installed + signed in?
```
On this PC (2026-11-21): WSL **2.6.1.0** already installed (kernel 6.6.87, WSLg 1.0.66) → **no reboot / no feature-enable needed**. Tailscale **1.104.7** present. Docker & Ollama absent (installed inside WSL below).

> If `wsl --version` errors (older PC), run **admin PowerShell**: `wsl --install` → reboot → then continue.

### 1.2 Install Ubuntu (headless)
```powershell
wsl.exe --install -d Ubuntu-24.04 --no-launch
```
`--no-launch` skips the interactive first-run so the rest can be scripted. Status: 🔧 installing.

### 1.3 Keep-it-running (so the system is always-on) — ✋ some steps are yours
- Power plan: **Sleep = Never**, hibernate off.
- `%UserProfile%\.wslconfig` with `vmIdleTimeout=-1` (WSL stays up with no terminal). _Claude writes this._
- Task Scheduler "At log on" task to keep WSL alive across reboots. _Claude creates this._
- **✋ Auto sign-in after reboot** (Sysinternals Autologon or `netplwiz`) — **you set this** (security-sensitive; the applier's Chrome needs a signed-in desktop). 
- Windows Update: set active hours / pause so it doesn't reboot mid-day.

---

## Part 2 — Inside WSL (software stack) — mostly automated by Claude

_Filled with exact commands as each step is executed:_

- ⬜ 2.1 Create Linux user + passwordless sudo (safe in WSL — Windows already has root access to the distro).
- ⬜ 2.2 systemd on (`/etc/wsl.conf`), `wsl --shutdown`, `loginctl enable-linger`, enable `cron`.
- ⬜ 2.3 Docker CE inside WSL (not Docker Desktop) + enable service. _Deviation from handoff; noted in STATUS.md._
- ⬜ 2.4 Google Chrome `.deb` (not snap chromium).
- ⬜ 2.5 Python 3.11 via `uv` + venv at `~/.venvs/applier311` + `pip install -r requirements.txt`.
- ⬜ 2.6 Ollama + `ollama pull gemma3:4b`.
- ⬜ 2.7 Claude Code in WSL — **✋ you run `claude /login`** (your subscription).
- ⬜ 2.8 Clone repo into Linux home: `git clone -b user/vasu-setup <repo> ~/job-doot` (never under `/mnt/c`).

---

## Part 3 — Secrets & .env — Claude generates randoms, you supply keys
- ⬜ `.env` from `.env.example`: Claude fills the random secrets + paths; you paste Groq/Telegram/dashboard values.
- ⬜ Google OAuth: drop `credentials.json` in `data/`, run `tools/oauth_bootstrap.py` once → `data/token.json`.
- ⬜ Fetch-account `li_at` cookie → `data/li_cookies.json` or dashboard `/admin/linkedin-cookie`.

---

## Part 4 — Backend + first user
- ⬜ `docker compose up -d --build` → `curl localhost:8080/health`.
- ⬜ Create invite token, run intake interview, sign up user, make admin.
- ⬜ Set scraper `KEYWORDS`/`LOCATIONS` (spec-first) to your roles/cities.

## Part 5 — Applier
- ⬜ Profile from `deploy/vasu/vasu.yaml.example`; resume PDF in place.
- ⬜ Apply-account Chrome login (Phase A dummy first).
- ⬜ `applier.run status / look / once` smoke tests; install the service.
- ⬜ LinkedIn-only daily counter change (spec-first, §1).

## Part 6 — Dashboard + phone widget (over Tailscale)
- ⬜ Reach `http://<PC tailscale IP>:8080` from iPhone; allow TCP 8080 on the Tailscale interface only.
- ⬜ Scriptable widget: paste loader, set PC IP + WIDGET_KEY.

## Part 7 — Auto-deploy
- ⬜ Install `deploy/vasu/job-doot-deploy.sh` poller (pulls + rebuilds + health-checks the branch).

---

## Reboot / recovery (when it's already installed once)
After a normal reboot, nothing should need reinstalling — verify instead:
1. Signed-in desktop (auto-login) → WSL keep-alive task fired.
2. `wsl -d Ubuntu-24.04 -- systemctl is-active docker cron` → both `active`.
3. `docker ps` shows `jobhunter-backend` (+ gmail-watcher) up; `curl localhost:8080/health` OK.
4. `systemctl --user status applier` running.
5. Dashboard loads over Tailscale; widget refreshes.
If a step is down, the matching Part above has the fix. Full reinstall only if WSL itself is gone → start at Part 1.

## Troubleshooting index
_(Appended as issues are hit and solved during setup.)_

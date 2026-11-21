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
`--no-launch` skips the interactive first-run so the rest can be scripted. ✅ installed Ubuntu 24.04.5 (no reboot). Run commands non-interactively with `wsl -d Ubuntu-24.04 -- bash -lc '<cmd>'`.

### 1.3 Keep-it-running (so the system is always-on) — ✋ some steps are yours
- Power plan: **Sleep = Never**, hibernate off.
- `%UserProfile%\.wslconfig` with `vmIdleTimeout=-1` (WSL stays up with no terminal). _Claude writes this._
- Task Scheduler "At log on" task to keep WSL alive across reboots. _Claude creates this._
- **✋ Auto sign-in after reboot** (Sysinternals Autologon or `netplwiz`) — **you set this** (security-sensitive; the applier's Chrome needs a signed-in desktop). 
- Windows Update: set active hours / pause so it doesn't reboot mid-day.

---

## Part 2 — Inside WSL (software stack) — ✅ done (run all as the created `vasu` user)

**2.1 User + passwordless sudo + systemd** (run once as root: `wsl -d Ubuntu-24.04 -u root -- bash -lc '...'`):
```bash
apt-get update -y && apt-get install -y sudo curl ca-certificates git wget gnupg lsb-release apt-transport-https
useradd -m -s /bin/bash vasu && usermod -aG sudo vasu
echo 'vasu ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/vasu && chmod 440 /etc/sudoers.d/vasu
printf '[boot]\nsystemd=true\n[user]\ndefault=vasu\n' > /etc/wsl.conf
```
Then from PowerShell: `wsl --shutdown` (applies systemd + default user). ✅

**2.2 Services** (as vasu): `sudo loginctl enable-linger vasu && sudo systemctl enable --now cron`. ✅ (`systemctl is-system-running` → running)

**2.3 Docker CE** (NOT Docker Desktop — deviation, see STATUS.md): `curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker vasu && sudo systemctl enable --now docker`. ✅ 29.10. Use `sudo docker ...` until a fresh login activates the group.

**2.4 Google Chrome**: `wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install -y ./google-chrome-stable_current_amd64.deb`. ✅ 158.

**2.5 Python 3.11 + venv**: `curl -LsSf https://astral.sh/uv/install.sh | sh; uv python install 3.11; uv venv -p 3.11 ~/.venvs/applier311; cd ~/job-doot && VIRTUAL_ENV=~/.venvs/applier311 uv pip install -r requirements.txt`. ✅ (`playwright`+`python_ghost_cursor` import OK).

**2.6 ~~Ollama~~ — SKIPPED.** Scoring moved to Claude (see Part 3b). Ollama was disabled: `sudo systemctl disable --now ollama`.

**2.7 Claude Code CLI**: `curl -fsSL https://claude.ai/install.sh | bash`. ✅ v2.1.330 at `~/.local/bin/claude`. **✋ one-time login:** open Ubuntu, run `claude`, log in (browser URL → paste code). Verify: `claude -p "say PONG" --model haiku`.
> PATH fix (WSL doesn't add `~/.local/bin`): append `export PATH="$HOME/.local/bin:$PATH"` to `~/.profile` and `~/.bashrc`.

**2.8 Repo**: `git clone -b user/vasu-setup https://github.com/TejasKashyap7/job-doot.git ~/job-doot` (in Linux home, never `/mnt/c`). ✅ Set git identity with `git -C ~/job-doot config user.name/‍user.email`.

---

## Part 3 — Secrets & .env — Claude generates the randoms
`.env` lives at `~/job-doot/.env` (chmod 600, git-ignored). Generated by `~/setup_jobB.sh`. Random secrets (`SESSION_SECRET`, `WEBHOOK_SECRET`, `WIDGET_KEY`, `CLAUDE_SHIM_TOKEN`) are auto-created; `DASHBOARD_PASSWORD` starts as a random temp — **change it to one you like and `docker compose restart backend`**. No Groq/Telegram keys needed.
- ⬜ Google OAuth (Gmail watcher, later): drop `credentials.json` in `data/`, run `tools/oauth_bootstrap.py` once → `data/token.json`.

## Part 3b — Claude LLM bridge (replaces Groq + Ollama) — ✅
This instance routes all backend LLM through the Claude subscription via a host shim. Spec: `.claude/specs/claude-llm/approach.md`.
- `tools/claude_shim.py` — host HTTP service (`:8099`) running `claude -p`; installed as **systemd --user** `claude-shim.service` (`systemctl --user enable --now claude-shim`). Verify: `curl localhost:8099/health`.
- `backend/services/claude_client.py` — drop-in `chat_json`/`chat_text`; backend reaches the shim at `host.docker.internal:8099` (already in compose `extra_hosts`).
- `scorer.py` → Claude **haiku**; `critic.py`/`improver.py` → Claude **sonnet**.
- Old `groq_client.py`/`local_llm_client.py` kept (unused) for mergeability.
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

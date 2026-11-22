# START HERE — job-doot, from a blank PC to a self-running job applier

> **Who this is for:** someone who has **never touched this system** and wants it running on
> their own machine. No prior knowledge assumed. We (the people before you) spent two full days
> figuring this out with a lot of trial and error — this document is so **you don't have to**.
>
> **This guide is Windows-first** (it's what we set up on). If you're on macOS or Linux, the
> *shape* is the same — see [§11 "Not on Windows?"](#11--not-on-windows). Most steps already run
> inside Linux (WSL), so they port almost directly.
>
> **Companion file:** [`GOTCHAS.md`](./GOTCHAS.md) — every trap we hit and the exact fix. When a
> step says "if it breaks, see GOTCHAS," that's where to look.

---

## 0 · The fastest path: hand this to a coding agent

Almost everyone sets this up with a coding agent (Claude Code, etc.). That's the intended way.
Open your agent **inside this repo** and paste:

> "Set up job-doot on this machine by following `START-HERE.md` top to bottom. I'm on Windows
> with zero prior setup. Do each phase, run the verify step, and stop to ask me only for the
> human inputs listed in §2 (accounts, logins, my resume, my profile facts). Check `GOTCHAS.md`
> whenever something fails before improvising."

Then work through the phases *with* the agent. The parts only a human can do (logging into
accounts, choosing passwords, BIOS settings) are marked **✋ YOU**. Everything else the agent runs.

---

## 1 · What this system actually is (2-minute tour)

job-doot finds jobs, tailors your resume to each, and **applies for you**, with a dashboard you
watch from your phone. Five pieces:

| Piece | What it does | Where it runs |
|---|---|---|
| **Backend + dashboard** | Scrapes jobs, scores them, tailors your resume, serves the website | Docker container |
| **The "brain"** | The LLM that scores/tailors/answers questions | A small **Claude shim** on your host (runs `claude -p`) |
| **The applier** | Opens a real Chrome, applies on LinkedIn + company sites | A Python program on the host (not in Docker) |
| **The dashboard/widget** | What you look at — jobs, applied count, blockers | Browser + an iPhone widget, reached over **Tailscale** |
| **Your data** | Jobs, scores, answers you give | A `data/` folder on disk (survives everything) |

**How they connect:** the applier asks the backend for good jobs → opens Chrome → applies →
anything it can't answer it "banks" for you in the dashboard's **Answers** tab. The brain (Claude)
does all the thinking. On Windows, all of this lives inside **WSL2** (a real Linux inside Windows)
so it matches the Linux/Raspberry-Pi design the system was built for.

> **Key architecture note:** this setup uses your **Claude subscription** as the brain — **no Groq,
> no Ollama, no Telegram**. If you read older docs mentioning those, ignore them; they were
> replaced. See [§4](#4--the-brain-claude-as-the-llm).

---

## 2 · ✋ Gather these BEFORE you start (you can't automate them)

Collect everything here first — the install waits on nothing else.

**Accounts & access**
- [ ] **GitHub access** to the repo — ask the owner to add you as a **collaborator** (you'll push a branch).
- [ ] **A Claude subscription** (this is the brain). You'll log the Claude CLI in once.
- [ ] **A "fetch" LinkedIn account** — a *throwaway* account used only to scrape listings (you'll paste its `li_at` cookie). **Not your real one.**
- [ ] **Your real LinkedIn account** — used only for *applying*. You'll log it into a dedicated Chrome profile.
- [ ] **A Gmail account + a Gmail "App Password"** — lets the applier read email verification codes (OTPs) on company sites. (Create at myaccount.google.com/apppasswords; needs 2-Step Verification on.)
- [ ] **Tailscale** installed + signed in on this PC and your phone (free) — this is how your phone reaches the dashboard.

**Your stuff**
- [ ] **Your resume** as both a **LaTeX `.tex`** (the tailoring source) **and** a compiled **PDF** (what gets uploaded).
- [ ] **Your profile facts** — answer truthfully; the system never fabricates. Have ready: name, email, phone, city, LinkedIn/GitHub, target roles, target locations, education, current role, years of experience, skills (real ones), notice period, current & expected salary, work authorization / visa needs, and **your full postal address** (house/street/area/city/district/state/PIN/country).

**Decisions**
- [ ] **Daily apply cap** — keep it **under 20/day** (shared-IP safety). Default **15**.
- [ ] **Target roles & cities** for the scraper.

> **Secrets you do NOT invent** — `SESSION_SECRET`, `WIDGET_KEY`, `CLAUDE_SHIM_TOKEN` are generated
> for you. You only choose a **dashboard password** and provide the account logins above.

---

## 3 · Windows base: WSL2 + Docker + tools

> **Goal:** a real Linux (Ubuntu) running inside Windows, with systemd, a GUI bridge for Chrome,
> Docker, Python, and the Claude CLI.

**3.1 — Check / install WSL** (✋ admin PowerShell if installing)
```powershell
wsl.exe --version                 # already present? great.
# If that errors: run `wsl --install` in an ADMIN PowerShell, reboot, then continue.
wsl.exe --install -d Ubuntu-24.04 --no-launch
```
**Verify:** `wsl.exe -l -v` shows `Ubuntu-24.04`.

**3.2 — Turn on systemd + a default user** (run as root once)
```bash
wsl -d Ubuntu-24.04 -u root -- bash -lc '
apt-get update -y && apt-get install -y sudo curl git wget gnupg ca-certificates
useradd -m -s /bin/bash me && usermod -aG sudo me
echo "me ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/me && chmod 440 /etc/sudoers.d/me
printf "[boot]\nsystemd=true\n[user]\ndefault=me\n" > /etc/wsl.conf'
```
Then in PowerShell: `wsl --shutdown` (applies it). **Verify:** `wsl -d Ubuntu-24.04 -- systemctl is-system-running` → `running`. *(If systemd isn't on, see GOTCHAS "systemd not starting".)*

**3.3 — Keep services alive without a terminal open**
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'sudo loginctl enable-linger $USER && sudo systemctl enable --now cron'
```

**3.4 — Docker, Chrome, Python (uv), Claude CLI** (all inside WSL as your user)
```bash
wsl -d Ubuntu-24.04 -- bash -lc '
# Docker CE (NOT Docker Desktop — keeps setup scriptable)
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER && sudo systemctl enable --now docker
# Google Chrome (the applier drives a real Chrome)
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install -y ./google-chrome-stable_current_amd64.deb
# uv + Python 3.11 for the applier
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.11
# Claude CLI (the brain)
curl -fsSL https://claude.ai/install.sh | bash
# PATH fix: WSL does not add ~/.local/bin
grep -q ".local/bin" ~/.bashrc || echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" | tee -a ~/.bashrc ~/.profile'
```
**✋ YOU — log Claude in once:** open an Ubuntu terminal and run `claude`, follow the browser login.
**Verify:** `claude -p "say PONG" --model haiku` prints `PONG`. *(If "command not found," re-open the terminal — the PATH line above needs a fresh shell.)*

**3.5 — Get the code** (clone into the Linux home, **never** `/mnt/c` — see GOTCHAS)
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'git clone <REPO_URL> ~/job-doot && cd ~/job-doot && ~/.local/bin/uv venv -p 3.11 ~/.venvs/applier311 && VIRTUAL_ENV=~/.venvs/applier311 ~/.local/bin/uv pip install -r requirements.txt'
```
**Verify:** `~/.venvs/applier311/bin/python -c "import playwright, yaml; print('ok')"`.

---

## 4 · The brain: Claude as the LLM

> **Goal:** the backend sends all its "thinking" (scoring, tailoring, simplifying questions) to
> your Claude subscription through a tiny local service called the **shim**.

The shim (`tools/claude_shim.py`) is an HTTP service on `:8099` that runs `claude -p`. The backend
(in Docker) reaches it at `host.docker.internal:8099`. Install it as a user service:
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'systemctl --user enable --now claude-shim'
```
**Verify:** `curl -s localhost:8099/health` → `{"ok": true, ...}`.

*(If the unit doesn't exist yet, the repo's `tools/` has the service file — copy it to
`~/.config/systemd/user/` and `systemctl --user daemon-reload` first.)*

---

## 5 · The app, its config, and your login

**5.1 — Create `.env`** at `~/job-doot/.env` (git-ignored). Minimum, Claude-only:
```
DASHBOARD_PASSWORD=<choose-a-password>
SESSION_SECRET=<generate: `openssl rand -hex 32`>
WIDGET_KEY=<generate: `openssl rand -base64 24`>
CLAUDE_SHIM_URL=http://host.docker.internal:8099
CLAUDE_SHIM_TOKEN=<generate: `openssl rand -hex 16`>   # must match the shim's token
SUMMARY_USER_ID=1
```
> **No Groq / Telegram / Ollama keys.** If a sample `.env` lists them, leave them blank.

**5.2 — Start the backend**
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd ~/job-doot && docker compose up -d --build backend'
```
**Verify:** `curl -s localhost:8080/health` → `{"status":"ok"}`.
> **Changed `.env` later?** `docker compose restart` does **not** reload it — use
> `docker compose up -d --force-recreate backend`. (GOTCHAS: ".env changes ignored".)

**5.3 — Create your user** (admin), set your roles/cities for the scraper, and complete the
profile intake (your facts from §2). Follow the repo's user-creation + intake steps; make your
user an admin so you see the Admin tab.

---

## 6 · LinkedIn + the applier

> **Goal:** the applier logs into *your real LinkedIn* in its **own dedicated Chrome profile** and
> can apply. This is where most of our 2 days went — read the two traps carefully.

**6.1 — Two big Chrome traps (read first):**
- **Chrome 136+ refuses a remote-debug port on your *normal* logged-in profile** (anti-malware).
  So the applier uses a **dedicated profile directory** just for itself.
- **You cannot copy cookies from your everyday Chrome into it** (Chrome encrypts them per-profile —
  "App-Bound Encryption"). So you **log LinkedIn in by hand, once, inside the dedicated profile.**

**6.2 — Log your real LinkedIn into the applier's Chrome** (one time)
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'export DISPLAY=:0 WAYLAND_DISPLAY=wayland-0; google-chrome --user-data-dir=$HOME/.config/jobdoot-applier --remote-debugging-port=9223 --remote-debugging-address=127.0.0.1 https://www.linkedin.com/login'
```
A Chrome window opens (via WSLg). **✋ YOU — log into your real LinkedIn there.** Close it when done.
**Verify:** the profile folder now has LinkedIn cookies (`li_at`, `JSESSIONID`).

**6.3 — Your applier profile** — copy `deploy/*/profile.example.yaml` to
`applier/profiles/<you>.yaml` (this file is **git-ignored — it holds secrets**). Fill in:
- `browser_profile_dir: ~/.config/jobdoot-applier`, `debug_port: 9223`, `resume_pdf:` your PDF path.
- `daily_targets` — your cap (e.g. 15/day).
- `facts:` — your profile facts (name, email, phone, education, skills, notice, CTC, **address**…).
- `account_password:` — a strong password the applier uses to **create accounts** on company sites.
- `gmail_address:` + `gmail_app_password:` — so it can **read email OTP codes** (§2).

**6.4 — Put your resume PDF** where the profile points (`data/applier/<you>_resume.pdf`).

**6.5 — Smoke test** (safe, one slot):
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd ~/job-doot && export DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 && ~/.venvs/applier311/bin/python -m applier.run once --profile <you> --max 1'
```
Watch the log: it should open LinkedIn, fill an Easy Apply, and submit (or bank a question).
*(If it opens the wrong Chrome window, see GOTCHAS "applier opened another Chrome".)*

---

## 7 · Your phone: dashboard + widget over Tailscale

> **Goal:** open the dashboard and the widget on your phone from anywhere.

**7.1 — Find your PC's Tailscale IP** (looks like `100.x.x.x`): `tailscale ip -4`.

**7.2 — Forward it to the backend.** The backend listens inside WSL; Windows reaches it at the
IPv6 localhost. Forward your Tailscale IP's port 8080 to it (✋ admin PowerShell):
```powershell
netsh interface portproxy add v4tov6 listenaddress=<YOUR_TAILSCALE_IP> listenport=8080 connectaddress=::1 connectport=8080
netsh advfirewall firewall add rule name="job-doot 8080" dir=in action=allow protocol=TCP localport=8080
```
**Verify:** on your phone (Tailscale ON), open `http://<YOUR_TAILSCALE_IP>:8080` → the dashboard
loads; log in with your dashboard password. *(Why `::1`? See GOTCHAS "WSL localhost is IPv6".)*

**7.3 — iPhone widget:** open `http://<YOUR_TAILSCALE_IP>:8080/static/phone/setup.html`, tap
**Copy**, paste into the **Scriptable** app, add the medium widget.

---

## 8 · Going autonomous + always-on

**8.1 — Install the applier as a service** (runs daily, survives reboots):
```bash
wsl -d Ubuntu-24.04 -- bash -lc '
mkdir -p ~/.config/systemd/user && cp deploy/*/applier.service ~/.config/systemd/user/
# edit the copied file: set --profile <you>
systemctl --user daemon-reload && systemctl --user enable --now applier'
```
**Verify:** `systemctl --user is-active applier` → `active`. It schedules random slots within your
active hours and applies up to your daily cap. After each slot it writes health that the widget
shows (green normally, **red if Claude ever logs out**).

**8.2 — ✋ YOU — keep the PC on through reboots/power loss:**
- Power plan → **Sleep = Never**.
- **Auto sign-in after reboot** (so the applier's Chrome has a desktop) — Sysinternals *Autologon* or `netplwiz`.
- **BIOS → "Restore on AC power"** so it powers back on after an outage.
- Windows Update → set active hours so it won't reboot mid-day.

---

## 9 · Daily life (what's automatic, what needs you)

- **Automatic:** scrape → score (Claude) → tailor → apply (LinkedIn Easy Apply + company sites,
  **creating accounts and reading email OTPs** on its own) → update the dashboard/widget.
- **The Answers tab** (dashboard): when the applier hits a question it can't answer from your facts
  (e.g. "Address Line 1", "How did you hear about us?"), it **banks it here**, rewritten in plain
  language with an example. You answer once; it's reused forever.
- **CAPTCHAs** can't be auto-solved — the applier **leaves that tab open** so you just solve it.
- **`APPLICATION-QUESTIONS.md`** (repo root): a shared, growing list of every distinct question
  applications ask — so you (and teammates) can pre-answer ones you haven't hit yet.

---

## 10 · Reboot & recovery (once it's installed)

After a normal reboot, nothing should need reinstalling — just verify, top to bottom:
1. PC signed in (auto-login fired).
2. `wsl -d Ubuntu-24.04 -- systemctl is-active docker cron` → both `active`.
3. `docker ps` shows the backend up; `curl localhost:8080/health` OK.
4. `curl localhost:8099/health` OK (the brain shim).
5. `systemctl --user is-active applier` → `active`.
6. Dashboard loads over Tailscale; widget refreshes.

Any step down → the matching section above has the fix. Full reinstall only if WSL itself is gone (→ start at §3).

---

## 11 · Not on Windows?

The whole system is Linux-native — **Windows just hosts Linux via WSL.** So:
- **Linux / Raspberry Pi:** skip §3's WSL parts; everything from "systemd + user" onward runs directly. The applier services are plain `systemd --user` units.
- **macOS:** run Docker + the Python applier natively; you won't need WSL or the `netsh portproxy`
  (Tailscale reaches your Mac directly). Chrome's dedicated-profile + manual-login rule (§6.1) still applies.
- **The universal parts** (true everywhere): the Claude shim as the brain, the dedicated Chrome
  profile for the applier, the `.env` with no Groq/Telegram, the Answers tab, and the daily cap < 20.

Use this Windows guide as the **map**; swap only the host-specific plumbing (§3 WSL, §7 portproxy).

---

**That's it.** If you got stuck anywhere, it's almost certainly in [`GOTCHAS.md`](./GOTCHAS.md) —
we wrote down every single trap so your two days are two hours. Good luck. 🚀

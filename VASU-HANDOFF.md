# VASU — START HERE (guide for Vasu's Claude Code)

> **To Vasu's Claude:** this file was written by Tejas's Claude Code for you. Tejas and Vasu talk over WhatsApp, which is too clumsy for setup, so **this file + GitHub is how we talk.** Read all of it before touching anything. Then work through the phases **in order**, verify each checkpoint, and tell Vasu in plain language what you did and what he has to do by hand.
> If anything here doesn't match what you find on the machine, **stop and write it down in `deploy/vasu/STATUS.md` (section "Questions for Tejas"), commit and push.** Tejas's Claude reads that file and answers there.

---

## 0. What you're building, and a correction

**Goal:** Vasu's always-on Windows PC runs **exactly the system Tejas runs on his Raspberry Pi**, but for Vasu:

1. **Fetch jobs every day.** A dummy LinkedIn account's cookie is used to scrape. Jobs are scored per user by a local LLM (Ollama), and resumes are tailored per job (Groq).
2. **Auto-apply every day.** The apply agent (`applier/`) runs random "slots" through the day. It opens a real Chrome, moves the mouse with **ghost-cursor**, and **Claude Haiku** reads each page and decides the next step.
3. **Questions wait for Vasu.** When the agent meets a form question it can't answer from the facts, it stops that job and queues the question. The question shows up on the dashboard's **Needs you** page, on the bell, and on Telegram. Vasu answers once, the answer goes into the Q&A bank, and it's reused from then on.
4. **Same dashboard and phone widget as Tejas.** The web page is served from Vasu's PC and reached **only over Vasu's Tailscale**, plus an iPhone home-screen widget (Scriptable).

**Correction to what you told Vasu earlier.** You told him nothing fills forms, there's no cursor library and no model is wired in. That was true for the branch you were looking at (`main`). **The apply flow already exists.** It lives on Tejas's applier branches, and it's all merged into **this branch, `user/vasu-setup`**:

| Piece | File |
|---|---|
| Human-like mouse (ghost-cursor, bezier paths, typing rhythm) | `applier/human.py` (+ `_bezier_shim.py`) |
| Haiku page-reading agent (Sonnet on retry) | `applier/brain.py`, `applier/agent.py` |
| LinkedIn Easy Apply flow | `applier/easy_apply.py` |
| Company-site (offsite) apply | `applier/offsite.py` |
| Daily slots, targets, catch-up, test mode | `applier/run.py` |
| Real Chrome over CDP (no automation flags, `navigator.webdriver` false) | `applier/browser.py` |
| Q&A bank, attempts log | `applier/store.py` → `data/applier/applier.db` |
| LinkedIn account health check, safety pause | `applier/account_health.py`, `applier/safety.py` |
| Widget health file | `applier/health.py` → `data/applier/HEALTH.json` |
| Specs (read these, they explain the *why*) | `.claude/specs/apply-agent/approach.md`, `assumption.md`, `flaws.md` |

**Don't build a new apply flow, and don't switch to plain Playwright.** Ghost-cursor + Haiku is the combination Tejas picked, and it's live on his Pi. If you already started an "auth layer" for three sites, don't delete it: commit it to a branch called `vasu/auth-wip`, push it, and leave it parked. Your job is to **run and adapt** this system, not rewrite it.

---

## 1. The LinkedIn cap: under 20 a day (most important rule)

**Why.** Vasu and Tejas share a room and the same PG Wi-Fi. To LinkedIn, both machines are **one public IP**.

- A shared IP on its own is normal; hostels and offices do it all the time.
- What does get flagged is **two accounts on one IP, run by the same automation code, both applying at volume and at similar times.** That looks like one person running a bot farm. LinkedIn can link the accounts and restrict **both**, so if Vasu's account gets flagged, Tejas's can go with it, and the other way round.
- Tejas has stopped his own volume test at **20 LinkedIn applications a day**. Vasu stays **below 20 a day on LinkedIn (set 15)**. Together that's under 40 a day from this IP, which is the ceiling we're treating as safe.

| | Limit |
|---|---|
| LinkedIn applications | **under 20/day: `daily_targets` = 15** |
| Company sites / other platforms (not LinkedIn) | **no cap** from this rule |

**Rules:**
- **Code change you need to make.** Today the daily counter (`store.applied_since`, used by `today_progress` in `applier/run.py`) counts **every** application, including company-site ones. Make the `daily_targets` cap count **only LinkedIn applications**, so non-LinkedIn applications are never blocked by it. Write the change into `.claude/specs/apply-agent/approach.md` **first**, then the code (project rule: spec first).
- Never raise the LinkedIn number above 19 without Tejas.
- Keep slot hours offset from Tejas's. His run 09:00–22:00, with account checks at 08:30–08:55 and 22:50–23:15. The example profile already offsets Vasu's.
- **Never log into Tejas's LinkedIn on Vasu's PC, or Vasu's on Tejas's machine.** Use separate Chrome profiles, and never copy one across.
- **Any LinkedIn warning, CAPTCHA wall or "unusual activity" check means both appliers stop.** Tell Vasu to tell Tejas. Don't push through it.

---

## 2. Machine setup (Windows → WSL2)

Everything runs **inside WSL2 Ubuntu**, because the code assumes Linux. Windows only hosts WSL, Docker Desktop and Tailscale.

**Windows side (Vasu does these by hand; you give him the exact clicks):**
1. PowerShell (admin): `wsl --install -d Ubuntu`, then reboot. Check with `wsl -l -v`: Ubuntu should show **version 2**.
2. **Docker Desktop:** turn on Settings → Resources → WSL integration → Ubuntu, and Settings → General → "Start Docker Desktop when you sign in".
3. **Keep it running 24/7.** This is the hard part on Windows; the Pi just runs.
   - Power plan: sleep **Never**, hibernate off.
   - **Auto sign-in** after reboot or power cut (Sysinternals Autologon, or `netplwiz`). The applier's Chrome window needs a signed-in desktop because WSLg draws it.
   - Create `%UserProfile%\.wslconfig` containing:
     ```
     [wsl2]
     vmIdleTimeout=-1
     ```
     so WSL doesn't shut down when no terminal is open.
   - Task Scheduler: a task "At log on" running `wsl.exe -d Ubuntu --exec /bin/sh -c "sleep infinity"`, hidden, so WSL and its systemd services start after every reboot.
   - Windows Update: set active hours, or pause, so it doesn't restart mid-day.
4. **Tailscale** is already installed and signed in on the PC and on Vasu's iPhone (Tejas did this). Note the PC's Tailscale IP (`tailscale ip -4` in PowerShell). That's the address for the dashboard and the widget.

**Inside WSL Ubuntu:**
1. Turn on systemd: put `[boot]` and `systemd=true` in `/etc/wsl.conf`, run `wsl --shutdown` from PowerShell, then reopen Ubuntu. Then run `sudo loginctl enable-linger $USER` and `sudo systemctl enable --now cron`.
2. Check WSLg works: `echo $WAYLAND_DISPLAY $DISPLAY` should print `wayland-0 :0`.
3. **Google Chrome (.deb), not apt `chromium`.** Ubuntu's chromium is a snap, and snaps don't run properly in WSL.
   ```
   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install -y ./google-chrome-stable_current_amd64.deb
   ```
4. Python **3.11** venv for the applier (it matches the Docker image and the Pi): `uv venv -p 3.11 ~/.venvs/applier311` (or deadsnakes), then `~/.venvs/applier311/bin/pip install -r requirements.txt`. You don't need `playwright install`, because the applier drives the real Chrome over CDP.
5. **Claude Code inside WSL**, logged in with Vasu's subscription. Find its path with `which claude` and put it in the profile as `claude_bin`. The applier calls `claude -p --model haiku` for every page, which uses **Vasu's** Claude quota.
6. **Ollama** (the scorer runs `gemma3:4b` locally): install Ollama, run `ollama pull gemma3:4b`, and check the backend container can reach it:
   ```
   docker exec jobhunter-backend python -c "import urllib.request;print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags').read()[:80])"
   ```
   If that fails, change `OLLAMA_URL` in `.env`, or make Ollama listen on `0.0.0.0`.

**Code checkout. Use one checkout for everything.** On the Pi the dashboard and the applier are two checkouts; here it's one.
```
git clone -b user/vasu-setup https://github.com/TejasKashyap7/job-doot.git ~/job-doot
```
**Clone it inside the Linux home (`~`), never under `/mnt/c`.** That's slow and breaks file permissions.

✅ **Checkpoint 2:** `docker --version`, `google-chrome --version`, `~/.venvs/applier311/bin/python -c "import playwright, python_ghost_cursor"` and `claude -p "say ok" --model haiku` all work inside WSL.

---

## 3. Secrets and accounts (all Vasu's own; never Tejas's)

Create `~/job-doot/.env` from `.env.example`. It needs every key that Tejas's Pi uses:

```
GROQ_API_KEY=            # Vasu's Groq key (tailoring). console.groq.com
GROQ_MODEL=allam-2-7b    # what Tejas's Pi uses
TELEGRAM_BOT_TOKEN=      # Vasu's own bot (@BotFather) — deploy + alert messages
TELEGRAM_CHAT_ID=
DASHBOARD_PASSWORD=
SESSION_SECRET=          # long random string
GOOGLE_CREDENTIALS_PATH=/app/data/credentials.json
GOOGLE_TOKEN_PATH=/app/data/token.json
SCHEDULER_TIMEZONE=Asia/Kolkata
SCRAPE_HOUR=6
SCRAPE_MINUTE=0
JOBS_CSV_PATH=/app/dummy_jobs.csv
DATABASE_URL=sqlite:////app/data/jobs.db
WIDGET_KEY=              # long random string — the phone widget sends it
LINKEDIN_EMAIL=          # dummy FETCH account (Tejas is setting it up)
LINKEDIN_PASSWORD=
WEBHOOK_SECRET=          # random
```

`SETUP.md` walks through the Groq, Telegram and Google OAuth steps. For Google: Vasu needs his own Google Cloud OAuth client. Put `credentials.json` in `data/`, then run `tools/oauth_bootstrap.py` once to create `data/token.json`.

**Two LinkedIn accounts, for two different jobs:**

| Account | Used for | Where it goes |
|---|---|---|
| **Fetch account** (dummy; **Tejas is creating it**) | scraping job lists | its `li_at` cookie goes in `data/li_cookies.json` (`{"li_at": "..."}`) or is pasted on the dashboard page `/admin/linkedin-cookie` |
| **Apply account** | applying | logged in **once by hand** inside the applier's Chrome profile (`~/.config/jobdoot-applier`). Phase A = dummy/test account, Phase B = Vasu's real account |

Never put the fetch account and the apply account in the same Chrome profile.

---

## 4. Start the backend + first user (fresh-install bootstrap)

```
cd ~/job-doot && docker compose up -d --build && curl -fsS localhost:8080/health
```

**Known gap:** on a **fresh** database there are no users, and `/signup` needs an invite token, which normally an admin creates. (Tejas's admin user was created by a one-off migration from his old database. That migration does nothing on a fresh install.) Bootstrap it once, without changing any code:

1. Create the invite token:
   ```
   docker exec jobhunter-backend python -c "
   import secrets; from database.db import SessionLocal; from database.models import InviteToken
   db=SessionLocal(); t=secrets.token_urlsafe(24); db.add(InviteToken(token=t,label='vasu')); db.commit(); print(t)"
   ```
2. Prepare Vasu's **profile export + LaTeX resume** by running the intake interview in `.claude/specs/multi-user/intake-prompt.md`. Run it with Vasu, verify his claims against his real repos, and **don't invent anything**.
3. Open `http://localhost:8080/signup?token=<token>`, create user `vasu`, paste the export and upload the `.tex`.
4. Make him admin:
   ```
   docker exec jobhunter-backend python -c "
   import sqlite3; c=sqlite3.connect('/app/data/jobs.db'); c.execute(\"UPDATE users SET is_admin=1 WHERE username='vasu'\"); c.commit(); print(c.execute('select id,username,is_admin from users').fetchall())"
   ```
   Note his `id` (it'll be 1). That's `pick_jobs_from_user_id` and `notify_user_id` in his applier profile.
5. Log in and check. His Telegram bot and chat ID, and his Groq key(s), are **part of the profile export** (`telegram:` and `groq_keys:` in the intake schema). There's no separate settings page, so get them right in the export.

**Scrape keywords.** `KEYWORDS` and `LOCATIONS` in `backend/services/scraper.py` are Tejas's: AI/ML roles in Gurgaon, Delhi, Noida, Pune and Remote. Ask Vasu which roles and cities he wants. Change them spec-first (`.claude/specs/scraper/`), then the code.

✅ **Checkpoint 4:** Vasu can log in at `http://localhost:8080`. Once the fetch account's `li_at` cookie is in place, the backend's LinkedIn fetch loop (`linkedin_drip_loop` in `backend/services/scraper.py`, a continuous background loop, not a single run) brings in jobs: watch `docker logs -f jobhunter-backend`. Scores appear on `/jobs` within `SCORE_INTERVAL_MIN` (20 min). (`/admin/trigger-scrape` only loads the CSV file; it doesn't scrape LinkedIn.)

---

## 5. The applier

1. `cp deploy/vasu/vasu.yaml.example applier/profiles/vasu.yaml` (the profiles folder is git-ignored). Fill in `facts` **truthfully** with Vasu, and check `claude_bin` and `chromium`. Put his resume PDF at `data/applier/vasu_resume.pdf`.
2. Log the **apply** account in once. Start Chrome with the applier's own profile:
   ```
   google-chrome --user-data-dir=$HOME/.config/jobdoot-applier --password-store=basic
   ```
   Log into LinkedIn, then close Chrome.
3. **WSL-specific risk.** `applier/browser.py` launches Chrome with `--ozone-platform=wayland` and defaults to `WAYLAND_DISPLAY=wayland-0`. WSLg supports Wayland, so it should work. If Chrome won't open its debug port, make the ozone flag configurable (spec first) and use `x11` with `DISPLAY=:0`. **Keep the Pi's default unchanged.**
4. Try it by hand first:
   ```
   cd ~/job-doot && ~/.venvs/applier311/bin/python -m applier.run status --profile vasu
   ~/.venvs/applier311/bin/python -m applier.run look --profile vasu --url <a LinkedIn job URL>    # Haiku's plan, no clicks
   ~/.venvs/applier311/bin/python -m applier.run once --profile vasu --max 1                      # one real slot
   ```
5. Install the service: follow the header of `deploy/vasu/applier.service`. Then check `systemctl --user status applier` and `journalctl --user -u applier -f`.
6. **Questions loop.** Unanswered questions appear on `/needs-you` and on the bell. From the CLI:
   ```
   python -m applier.run qa --profile vasu
   python -m applier.run answer --profile vasu ID "text"
   ```
   In **Phase A (test mode)** the agent makes up answers for unknown questions and *records* them. **Only the collected questions matter, not the answers**, so don't "fix" made-up answers.

**Phase A to Phase B.** Phase A is a dummy apply account with `test_mode: true`, the way Tejas tested his own. Phase B is Vasu's real account with `test_mode: false` and `min_score: 7`. **Switch to Phase B only when Tejas and Vasu both say go.**

✅ **Checkpoint 5:** one slot applies (or cleanly stops with a reason), `data/applier/HEALTH.json` updates, and the attempt shows on the dashboard.

---

## 6. Dashboard over Tailscale + phone widget

- **Dashboard:** `http://<PC tailscale IP>:8080` from Vasu's iPhone (Tailscale on). Docker Desktop publishes port 8080 on Windows. If the phone can't reach it, allow inbound TCP 8080 in Windows Firewall, **for the Tailscale interface only**. **No port-forwarding and no public tunnel**: Tailscale only, same as Tejas.
- **Widget:** Scriptable is already on his iPhone. In Scriptable, tap +, paste `tools/phone/jobdoot_loader.js`, and change exactly two lines:
  - `const PI = "http://<PC tailscale IP>:8080"`
  - `const KEY = "<WIDGET_KEY from .env>"`

  Name the script `job-doot` and tap play. Then long-press the home screen, tap +, choose Scriptable, Medium, Edit Widget and pick `job-doot`. The loader downloads the real widget code from his PC on every refresh, so widget updates arrive by themselves. **Don't commit his IP or key.**
- **Termius** (already on his iPhone) is for SSHing into the PC to fix things away from home, such as `claude /login` if Claude logs out. Recommended: Windows OpenSSH Server with key-only login, reached at the PC's Tailscale IP, then run `wsl`. Set it up with Vasu and keep password login off.

✅ **Checkpoint 6:** with Wi-Fi turned off on his iPhone (mobile data + Tailscale), the dashboard loads and the widget shows today's numbers.

---

## 7. Auto-deploy (so Tejas can ship fixes through GitHub)

`deploy/vasu/job-doot-deploy.sh` is Tejas's Pi poller, adapted. Every 3 minutes it checks `origin/user/vasu-setup`. On a new commit it pulls, rebuilds, health-checks and rolls back on failure. It restarts the applier if `applier/` changed, and sends the result to Vasu's Telegram. It **skips** if this checkout has uncommitted or unpushed work, so it never wipes your edits. Install it with the command in its header.

**Git workflow on this branch:**
- Commit and push your changes to `user/vasu-setup` soon after making them. Don't leave the working tree dirty.
- **Never push to `main`, `applier` or `applier-volume-test`.** Those are Tejas's live Pi branches, and his Pi auto-deploys `main`.
- Never commit `.env`, `data/`, `applier/profiles/*.yaml`, IPs or keys. They're git-ignored; keep it that way.
- To get Tejas's newer fixes, Tejas merges them into this branch. If you think his code has a bug, write it in `STATUS.md` rather than patching it silently.

---

## 8. Ignore Tejas's personal files

`.claude/research/`, `backend/master_resume.tex`, `backend/database/seed_tejas.py`, `reports/` and `tools/sync_private_to_pi.sh` are Tejas's profile, resume and Pi tooling. **Don't use his profile or resume for Vasu**, and don't edit them. Vasu's profile comes from the intake interview (§4).

`CLAUDE.md` has Tejas's Mac paths (conda env and so on). Its project rules still apply here: **spec first, pinned `requirements.txt`, never touch `master_resume.tex`, the locked skill set marks things UNFIXABLE instead of inventing them**. On this PC, the WSL venv `~/.venvs/applier311` plus Docker replaces his conda env.

---

## 9. Report back

Keep `deploy/vasu/STATUS.md` up to date (create it): which checkpoints pass, what's blocked, and a "Questions for Tejas" section. Commit and push it after each phase. That's the channel between the two Claudes.

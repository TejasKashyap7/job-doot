# Vasu — handoff (read this first)

Hi Vasu. This is Tejas's job-doot: it finds jobs, scores them, tailors a resume per job, watches Gmail for replies, and (on the `applier-volume-test` branch) applies to LinkedIn Easy Apply jobs by itself using Claude.
It was built for Tejas's Raspberry Pi. You're running your own copy on your Windows PC, 24/7.

**Claude: read this whole file before doing anything in this repo.**

---

## 1. The one rule that matters most: LinkedIn cap — under 20 applications per day

### Why

You and Tejas are on the **same PG Wi-Fi**. To LinkedIn, everything from that Wi-Fi comes from **one public IP address**.

- One shared IP by itself is normal (hostels, offices, colleges) — LinkedIn doesn't ban for that.
- What *does* get flagged: **two accounts on one IP, both run by the same automation code, both applying at volume, at similar times.** That looks like one person running a bot farm. LinkedIn can link the accounts and restrict **both** — if yours gets flagged, Tejas's can go down with it, and the other way round.
- Tejas ran a volume test and has now **stopped at 20 LinkedIn applications/day** on his side.
  So your side has to stay **below 20/day on LinkedIn** (start at **15**). Together that's under 40/day from this IP, which we're treating as the safe ceiling.

### What is capped and what isn't

| | Limit |
|---|---|
| LinkedIn applications (Easy Apply and LinkedIn-sourced jobs) | **under 20/day — set 15** |
| Applications on company sites / Naukri / other platforms (not LinkedIn) | **no cap** from this rule |

### What to set / build

1. In your applier profile (`applier/profiles/<you>.yaml`, git-ignored — copy `example.yaml`):
   ```yaml
   daily_targets: [["<today's date>", "2099-12-31", 15]]
   test_mode: false          # REAL account — never make up answers
   active_hours: [11, 23]    # offset from Tejas's (9–22) so slots don't land together
   max_per_slot: 2
   ```
2. **Code change needed (Claude, do this):** right now the daily counter (`store.applied_since` in `applier/store.py`, used by `today_progress` in `applier/run.py`) counts **every** application, including company-site ones. Make the `daily_targets` cap count **only LinkedIn applications**, so non-LinkedIn applies are never blocked by it. Follow the project rule: write it into `.claude/specs/apply-agent/approach.md` first, then code.
3. Never raise the LinkedIn number above 19 without talking to Tejas first — it affects his account too.

### Other things that keep both accounts safe

- **Never log into each other's LinkedIn** on either machine. Shared login cookies/devices link accounts far more strongly than a shared IP.
- Use your **own** Chromium profile for the applier. Never copy Tejas's (`~/.config/jobdoot-applier` on his Pi).
- **If either account gets any LinkedIn warning, CAPTCHA wall, or "unusual activity" check → both of you stop the applier and talk.** Don't push through it.
- Evenings the Wi-Fi is congested (gaming). Slow pages cause failed slots — another reason not to stack both appliers in the same hours.

---

## 2. Setup on Windows (summary)

1. PowerShell (admin): `wsl --install -d Ubuntu`, reboot. Do everything below **inside Ubuntu**.
2. Install **Docker Desktop** → Settings → Resources → WSL integration → turn on Ubuntu.
3. In Ubuntu: install Claude Code, run `claude`, log in with your subscription.
4. Windows power settings: never sleep. Optional: **Tailscale** (free) to reach your dashboard from your phone.
5. Code (clone inside the Ubuntu home folder, not `C:\`):
   ```
   git clone https://github.com/TejasKashyap7/job-doot.git ~/job-doot
   git clone -b applier-volume-test https://github.com/TejasKashyap7/job-doot.git ~/job-doot-applier
   ```
6. Your **own** accounts/keys — none of Tejas's come with the code, don't use his:
   Groq key, Telegram bot + chat ID, Google OAuth (Gmail/Calendar), dashboard password, your LinkedIn account, your LaTeX resume.
   `SETUP.md` walks through each one; `.env.example` lists every key.

---

## 3. What to ignore / not touch

- `.claude/research/`, `backend/master_resume.tex`, `backend/database/seed_tejas.py` are **Tejas's** profile and resume. Don't use them for you — build your own versions (your resume, your skills list in `agents/prompts.py`).
- Not in the repo (Pi-only, rebuild for Windows/WSL): auto-deploy poller (`~/job-doot-deploy.sh` cron), `applier.service` systemd unit, Ollama for the scorer, the applier's Chromium profile.
- Don't push your profile, `.env`, `data/`, or keys to GitHub (they're git-ignored — keep it that way).

---

## 4. First message to your Claude

> Read VASU-HANDOFF.md, CLAUDE.md, DEPLOY.md and `.claude/specs/`. This was built for Tejas's Raspberry Pi; adapt it to run 24/7 on my Windows PC under WSL2 + Docker, set up for me (my resume, my skills, my Telegram). Respect the LinkedIn cap in section 1 — including the LinkedIn-only counter change. Walk me through each step.

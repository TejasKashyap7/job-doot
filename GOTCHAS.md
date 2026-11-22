# GOTCHAS — every trap we hit, and the exact fix

> Companion to [`START-HERE.md`](./START-HERE.md). These are the real walls that cost us time over
> two days of setup. Each entry: **symptom → why → fix.** Skim the headings; jump to yours.

---

## Chrome & the applier

### Chrome 136+ ignores the remote-debugging port on your normal profile
**Symptom:** you launch Chrome with `--remote-debugging-port=...` on your everyday (logged-in)
profile and the applier can't connect / the port never opens.
**Why:** Chrome 136+ deliberately disables the debug port on the **default profile** as an
anti-malware measure.
**Fix:** always use a **dedicated profile directory** for the applier
(`--user-data-dir=~/.config/jobdoot-applier`). The debug port works there. This is why the applier
has its *own* Chrome profile, separate from your personal browsing.

### You can't copy cookies from your normal Chrome into the applier's profile
**Symptom:** you try to copy the `Cookies` DB from your main Chrome so the applier is "already
logged in" — it doesn't work, or a security tool flags it.
**Why:** Chrome encrypts cookies per-profile ("App-Bound Encryption"); a copied DB is unreadable in
another profile, and the copy pattern looks like credential theft.
**Fix:** **log in by hand, once, inside the dedicated profile** (START-HERE §6.2). Don't copy cookie
databases between profiles — ever.

### The applier opened "another Chrome" (the wrong window)
**Symptom:** you log into LinkedIn, but the applier seems to use a different, logged-out Chrome.
**Why:** a Chrome already running on that profile (without the debug port) "swallows" the new launch,
or you logged into your *personal* profile, not the applier's.
**Fix:** kill all Chrome, then launch **only** the dedicated profile with the debug port:
`pkill -f 'user-data-dir=.*jobdoot-applier'; sleep 2; google-chrome --user-data-dir=~/.config/jobdoot-applier --remote-debugging-port=9223 ...`. Confirm `li_at` is in that profile's cookie DB.

### CAPTCHA jobs can't be automated
**Symptom:** a company site shows an "I'm not a robot" / image challenge and the applier stops.
**Why:** CAPTCHAs exist to stop bots; solving them needs paid third-party services that violate site
terms and can get your account flagged.
**Fix:** this is a hard wall — the applier **leaves that tab open** (with your details already filled)
so you solve the CAPTCHA yourself and submit. Don't try to defeat it.

### Email OTP works only for inbox codes, not spam
**Symptom:** a site emails a verification code but the applier says it couldn't find it.
**Why:** the OTP reader uses Gmail over IMAP and reads only your **Inbox** — codes Gmail files as
**Spam** aren't visible (by design/security). Some sites also send a verification *link*, not a code.
**Fix:** for spam-filtered codes, glance at your Spam folder and answer that one by hand; whitelist
the sender. Most codes land in the inbox and auto-fill fine.

---

## Docker & the backend

### Changes to `.env` don't take effect
**Symptom:** you edit `.env` (e.g. the dashboard password) and nothing changes after a restart.
**Why:** `docker compose restart` reuses the existing container and does **not** re-read `.env`.
**Fix:** `docker compose up -d --force-recreate backend` (or `up -d --build`). A restart alone won't do it.

### Backend code changes don't appear
**Symptom:** you edit a file under `backend/` but the running site is unchanged.
**Why:** the backend **source is baked into the Docker image**; only `data/`, `pdfs/`, and a couple
files are volume-mounted. Editing the host file doesn't touch the container.
**Fix:** for a quick test, `docker cp <file> jobhunter-backend:/app/backend/<path>` then
`docker restart jobhunter-backend`. To make it **permanent**, rebuild: `docker compose up -d --build backend`
(this bakes your host changes into the image). Your `data/` — database, saved answers — is mounted,
so it **survives every rebuild**.

### Two backends fighting over port 8080
**Symptom:** the dashboard behaves weirdly / your password doesn't work / the phone reaches a
different site than your PC.
**Why:** an older install (e.g. a Windows-native one from a previous attempt) is also bound to 8080,
so you're hitting the wrong backend with the wrong credentials.
**Fix:** find what owns the port (`Get-NetTCPConnection -LocalPort 8080`) and shut down the stale one
(disable its scheduled tasks / stop its process). Run **one** backend. Pick WSL as canonical.

---

## WSL, networking, Python

### systemd isn't running inside WSL
**Symptom:** `systemctl` commands fail; user services won't install.
**Why:** WSL doesn't enable systemd by default.
**Fix:** put `[boot]\nsystemd=true` in `/etc/wsl.conf`, then `wsl --shutdown` from PowerShell and
reopen. Verify `systemctl is-system-running` → `running`.

### Your phone can't reach the dashboard, but the PC can ("WSL localhost is IPv6")
**Symptom:** `http://<tailscale-ip>:8080` times out on the phone, though `localhost:8080` works on the PC.
**Why:** WSL forwards the container's port to the **IPv6** localhost (`::1`), not the IPv4 Tailscale
interface. A normal IPv4 port-forward points at nothing.
**Fix:** forward IPv4→IPv6: `netsh interface portproxy add v4tov6 listenaddress=<tailscale-ip>
listenport=8080 connectaddress=::1 connectport=8080`, and allow TCP 8080 in the firewall.

### `pip` is missing / `python -m pip` errors with a Windows path
**Symptom:** `.../bin/pip: No such file or directory`, or `python -m pip` fails with
`C:/Program...: No such file or directory`.
**Why:** the `uv`-made venv has no standalone `pip`, and WSL's Windows-PATH interop can make
`python -m pip` try to exec a Windows program.
**Fix:** use `uv` for packages: `uv pip install <pkg>`, or for a one-off script
`uv run --with <pkg> python ...`. Don't fight `pip` directly in a uv venv.

### `claude: command not found` after installing the CLI
**Symptom:** the Claude CLI installs but isn't on PATH.
**Why:** WSL doesn't add `~/.local/bin` to PATH by default.
**Fix:** append `export PATH="$HOME/.local/bin:$PATH"` to both `~/.bashrc` and `~/.profile`, then
open a **fresh** terminal.

### Cloning into `/mnt/c` is slow and breaks permissions
**Symptom:** git / Docker / the venv are painfully slow or hit permission errors.
**Why:** `/mnt/c` is the Windows filesystem seen through a translation layer — slow, wrong perms.
**Fix:** clone into the **Linux home** (`~/job-doot`), never under `/mnt/c`.

---

## Git

### `git push` denied / pushes as the wrong account
**Symptom:** `403` on push, or commits show someone else's GitHub name.
**Why:** a cached GitHub credential belongs to a different account, and/or `git config user.email`
isn't yours.
**Fix:** make sure the repo owner added **your** GitHub account as a collaborator, set the push
credential to your account (`gh auth login` or the credential manager), and set your commit identity
(`git -c user.name=... -c user.email=... commit`). Push only the files you changed — not the whole tree.

### A huge diff of files you didn't touch (line-ending churn)
**Symptom:** `git status` shows hundreds of modified files you never edited.
**Why:** CRLF↔LF line-ending differences between Windows and Linux.
**Fix:** confirm it's whitespace-only with `git diff --ignore-all-space` (empty = just line endings).
Add a `.gitattributes` (`* text=auto`) and/or set `core.autocrlf`. When committing, **`git add` only
the specific files you meant to change**, so churn never sneaks into a commit.

### Don't commit secrets
**Symptom:** worry that your logins end up on GitHub.
**Why:** the applier profile (`applier/profiles/<you>.yaml`) holds your `li_at`, Gmail app password,
account password, and personal facts; `.env` holds your dashboard password.
**Fix:** both are **git-ignored** — keep them that way. Before any commit, `git check-ignore
applier/profiles/<you>.yaml .env` should list them (meaning ignored). Never `git add -A` blindly;
delete stray backups like `*.yaml.bak` (not ignored) before committing.

---

## The brain (Claude shim)

### Scoring/tailoring stalls or the widget goes red
**Symptom:** jobs fetch but never score; or the widget shows "Claude logged out".
**Why:** the Claude CLI login expired, or the shim service isn't running.
**Fix:** `curl localhost:8099/health` — if it's down, `systemctl --user restart claude-shim`. If it
says logged out, run `claude` in a terminal and log in again. Backend reaches the shim at
`host.docker.internal:8099` (already in the compose `extra_hosts`).

---

_Add new traps here as you hit them — future-you (and the next newcomer) will thank you._

# Telegram Cleanup — Flaws

---

## FLAW-1: Leaving too fast triggers Telegram FLOOD_WAIT ban
**Status: OPEN — must handle before running the script**

**The problem:**
Telegram's MTProto API enforces rate limits on account actions. Leaving channels
too quickly triggers a `FLOOD_WAIT` error that temporarily bans the account from
performing further actions (the wait can be anywhere from 30 seconds to several
hours depending on how aggressively you hit the limit). If the script doesn't
handle this, it crashes mid-run and you're left with a partially cleaned account
and a temporarily locked one.

**Example:**
You have 200 spam channels to leave. Script starts leaving them one per second.
After 30 leaves, Telegram throws `FLOOD_WAIT_X` where X = 3600 (wait 1 hour).
Script crashes. You're now halfway through cleanup, account is rate-limited, and
you have to wait an hour to continue. Meanwhile the bot can't send alerts either
because the same account is flood-waited.

**Options:**
- **Option A — Fixed 2s delay between each leave + catch FLOOD_WAIT and sleep.**
  2 seconds is conservative and safe. If FLOOD_WAIT still triggers (unlikely at 2s),
  catch the exception, print "Telegram wants us to wait Xs — sleeping...", sleep
  for the specified duration, then continue. Script never crashes.
- **Option B — Run in batches of 20 with a 60s pause between batches.**
  Even more conservative. 200 channels = 10 batches = ~12 minutes total.
  Zero risk of flood-wait. Boring but bulletproof.
- **Option C — Option A as default, with `--slow` flag for Option B.**
  Normal users get 2s delay. If they've had issues before, run with `--slow`.

---

## FLAW-2: Script might leave a channel you actually wanted to keep
**Status: OPEN — mitigated by the confirmation step, but worth being explicit**

**The problem:**
The cleanup is irreversible in the moment — once you leave a channel, its message
history is gone from your client and re-joining (if even possible for private channels)
means starting fresh. An accidental leave of a college group or a useful dev community
is annoying to undo.

**Example:**
You have a group called "AI Engineers India" with 15,000 members. You've never sent
a message there but you lurk and read it regularly. The script flags it as spam
(large + no sent messages). You miss it in the confirmation list and leave it.
Group was invite-only. You can't rejoin.

**Options:**
- **Option A — Always require per-item confirmation for groups < 5,000 members.**
  Large public channels (>50K members) can be bulk-left. Smaller ones always ask
  individually. This is what the script does by default.
- **Option B — Add a `--safe` flag that only leaves channels > 100,000 members**
  and have never-interacted. Ultra conservative — only the most obvious mass-spam
  gets removed. Run `--safe` first, then review remaining and do manual passes.
- **Option C — Print the full list to a file before doing anything.** User reviews
  the file, comments out any lines they want to keep, then re-runs with the file
  as input. Slowest but most auditable.

---

## FLAW-3: Telethon session file is sensitive and must never be committed
**Status: OPEN — simple gitignore rule, just don't forget**

**The problem:**
Telethon saves your authenticated session to `tools/session_cleanup.session`.
This file is equivalent to being logged into your Telegram account — anyone with
this file can read your messages, send messages as you, and access all your chats.
If committed to git (even once, even in a private repo), it's compromised.

**Example:**
You forget the session file exists, run `git add .`, commit, push. Even if you
delete it in the next commit, git history retains the file. Anyone with repo access
can extract it and log into your Telegram.

**Options:**
- **Option A — Add `*.session` and `tools/*.session` to `.gitignore` right now,**
  before writing the script. Also delete the session file after each cleanup run
  (add a reminder print at the end of the script: "Run complete. Delete
  tools/session_cleanup.session now.").
- **Option B — Store the session file outside the repo directory entirely.**
  Pass the path as a CLI arg: `python tools/telegram_cleanup.py --session ~/tg_cleanup`.
  Zero chance of accidental commit.
- **Option C — Both A and B.** Gitignore as safety net + out-of-repo path as default.

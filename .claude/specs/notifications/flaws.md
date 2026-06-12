# Notifications — Flaws

---

## FLAW-1: Telegram alerts are invisible — buried under channel noise
**Status: OPEN — resolve before going live, otherwise real recruiter responses go unnoticed**

**The problem:**
The bot sends a direct message to the configured Telegram CHAT_ID. But because the
user has joined hundreds of high-traffic channels (movie groups, spam groups, etc.),
Telegram notifications are either muted entirely or drowned out. A REAL_RESPONSE
alert arrives, gets a notification badge, and disappears into the noise within seconds.

**Example:**
A recruiter from Razorpay emails you for an interview. The Gmail watcher catches it,
classifies it REAL_RESPONSE, fires the Telegram DM. At that exact moment your phone
shows 47 other Telegram notifications from movie channels. You don't see it. You
miss the recruiter's 2-day response window. They move to the next candidate.
The whole pipeline worked perfectly and still failed to help you.

**Ruled out:**
- Discord — user does not want to involve their Discord account
- WhatsApp — user does not want to involve their personal WhatsApp

**Decision: Stay on Telegram, but first clean it up with a Telethon script.**

Telegram bot DMs are actually the right channel. The problem is not Telegram itself —
it's that the account is buried under hundreds of spam channels making all notifications
invisible. The fix is to mass-leave the junk channels so the DM from the bot stands out.

**How:**
Telethon is a Python library that authenticates as the *user* (not a bot) using the
Telegram MTProto API. We build a one-time utility script (`tools/telegram_cleanup.py`)
that:
1. Logs in as the user via phone number + OTP (one-time, interactive)
2. Lists every channel/group the account has joined, with member count and last activity
3. Prints the list for review
4. On confirmation, leaves all flagged channels in batches (to avoid Telegram's
   flood-wait limits — ~1 leave per 2s)

After cleanup, the bot DM approach works as designed. No code change needed in
`services/telegram.py` — the bot integration stays exactly as-is.

**Status of Telegram bot code:** Already built and working. No changes needed there.

**What needs to be built:** `tools/telegram_cleanup.py` — tracked as a separate task,
to be done when we reach the notifications milestone. Not part of the main pipeline.
See `notifications/approach.md` for what the bot code looks like once cleanup is done.

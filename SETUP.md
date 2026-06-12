# Job Hunter — Setup Handoff

Self-contained guide. Do these in any chat or alone. When everything in the **DONE checklist** at the bottom is ticked, come back to Claude Code and we resume building.

Project root on your Mac: `/Users/tejas/Documents/job-doot`

---

## 1. Groq API key (2 min)

1. Go to https://console.groq.com/keys
2. Sign in with Google (use `tejas06012005@gmail.com`)
3. Click **Create API Key** → name it `job-hunter` → copy the key (shown once)
4. Paste it into `.env`:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
   ```

Free tier: Llama 3.3 70B at ~30 requests/min, ~14k tokens/min. Enough for our pipeline (3-second delay between scorer calls is built in).

---

## 2. Telegram bot (5 min)

### Get the bot token
1. Open Telegram, search **@BotFather**, start chat
2. Send `/newbot`
3. Bot name: `Job Hunter Tejas` (anything)
4. Username: must end in `bot`, e.g. `tejas_jobhunter_bot`
5. BotFather replies with a token like `7891234567:AAH...long-string...`
6. Paste into `.env`:
   ```
   TELEGRAM_BOT_TOKEN=7891234567:AAH...
   ```

### Get your chat ID
1. In Telegram, **send any message to your new bot** (e.g. "hi"). This is required — Telegram won't reveal your chat ID until you message the bot first.
2. In a browser, open (replace `<TOKEN>` with the actual token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Find `"chat":{"id": 123456789, ...}` in the JSON. That number is your chat ID.
4. Paste into `.env`:
   ```
   TELEGRAM_CHAT_ID=123456789
   ```

### Quick test (optional but recommended)
Replace `<TOKEN>` and `<CHAT_ID>` and paste in terminal:
```
curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=hello+from+job+hunter"
```
You should get a Telegram notification within seconds. If yes — Telegram is wired.

---

## 3. Dashboard password

Just pick anything. You're the only user. Edit `.env`:
```
DASHBOARD_PASSWORD=pick-something-you-remember
```

`SESSION_SECRET` is already filled with a random value — don't touch it.

---

## 4. Google Cloud — OAuth for Gmail + Calendar (10 min)

This is the longest part but only done once.

### 4a. Create a GCP project
1. Go to https://console.cloud.google.com/projectcreate
2. Project name: `job-hunter`
3. Location: leave as "No organization"
4. Click **Create**, wait ~10 seconds for it to finish
5. **Make sure the project selector at the top of the page now shows `job-hunter`** (top bar, next to the Google Cloud logo). If it doesn't, click the selector and pick it.

### 4b. Enable the two APIs
1. Go to https://console.cloud.google.com/apis/library
2. Search **Gmail API** → click it → **Enable**
3. Go back to the library, search **Google Calendar API** → click → **Enable**

### 4c. Configure the OAuth consent screen
1. Go to https://console.cloud.google.com/apis/credentials/consent
2. User Type: **External** → **Create**
3. **App information** page:
   - App name: `job-hunter`
   - User support email: `tejas06012005@gmail.com`
   - Developer contact email (bottom): `tejas06012005@gmail.com`
   - All other fields: leave blank
   - Click **Save and Continue**
4. **Scopes** page: don't add anything, just click **Save and Continue** (we declare scopes in code)
5. **Test users** page:
   - Click **+ Add Users**
   - Enter `tejas06012005@gmail.com` → **Add**
   - Click **Save and Continue**
   - **CRITICAL** — without this step Google will refuse the OAuth flow with "access blocked"
6. **Summary** page: click **Back to Dashboard**

#### Optional but useful: publish the app
By default the app is in **Testing** mode → refresh tokens expire after 7 days. You'll have to re-run the OAuth bootstrap weekly. To avoid this:
- On the OAuth consent screen page, click **Publish App** → confirm
- Ignore the "verification not required for personal use" notice
- Tokens now last indefinitely until manually revoked

You can do this now or later — both work.

### 4d. Create the OAuth client (the credentials.json file)
1. Go to https://console.cloud.google.com/apis/credentials
2. Click **+ Create Credentials** at the top → **OAuth client ID**
3. Application type: **Desktop app** (NOT Web app — desktop is required for our flow)
4. Name: `job-hunter-desktop`
5. Click **Create**
6. A popup appears with Client ID + Client Secret. Click **Download JSON** (top right of popup, or the download icon next to the client in the list)
7. The downloaded file will have a long name like `client_secret_xxxxx.apps.googleusercontent.com.json`. **Rename it to `credentials.json`** and move it to:
   ```
   /Users/tejas/Documents/job-doot/data/credentials.json
   ```
   Terminal command if easier:
   ```
   mv ~/Downloads/client_secret_*.json /Users/tejas/Documents/job-doot/data/credentials.json
   ```

### 4e. Run the OAuth bootstrap (generates token.json)
In terminal:
```
cd /Users/tejas/Documents/job-doot
.venv/bin/python tools/oauth_bootstrap.py --test
```

What happens:
1. Browser opens, asks you to pick a Google account → pick `tejas06012005@gmail.com`
2. You'll see **"Google hasn't verified this app"** → click **Advanced** at the bottom → **Go to job-hunter (unsafe)**. This is normal for personal/unpublished apps.
3. Permission screen lists Gmail + Calendar access → click **Continue**
4. Browser shows "The authentication flow has completed. You may close this window."
5. Terminal prints:
   ```
   [ok] wrote /Users/tejas/Documents/job-doot/data/token.json
   [..] hitting Gmail API
   [ok] gmail account: tejas06012005@gmail.com (XXXXX messages total)
   [..] hitting Calendar API
   [ok] calendars visible: ['tejas06012005@gmail.com', ...]
   ```

If you see those `[ok]` lines — Gmail + Calendar are fully wired.

### Common errors and fixes
| Error | Cause | Fix |
|---|---|---|
| `Error 403: access_denied` | Forgot to add yourself as a test user | Redo step 4c.5 |
| `Error 400: redirect_uri_mismatch` | Picked Web app instead of Desktop app | Delete the OAuth client, redo 4d with Desktop app |
| `credentials.json not found` | Wrong filename or location | Confirm exact path: `data/credentials.json` |
| Browser doesn't open | SSH session or no display | Run on Mac directly, not over SSH |
| `invalid_grant` after a few days | Test-mode token expired (7 days) | Re-run `oauth_bootstrap.py --force`, or publish the app (4c optional step) |

---

## 5. Final .env check

Open `/Users/tejas/Documents/job-doot/.env` and confirm all four are filled:
```
GROQ_API_KEY=gsk_...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DASHBOARD_PASSWORD=...
```

The Google paths and the rest stay as-is.

---

## DONE checklist

When all of these are true, ping Claude Code in this project and say "setup done, continue Saturday tasks":

- [ ] `.env` has `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DASHBOARD_PASSWORD` filled
- [ ] Telegram test curl delivered a message to your phone
- [ ] `data/credentials.json` exists
- [ ] `data/token.json` exists
- [ ] `oauth_bootstrap.py --test` printed both `[ok] gmail account: ...` and `[ok] calendars visible: [...]`

---

## What you do NOT need to do

- Do **not** install Docker, build images, or run docker-compose yet (we'll do that together later)
- Do **not** create the GCP project's billing account — Gmail + Calendar APIs are free, no card needed
- Do **not** add scopes manually in the consent screen — code requests them
- Do **not** edit any `.py` files — only `.env`
- Do **not** commit `.env`, `credentials.json`, or `token.json` to git (already in `.gitignore`)

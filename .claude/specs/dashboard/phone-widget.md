# Daily visibility on Tejas's phone — home-screen widget + calendar event

Decided 2026-11-03. Problem: Tejas rarely opens Telegram, so outages/progress went unseen
for weeks. Office mail is ruled out (monitored). Put the numbers where he looks anyway.

## /api/summary (backend)
JSON for today (IST): jobs fetched, jobs scored (user 1), applied today (Easy Apply vs
company site), parked "needs you", failed, open form questions, upcoming interviews
(7 days), scraper health (healthy / collected-0 / sick / paused), applier health
(running / paused + reason / quiet >26h), overall status green|yellow|red + a one-line text.
Access: `?key=<WIDGET_KEY>` (random, in the Pi's .env). Originally Tailscale-IP-only, but
Docker's port proxy makes every caller appear as the bridge gateway (172.18.0.1), so IP
checks can't tell Tailscale from home wifi — key instead (2026-11-03). Read-only counts.
Applier numbers come from `data/applier/applier.db` (+ PAUSED flag), read-only.

## iPhone widget (Scriptable, free)
`tools/phone/jobdoot_widget.js` — fetches /api/summary over Tailscale every ~15 min,
shows status colour + Fetched / Applied / Need you / Interviews. Red when anything is
sick or paused. Shows "offline" if the Pi or Tailscale is unreachable.

### Look (decided 2026-11-03)
Matched to Tejas's wallpaper (night sky + red Coke cans) instead of a flat grey card.
- **Plain black card (#000).** The screenshot-based "clear background" was tried and
  dropped the same evening: too fiddly, and screenshots carry app icons. No screenshot
  step, no setup menu. Running the script inside Scriptable shows the widget preview
  straight away.
- **Rings (Apple Fitness style)**, colours taken from the wallpaper: Applied = can red
  #ff4a4a (outer, main goal), Fetched = can silver #f2e4df, Need you = city amber #ffb547.
  Faint same-hue tracks (~30%), round caps, small arrow at the leading end. Goals 12/30/5.
- **Medium:** rings left (~120pt); right: label left (warm off-white ~80%), big rounded
  number right in ring colour ("5/12", "26/30", "3"). Footer: status dot + 12-hour time;
  when yellow/red the reason replaces the time, in the status colour. Interviews appear in
  the footer only when > 0. No title, no "ok" text, no easy/site line.
- **Small:** rings (~80pt) + the three coloured numbers beside them, footer as above.
- **Tap:** opens the job-doot dashboard (http://100.66.138.76:8080) in Safari, not
  Scriptable. iOS gives Scriptable widgets no tap-to-refresh; refresh is iOS-scheduled
  (~15 min ask via refreshAfterDate).
- Script stays ASCII-only (\u escapes) so copying through Safari can't mangle it.

## Daily calendar event
Every day 09:30 IST the scheduler creates a 15-min event on Tejas's personal Google
Calendar (same OAuth as interview events): title = the one-line summary
(e.g. "📊 Fetched 12 · Applied 5 · Need you 2"), description = full breakdown,
popup reminder at start so the phone notifies. Toggle: env DAILY_SUMMARY_EVENT=0 disables.

## Applier errors on the widget (decided 2026-11-12, Tejas)
Problem: on 11–12 Nov the applier was down for ~30h (Claude logged out on the Pi + every
slot crashing at browser start) and the widget stayed **green** until the 26h "quiet"
rule turned it yellow with no reason. Rule from now on: **any applier error shows on the
widget at the next refresh, in plain words.**

- The applier writes `data/applier/HEALTH.json` after every slot (atomic write):
  `{"at", "result": "ok"|"crashed"|"claude_logged_out", "message" (short, fits the footer),
  "detail" (first line of the real error), "streak" (same result in a row)}`.
  - `crashed` — the slot raised before finishing (e.g. browser couldn't start/connect).
  - `claude_logged_out` — a brain call failed with an auth error ("Failed to
    authenticate", "OAuth session expired", "Not logged in", "Invalid API key",
    "Please run /login"). The slot ends at once, the job is **not** logged as failed
    (so it gets retried after the login is fixed), and one Telegram alert per day.
  - `ok` — the slot finished (including "paused" / "no eligible jobs" / quota). Clears the error.
- `/api/summary` reads it (read-only). Order of applier states: paused → Claude logged
  out → crashed → quiet >26h → running. Logged out / crashed ⇒ status **red**.
  Footer text (via the existing `Applier: <applier>`): `Applier: Claude logged out (Pi)`,
  `Applier: crashed 19:43 (x8)`. New field `applier_detail` carries the real error;
  the calendar/summary text includes it.
- **`reason` field (server decides what the footer says).** The old footer logic was
  "scraper not healthy → scraper text, else applier text", so a red applier error hid
  behind a yellow "Scraper: collected 0 in 24h", and a yellow day caused only by open
  questions showed "Applier: running". Now `/api/summary` returns `reason` = the most
  serious problem, in this order: applier red (paused / Claude logged out / crashed) →
  scraper red (sick / paused) → scraper yellow → applier quiet → "N questions to answer".
  Empty when green. The widget shows `d.reason` (falls back to the old logic if the
  field is missing). One-time re-paste of the widget script into Scriptable; after
  that, new error types only need a backend change.

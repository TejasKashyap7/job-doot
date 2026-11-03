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

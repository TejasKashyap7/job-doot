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

## Daily calendar event
Every day 09:30 IST the scheduler creates a 15-min event on Tejas's personal Google
Calendar (same OAuth as interview events): title = the one-line summary
(e.g. "📊 Fetched 12 · Applied 5 · Need you 2"), description = full breakdown,
popup reminder at start so the phone notifies. Toggle: env DAILY_SUMMARY_EVENT=0 disables.

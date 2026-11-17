# Dashboard redesign — "A · Night rings" (decided 2026-11-03)

Tejas found the old UI depressing and desktop-only ("on mobile the whole dynamics
change"). Seven local mockups were compared (A–G, inspired by 21st.dev Orbit Ring Stats +
System Status Block); he picked **A**. Same look as the phone widget so the two feel like
one product.

## Look
- Pure black page, near-black cards (#111014, 1px #26222a border, 22px radius).
- Colours from his wallpaper (same as the widget): applied = can red #ff4a4a,
  fetched = can silver #f2e4df, need-you / warning = city amber #ffb547, ok = #30d158,
  error = #ff453a. Text warm white #f5efed, muted #a39a98.
- System font stack (SF on iPhone/Mac), rounded numerals for big numbers, tabular digits.
- Score = small ring (conic fill = score/10, red) with the number inside.

## Layout
- **Phone first.** < 900px: one column, frosted bottom tab bar (Today, Jobs, Insights,
  Blockers (was Archive until 2026-11-13, see needs-you.md), Admin — Admin only for admins), safe-area insets respected. ≥ 900px: left rail
  with the same items + username + sign out; content in up to 2 columns.
- No table ever makes the page scroll sideways. Job lists are cards on every screen size.
  Admin tables may scroll inside their own box.
- Sign out lives in the rail (PC) and in the account chip on each page header (phone).

## Pages
- **Today (/)**: date + status pill; rings card (applied/12, fetched/30, need you/5) with
  the applier/scraper note from `build_summary`; **health, last 14 days** strip (per day:
  scraper green if it fetched anything else red; applier green if it applied that day);
  **best matches** (top 5 active jobs by score, newest first); **pipeline** card (sources +
  live alerts, all real — no invented activity feed); the existing month calendar heatmap
  kept below (tap a day → that day's Today view, see "Past day view").
- **Jobs (/jobs)**: count chips (Active, Needs review → ?review=1, Filtered → /filtered,
  Awaiting scoring), compact search + score + status filters, source status, day groups
  of job cards. Each card keeps every old action: mark applied, CV, tailoring badge,
  + event (calendar dialog), why? (matches/gaps), apply link, remote/salary.
- **Archive, Filtered**: same card style; archive keeps undo + CV + event.
- **Insights**: same charts (Chart.js), recoloured to the palette, cards stack on phone.
- **Admin**: same sections/actions, restyled; tables scroll inside their card on phone.
- **Login / Sign-up / LinkedIn cookie**: restyled, same forms and field names.

## Rules
- Only templates + `static/style.css` + small read-only additions to the home route
  (summary, 14-day history, best matches). No change to any POST route, form field name,
  or data written.
- Every number shown is real (from the DB / applier.db / alerts). Nothing invented.

## Past day view (decided 2026-11-18, Tejas)
Problem: no way to see how "Today" looked on an earlier day; tapping a calendar day only
listed that day's jobs.
- Tapping a calendar day opens `/?date=YYYY-MM-DD`: the Today page for that IST day.
  Today's date (or no `date`) = the normal live page. Future dates and bad values fall
  back to the live page. The calendar shows the month of the chosen day.
- Shown for a past day (all real, from `build_summary(db, days_ago=N)`): the rings,
  Applied / Fetched / Need you, Easy Apply vs company site, scored, failed. Header
  "Tue 17 Nov" + "Back to today ›", and a "See that day's jobs ›" link to
  `/jobs?date=` (the old tap behaviour, one tap away).
- Hidden for a past day (they describe *right now*, not that day): status pill, scraper /
  applier notes, open questions, interviews in the next 7 days, LinkedIn safety, Best
  matches, Pipeline. The 14-day health bars stay (history, not live).
- The selected day is outlined in the calendar.
- Known small difference: calendar counts and `/jobs?date=` group by UTC day, the day view
  by IST day, so "Fetched" can differ by the few jobs scraped 00:00–05:30 IST.

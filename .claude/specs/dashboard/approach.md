# Dashboard — Approach

## Status
BUILT

## What it does
A password-protected web UI for reviewing scored/tailored jobs, downloading tailored
PDFs, marking jobs as applied, and scheduling interview calendar events. Runs as part
of the main FastAPI backend — no separate process needed.

## Auth
- Cookie-based session login (NOT HTTP Basic Auth)
- Single password stored in `.env` as `DASHBOARD_PASSWORD`
- `require_login` dependency injected on every protected route
- Session cookie: httponly, samesite=lax, no expiry (persists until explicit logout)
- Login page: `/login` | Logout: `POST /logout`

## Pages

### `/` — Active Jobs Dashboard
Shows all jobs in statuses: `ready`, `review_needed`, `scored`, `tailoring`, `filtered_out`
- Grouped by date scraped (newest first)
- Each job card shows: title, company, location, salary, remote flag, score badge, status
- Score badge colour: green (≥8), yellow (≥6), grey (<6 or unscored)
- Filter bar: min score, status dropdown, text search (title/company/location)
- Per-job actions: Apply URL link, Download PDF button (if PDF exists), Mark Applied button

### `/archive` — Applied Jobs
Shows all jobs with `status='applied'`, ordered by date applied (newest first).
Per-job actions: Unapply (moves back to scored/ready), Add to Calendar form.

## Admin endpoints (all require login)
```
POST /admin/trigger-scrape      → manually runs load_csv (load current jobs.csv)
POST /admin/score-pending       → manually scores all 'scraped' jobs
POST /admin/score-one/{job_id}  → score a single job
POST /admin/tailor-pending      → manually tailors all 'scored' jobs
POST /admin/tailor/{job_id}     → tailor a single job
GET  /admin/pdf/{job_id}        → serve the tailored PDF for download
GET  /admin/jobs                → JSON list of recent jobs (debug)
```

## Calendar event creation
From the archive page, a form lets you add an interview/assessment/call to Google
Calendar. Fields: event type, date, time, notes. Creates a real Google Calendar event
via `services/calendar_service.py` and persists a `CalendarEvent` row in the DB.
The event name in Google Calendar is "disguised" (not "Interview at Razorpay") so it
doesn't reveal job-hunting activity to anyone who can see your calendar.

## Job lifecycle (status flow)
```
scraped → scored / filtered_out / rejected
scored  → tailoring → ready / review_needed
ready / review_needed → applied (manual action from dashboard)
applied → scored / ready (unapply action from archive)
```

## Templates
All rendered server-side via Jinja2. No JS framework — plain HTML + CSS.
- `templates/base.html` — shared nav, layout shell
- `templates/login.html` — login form
- `templates/dashboard.html` — active jobs grid
- `templates/archive.html` — applied jobs list
- `static/style.css` — all styling

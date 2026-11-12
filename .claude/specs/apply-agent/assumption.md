# Apply Agent — Assumptions (test phase vs real account)

> Decided by Tejas, 2026-11-13. These rules hold **only while the applier runs on a dummy /
> test account** (today: Vishal's). They change when Tejas's own LinkedIn account is introduced.

## Test phase (dummy account): now

1. **Volume = jobs fetched.** Each day the number of applications should reach the number of
   jobs fetched (scraped) that IST day. Why: we are testing the mechanism and LinkedIn's
   tolerance, not choosing jobs carefully.
2. **No score threshold.** Every scored job is a candidate (`min_score: 0`). "Perfect fit" does
   not matter on a dummy account.
3. **Made-up answers are allowed.** Any form question not covered by the applicant facts or
   the Q&A bank is answered with a realistic, believable, made-up value (never placeholder-looking:
   no "test", "N/A", "xyz", "123456", "abc@abc.com"). The job is applied to instead of skipped.
   - Applicant facts still win: invent only what the facts don't cover.
   - Still never: passwords, creating accounts, payments, CAPTCHAs (hard rules, unchanged).
   - Never invent government ID numbers (PAN, Aadhaar, passport, SSN): a real person's number
     could be hit. That field stays a question for Tejas and the job is skipped.
   - Gender / title: use a "prefer not to say" option if there is one; otherwise ask (question).
4. **Keep the history.** Every made-up answer goes into `qa_bank` with `made_up = 1`, together
   with the question as written, so the full list of questions employers ask is kept.
5. **The 56 questions waiting on 13 Nov** were answered by Claude with made-up values
   (`made_up = 1`), except PAN and title (Mr./Ms.) → still waiting for Tejas.

## Real account (Tejas's LinkedIn): later

1. Apply only to jobs scoring **≥ a threshold** (Tejas will set it), not to everything fetched.
2. **No made-up answers.** Every `made_up = 1` question from the test phase becomes a question
   for Tejas to answer for real, before the first real application. Copy the question list to
   Tejas's applicant with status `UNANSWERED`. The wording is already collected, so nothing
   has to be discovered again.
3. Volume: slow start (1–3 a day, Tejas approves each for the first week), then raise.
4. Honesty rules as originally designed (see `approach.md` → Decisions 2026-11-01).

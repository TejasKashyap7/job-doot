# Application Questions — shared knowledge base

**One growing list of every distinct question a job application has ever asked us, so no one has
to guess in advance what forms will want.** When the applier (or a person) hits a question it can't
answer, that question gets recorded here. Later, anyone — Tejas, Vasu, or any other user — can open
this file, pre-answer questions they haven't been asked yet, and the applier stops getting stuck.

This file is the **human-readable, shared superset**. Each person also has a private machine copy in
their applier (`data/applier/applier.db` → table `qa_bank`) that holds *their own* answers (an answer
may be personal — salary, notice period, address — so answers are NOT committed here unless they are
safe, generic guidance). This file holds the **questions** and **how to answer them**, not private
values.

---

## How it works (the rule)

When a new question appears (a form field the applier could not answer from the applicant's facts):

1. **Check this list first.** Is this question — or one that means the same thing, worded differently
   — already here? (e.g. "Total years of experience" ≈ "How many years have you worked?").
2. **If yes:** answer it the way the entry says; nothing to add.
3. **If no:** **add it** as a new numbered entry at the bottom of the log, with its category and
   answer guidance. The list grows by exactly one. That question is now solved for everyone, forever.

Never delete entries and never add a duplicate. If two entries turn out to mean the same thing, merge
them and keep the lower ID.

> Example of growth: the log has 20 entries; a form asks something genuinely new that none of the 20
> cover; you add it as **#21**. Next time anyone hits it, it's already answered.

---

## Categories

- **identity** — name, contact, links, demographics
- **eligibility** — work authorization, visa, notice period, availability
- **compensation** — current/expected salary, equity
- **location** — address, relocation, remote
- **experience** — years, skills, seniority, specific tech
- **screening** — yes/no knockout questions, certifications
- **documents** — resume, portfolio, references
- **free-text** — cover letter, "why this company", "about yourself"
- **sensitive** — government ID (PAN/Aadhaar/SSN/passport), bank, anything we must NOT auto-answer

---

## Answer guidance conventions

- **"From facts"** — the applier already answers this from the applicant's profile facts; listed here
  only so people know it's covered.
- **"Ask the person"** — personal value that must be collected from the applicant (via the dashboard
  **Admin / Answers** tab) and is then reused. Do not invent it.
- **"Never auto-answer"** — sensitive; always route to the human, never guess (IDs, bank, etc.).

---

## The log

| # | Question (as seen on forms) | Category | How to answer |
|---|------------------------------|----------|----------------|
| 1 | First name / Last name | identity | From facts (split the full name). |
| 2 | Email address | identity | From facts. |
| 3 | Phone / mobile number | identity | From facts (with country code). |
| 4 | LinkedIn profile URL | identity | From facts; leave blank if none. |
| 5 | Are you legally authorized to work in <country>? | eligibility | From facts (authorized in India; sponsorship needed elsewhere). |
| 6 | Do you now or will you require visa sponsorship? | eligibility | From facts (no for India; yes outside India). |
| 7 | Notice period | eligibility | From facts. |
| 8 | Current CTC / current salary | compensation | Ask the person (private; from their saved answer). |
| 9 | Expected CTC / expected salary | compensation | Ask the person (private; from their saved answer). |
| 10 | Total years of experience | experience | From facts. |
| 11 | Years of experience with <specific tech> | experience | From facts; 0 if the tech isn't listed. |
| 12 | Highest qualification / degree | experience | From facts. |
| 13 | Willing to relocate? | location | From facts. |
| 14 | Gender | identity | From facts; else "Prefer not to say". |
| 15 | Resume / CV upload | documents | Always available — upload the applicant's resume file. |
| 16 | Cover letter / Why do you want to join? / Tell us about yourself | free-text | 3–4 honest sentences from facts + the job; never invent experience. |
| 17 | **Full postal / house address (Address line 1)** | location | **Ask the person** — collected via the Admin/Answers tab. *(Added 2026-11-22: NationsBenefits & NTT DATA forms required a full street address, which the profile didn't have.)* |
| 18 | **PIN code / postal code / ZIP** | location | **Ask the person** — part of the address set. *(Added 2026-11-22, same forms.)* |
| 19 | City / District / State / Country | location | Ask the person (part of the address set). |
| 20 | Government ID — PAN / Aadhaar / passport / SSN / national ID | sensitive | **Never auto-answer** — always route to the human. |
| 21 | Date of birth | sensitive | Ask the person; don't guess. |

<!--
HOW TO ADD #22 AND BEYOND (copy a row, bump the number):
| 22 | <the question exactly as the form showed it> | <category> | <From facts | Ask the person | Never auto-answer> — short note + (Added YYYY-MM-DD, which site). |
Keep answers here GENERIC. Private values (a real address, a real salary) live in each person's
applier, never in this shared file.
-->

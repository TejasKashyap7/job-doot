# Shared question bank (decided 2026-11-22, Tejas + Vasu)

Idea from Vasu (`APPLICATION-QUESTIONS.md` on `user/vasu-setup`). Tejas and Vasu each run their
own applier, and both hit the same application form questions. One shared bank keeps the
**questions and how to answer them** in sync. **Personal answers are never shared.**

## Decisions (Tejas, 2026-11-22)
1. **Option B:** a git-based shared file, synced by each applier on its own. No server.
2. Tejas's existing `qa_bank` questions (≈415 from the Vishal test) go in: **questions only**,
   duplicates merged into general entries. Made-up test answers are never shared.
3. Sync **once a day**, at the applier's digest time.
4. Tejas's dashboard gets an **Answers** tab (like Vasu's) where Tejas types his **real** answers.

## Where it lives
- Branch **`shared/question-bank`** in `TejasKashyap7/job-doot`. It holds only:
  - `questions.jsonl`: the source of truth, one entry per line.
  - `APPLICATION-QUESTIONS.md`: generated from the JSONL for people to read (Vasu's format).
    Never edit it by hand; it is overwritten on every sync.
- Each machine keeps a checkout at `data/qbank/` (gitignored `data/`), so both the applier and
  the dashboard container (`./data:/app/data`) can read it.

## Entry format (`questions.jsonl`)
```json
{"id": 25, "question": "Years of experience with <tech>", "category": "experience",
 "rule": "facts", "guidance": "From facts; 0 if the tech isn't listed.",
 "wordings": ["How many years of work experience do you have with NoSQL?*"],
 "added": "2026-11-22", "added_by": "tejas"}
```
- `category`: identity | eligibility | compensation | location | experience | screening |
  documents | free-text | sensitive (Vasu's list).
- `rule`: `facts` (the applier answers from the profile facts) | `ask` (a personal value the
  person must give in the Answers tab) | `never` (sensitive: never auto-answer, always park for
  the human, e.g. PAN/Aadhaar/passport/bank).
- `wordings`: the raw form text seen on real forms, used to match new questions.
- Entries are never deleted. IDs only grow. Vasu's existing #1–#24 keep their numbers.

## Daily sync (`applier/qbank.py`, run at digest time)
1. `git pull --rebase` the `data/qbank/` checkout (cloned on first run).
2. Take this machine's `qa_bank` questions that are not already in any entry's `wordings`
   (match after normalising: lowercase, strip `*`, punctuation and spaces).
3. Send them to Haiku in batches with the list of existing entries. For each one, Haiku says
   either "same meaning as entry #N" (the wording is appended to N) or "new" (a new entry with
   question/category/rule/guidance; ID = max + 1). **Only the question text is sent, never an
   answer.**
4. Regenerate `APPLICATION-QUESTIONS.md`, commit as `qbank: +N new, +M wordings (<user>)`, push.
   If the push is rejected, pull --rebase and retry up to 3 times; on a JSONL conflict, re-run the
   merge on top of the remote file.
5. A failed sync only logs a warning and retries the next day. It never stops applying.
   If the push fails (e.g. the machine's GitHub key can't write), the merge commit is kept
   locally and rebased + pushed on the next run, so the Haiku work isn't repeated.
6. Pushing needs a GitHub key with write access on each machine (the Pi's deploy key must have
   "Allow write access").

## How the applier uses the bank
- `rule: never` entries are passed to the brain as "never answer these: park the job for the
  human". This applies to every profile.
- `facts` / `ask` guidance is not used for answering in phase 1. Answers still come only from the
  profile facts + this applicant's own answered `qa_bank` rows.

## Real answers: only for Tejas's real account (the key rule)
- The Answers tab saves Tejas's answers into `qa_bank` with **`applicant = "tejas"`** and
  `made_up = 0`.
- The applier only reads answered rows **where `applicant` = the applying profile's name**
  (`store.answered(conn, cfg["name"])`). So:
  - **Applying account is Tejas (profile `tejas`)** → use those answers.
  - **Any other account** (the `vishal` test profile now, Vasu's, anyone else's) → never use them.
- We are in the middle of the 2-week LinkedIn test with the Vishal dummy account. After that,
  applying switches to Tejas's real account, and only then are these answers used. **No date is
  set for that switch**; the rule is the account check above, not a calendar date.
- The Answers tab says this plainly at the top.

## Answers tab (Tejas's dashboard, `main`)
- Lists every bank entry with `rule: ask` (this machine's own questions are in the bank after
  each sync), grouped by category, with the guidance as help text. `rule: facts` entries sit in a
  collapsed "usually answered from your profile" section (optional fixed answers).
  `rule: never` entries are shown read-only ("never filled automatically") and can't be saved.
- Visible only to the owner (admin or `SUMMARY_USER_ID`).
- Clearing a box deletes that saved answer.

### Vasu-style saving + suggested answers (Tejas, 2026-11-23)
- **One card per question, saved on its own** (like Vasu's tab): `POST /answers/q/<id>` returns
  200 → the card shows "Saved ✓", fades and disappears. Errors show on the card and keep it.
  Answered questions move to a collapsed "Answered" section where they can still be edited.
- **3 suggested answers per question**, shown as tap-to-pick chips, plus a "Something else" box
  for typing your own. Picking a chip fills the box; Save stores whatever is in the box.
- Suggestions come from `applier/suggest.py` (runs on the Pi, after the daily bank sync and on
  demand): Haiku reads Tejas's `.claude/research/PROFILE.md` (never `private/`) and proposes up
  to 3 short answers per unanswered `ask`/`facts` question. Stored in the local applier DB table
  `qa_suggest(question, options, made_at)`. **Never pushed to the shared bank** (personal data).
- Identity questions (pronouns, gender, religion, caste, disability, ethnicity, sexual
  orientation): never guess from the profile or name; offer the standard neutral options,
  including "Prefer not to say".
- Values not in the profile (salary, DOB, address): suggestions are clearly guesses or formats;
  the person decides.
- One text box per question. Saving writes/updates the `applicant = "tejas"` row. It shows
  answered/total.
- Banner: "These are your real answers for your own account. They are NOT used while the test
  account (Vishal) is applying. They start being used once applying switches to your account."

## Out of scope (phase 1)
- Vasu's machine: he pulls this spec + `applier/qbank.py` and runs the same daily sync. His
  existing `APPLICATION-QUESTIONS.md` on his branch is folded in as the seed (#1–#24).
- Using shared guidance to auto-answer `facts`/`ask` questions.

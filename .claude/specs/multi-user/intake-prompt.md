# job-doot onboarding — intake session

You are helping me prepare everything needed to sign up for a personal AI job-hunting
pipeline (job-doot) that a friend runs. It scrapes AI/ML job postings, scores each one
against MY specific profile using an LLM, and auto-tailors a LaTeX version of my resume
for the jobs that score well. It is NOT generic — the scoring and tailoring only work
well if the profile data below is complete, specific, and true. Vague or padded answers
produce a worse resume and worse job matches for me, so push me for specifics rather
than accepting generic answers.

**Your job in this session:** interview me thoroughly, then produce one complete,
exactly-formatted export block (schema below) plus a separate LaTeX resume file. I will
copy/paste the export block and upload the resume into a signup form afterward — nothing
here gets submitted automatically.

## Ground rules (do not skip these)

1. **Verified facts only.** Every claim in `project_library` must be something I can
   actually back up — a real metric, a real tool I used, a real outcome. If I'm vague
   ("worked on some ML stuff"), ask follow-up questions until it's concrete, or drop it.
2. **If you (Claude) have read access to my actual project repositories in this session
   (I'm running you from inside them, or I share the code), cross-check my claims
   against the real code before finalizing `verified_facts`.** Don't just transcribe
   what I say — verify it. This matters: a resume/scoring system that gets fed inflated
   claims produces interviews I can't back up, and it also skews how jobs get scored for
   me. If you find a mismatch between what I claimed and what the code actually does,
   tell me and let's fix the claim, not the code.
3. **Never invent** metrics, tools, dates, or outcomes I didn't give you. If something is
   uncertain, mark it in `do_not_claim` instead of guessing.
4. This produces personal profile data, not a public post — be exhaustive, not brief.

## What to interview me about, in order

1. **Identity & basics:** desired username (no spaces), current role/status (student /
   intern / employed — be exact about title, company, dates), education (degree,
   institution, years, GPA if I want it included).
2. **How I want to be presented:** e.g. "present me as a working engineer, not a
   student" or the reverse — any framing rules, anything I explicitly don't want
   mentioned (e.g. a gap, a former employer, a personal detail).
3. **Locked skill set:** every real skill, grouped by category (languages; LLM/GenAI;
   vector DBs/embeddings; ML/DL frameworks; infra/deployment; practices; etc — adapt
   categories to what I actually have). Push for specificity: not "ML" but "PyTorch,
   fine-tuned ResNet50 for X." This list is a hard ceiling — nothing outside it will ever
   be claimed on my behalf later, so it must be complete now.
4. **Project library — the most important part.** For EVERY real project (work, research,
   personal, academic — anything substantial), extract:
   - name, tech stack, live link (if any)
   - `verified_facts`: bullet list of specific, defensible claims (what it does, scale,
     metrics, my specific contribution if it was a team project)
   - `do_not_claim`: things that are adjacent but NOT true (e.g. "does not use X even
     though it sounds like it might") — this is the hard guardrail against future
     hallucination, so think about what a reader might wrongly assume and rule it out
     explicitly.
5. **Role-type preferences.** Not all AI jobs are equally interesting to me — I need a
   ranked preference, e.g.: "Research/R&D roles are my top preference," "genuine core ML
   engineering is good too," "applied-AI-at-a-consulting-shop should score low even if
   the skills match," "these specific role types or companies should be penalized or
   excluded entirely." Be specific — this directly controls how jobs get scored for me,
   and it's supposed to be MY preference, not a generic AI-engineer default.
6. **Location / remote / salary preferences.** Cities I'll work in, remote-only or open
   to relocation, salary range if I want it used as a filter (optional).
7. **Telegram (optional):** do I want job alerts here? If yes, walk me through creating a
   bot via @BotFather (I message @BotFather, `/newbot`, get a token) and finding my
   numeric chat ID (message the bot once, then check
   `https://api.telegram.org/bot<TOKEN>/getUpdates`, or use @userinfobot). If I'd rather
   skip Telegram, that's fine — it's optional and can be added later.
8. **Groq API keys — get ALL of them, plural.** I should list every Groq key I have
   access to (multiple accounts if I have them), one per line. These get used in
   rotation for resume tailoring — when one account runs out of free-tier credits, the
   system automatically moves to the next key, so more keys = more uninterrupted
   tailoring. Remind me these come from console.groq.com → API Keys, and that each one
   should actually be tested (a real API call) before I call it done — a dead/typo'd key
   in the list just wastes a rotation attempt later.
9. **Resume file.** Ask whether I already have a LaTeX (`.tex`) resume:
   - If yes: use it as-is, but sanity-check that everything in it is backed by
     `verified_facts` above — flag any mismatch.
   - If no: help me produce one from scratch (or convert my existing PDF/Word resume).
     Keep it simple enough to compile with `tectonic` (avoid exotic/rare LaTeX packages),
     aim for one page, and make sure every factual claim in it traces back to
     `verified_facts` — nothing in the resume should exist that isn't also in the
     project library, since that's what keeps future auto-tailoring honest.

## Required output format

End the session with exactly this, nothing else outside the delimiters:

```
PROFILE_EXPORT_START
username: <handle, no spaces>
candidate_profile: |
  <2-4 sentence blurb: education, current role, how I want to be presented, anything
  explicitly off-limits to mention>
locked_skill_set:
  <category>: [<skill>, <skill>, ...]
  <category>: [...]
  # as many categories as needed
project_library:
  - name: <project name>
    tech: [<tool>, <tool>, ...]
    live_link: <url or "none">
    verified_facts:
      - <specific, defensible claim>
      - ...
    do_not_claim:
      - <thing that must never be claimed about this project>
      - ...
  # repeat per project
role_type_preferences:
  most_preferred: [<role type>, ...]
  also_good: [<role type>, ...]
  penalize: [<role type or company pattern>, ...]
  out_of_scope: [<role type>, ...]
  notes: |
    <anything about weighting that doesn't fit the lists above>
location_prefs:
  cities: [<city>, ...]
  remote_ok: <true/false>
  relocate_ok: <true/false>
salary_pref: <range, or "not disclosed">
telegram:
  enabled: <true/false>
  bot_token: <token, or "n/a">
  chat_id: <id, or "n/a">
groq_keys:
  - <key 1>
  - <key 2>
  # every key I have, each one tested working
resume_file: <filename of the .tex file I'm attaching separately>
PROFILE_EXPORT_END
```

Also produce/finalize the `.tex` resume file as a separate file alongside this export.

## Before I finish this session, confirm with me:

- [ ] Every project has at least one `verified_facts` entry backed by something real
- [ ] `do_not_claim` lists actually address plausible wrong assumptions, not left empty
      by default
- [ ] Every Groq key listed has been test-called and confirmed working
- [ ] If Telegram is enabled, the bot token + chat ID have been confirmed working (a
      test message was actually sent and received)
- [ ] The `.tex` file compiles cleanly (if I have a way to test that) and every claim in
      it traces back to `verified_facts`
- [ ] I have the export block AND the `.tex` file saved somewhere I can get to during
      signup

## Security note

This export contains real API keys and (if enabled) a Telegram bot token. Treat the
export block like a password: don't paste it anywhere other than the signup form, don't
leave it in a permanent notes file or a shared chat, and delete your local copy once
you've completed signup. Do NOT include a login password in this export — I'll set that
directly on the signup form itself, not here.

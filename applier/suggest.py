"""Suggested answers for the dashboard Answers tab (Tejas's real account).

Spec: .claude/specs/question-bank/spec.md "Vasu-style saving + suggested answers".
Haiku reads the owner's PROFILE.md and proposes up to 3 short answers per shared-bank question
that has no saved answer yet. Stored ONLY in the local applier DB (qa_suggest) — personal data,
never pushed to the shared bank.

  python -m applier.suggest --applicant tejas [--profile-md PATH] [--all]
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from . import config, qbank, store

log = logging.getLogger(__name__)

DEFAULT_PROFILE_MD = Path(os.path.expanduser("~/job-doot/.claude/research/PROFILE.md"))
BATCH = 20

PROMPT = """You help a job seeker pre-fill answers to job-application questions.

THEIR PROFILE (their own notes):
{profile}

THEIR ANSWER RULES (always follow these; make the first option match the rule):
{rules}

For each question below, give up to 3 short, realistic answers they would most likely pick,
best first. Each answer must be ready to paste into a form (no explanations, under 25 words;
free-text questions may be up to 2 sentences).
- Use the profile facts exactly where they apply.
- Values the profile does not state (salary, date of birth, address, phone): give sensible
  options or formats as guesses; never claim them as facts.
- Identity questions (pronouns, gender, religion, caste, disability, ethnicity, sexual
  orientation, veteran status): NEVER guess from the profile or name. Offer the standard
  neutral options and include "Prefer not to say".
- Yes/No questions: give the most likely one first, then the other.
- Questions whose answer depends on WHICH company the form is for ("previously employed here",
  "worked for us before", "applied here before", "know anyone / relatives who work here",
  "current or former employee"): the FIRST option must be a rule naming the employers from the
  profile, e.g. "No. Yes only if the company is Lenskart or Blu Parrot Ventures (BluParrot)."
  Then plain "No", then plain "Yes".
- Questions whose answer depends on the JOB DESCRIPTION (department, team, area of interest):
  the first option is a rule, e.g. "One choice: Research & Development (AI/ML). Several: every
  AI-related option that matches the job description."

QUESTIONS:
{questions}

Reply JSON only: {{"items": [{{"i": <index>, "options": ["...", "...", "..."]}}, ...]}}"""


def _table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS qa_suggest (question TEXT PRIMARY KEY,"
                 " options TEXT NOT NULL, made_at TEXT NOT NULL)")


def run(cfg, applicant: str, profile_md: Path = DEFAULT_PROFILE_MD, redo: bool = False) -> int:
    from .brain import _call
    profile = profile_md.read_text()
    rules_file = config.DATA / f"answer_rules_{applicant}.md"   # private, local (spec: answer rules)
    rules = rules_file.read_text() if rules_file.exists() else "(none)"
    conn = store.connect()
    _table(conn)
    answered = {r[0] for r in conn.execute(
        "SELECT question FROM qa_bank WHERE applicant=? AND status='ANSWERED'", (applicant,))}
    have = set() if redo else {r[0] for r in conn.execute("SELECT question FROM qa_suggest")}
    todo = [e for e in qbank.load() if e.get("rule") in ("ask", "facts")
            and e["question"] not in answered and e["question"] not in have]
    todo.sort(key=lambda e: e.get("rule") != "ask")      # ask-the-person questions first
    made = 0
    for s in range(0, len(todo), BATCH):
        chunk = todo[s:s + BATCH]
        qs = "\n".join(f"{i}. {e['question']}" + (f"  (hint: {e['guidance']})" if e.get("guidance") else "")
                       for i, e in enumerate(chunk))
        try:
            data = _call(cfg, PROMPT.format(profile=profile, rules=rules, questions=qs), cfg["models"]["primary"])
        except Exception:
            log.exception("suggest: batch %d failed", s)
            continue
        now = datetime.now().isoformat(timespec="seconds")
        for it in data.get("items") or []:
            try:
                e = chunk[int(it["i"])]
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            opts = [str(o).strip() for o in (it.get("options") or []) if str(o).strip()][:3]
            if opts:
                conn.execute("INSERT OR REPLACE INTO qa_suggest(question, options, made_at) VALUES(?,?,?)",
                             (e["question"], json.dumps(opts, ensure_ascii=False), now))
                made += 1
        conn.commit()
        log.info("suggest: %d/%d questions done", min(s + BATCH, len(todo)), len(todo))
    return made


def main():
    import argparse
    from .config import load_profile
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="vishal", help="applier profile (for claude settings only)")
    ap.add_argument("--applicant", default="tejas", help="whose answers the suggestions are for")
    ap.add_argument("--profile-md", type=Path, default=DEFAULT_PROFILE_MD)
    ap.add_argument("--all", action="store_true", help="redo questions that already have suggestions")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(f"suggestions made: {run(load_profile(a.profile), a.applicant, a.profile_md, a.all)}")


if __name__ == "__main__":
    main()

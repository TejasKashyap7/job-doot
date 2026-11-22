"""Shared question bank: one list of application questions for every job-doot user.

Spec: .claude/specs/question-bank/spec.md (main). Lives on git branch `shared/question-bank`
(questions.jsonl + generated APPLICATION-QUESTIONS.md), checked out at data/qbank/.
Only QUESTION TEXT is shared — never answers.

  python -m applier.qbank sync --profile vishal     # daily (also run from the digest)
  python -m applier.qbank show                      # print entries
"""
import json
import logging
import re
import subprocess
from datetime import date
from pathlib import Path

from . import config, store

log = logging.getLogger(__name__)

BRANCH = "shared/question-bank"
DIR = config.DATA.parent / "qbank"
JSONL = DIR / "questions.jsonl"
MD = DIR / "APPLICATION-QUESTIONS.md"
CATEGORIES = ["identity", "eligibility", "compensation", "location", "experience", "screening",
              "documents", "free-text", "sensitive"]
RULES = {"facts": "From facts", "ask": "Ask the person", "never": "Never auto-answer"}
BATCH = 40


def norm(q: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (q or "").lower()).strip()


def _git(*args, check=True):
    return subprocess.run(["git", "-C", str(DIR), *args], capture_output=True, text=True,
                          timeout=120, check=check)


def load() -> list[dict]:
    if not JSONL.exists():
        return []
    return [json.loads(l) for l in JSONL.read_text().splitlines() if l.strip()]


def never_list() -> list[str]:
    """Questions no applier may ever auto-answer (rule: never). Empty if no checkout yet."""
    try:
        return [e["question"] for e in load() if e.get("rule") == "never"]
    except Exception:
        log.exception("qbank: could not read never-list")
        return []


def _save(entries: list[dict]):
    entries.sort(key=lambda e: e["id"])
    JSONL.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    rows = []
    for e in entries:
        q = e["question"].replace("|", "/")
        g = e.get("guidance", "").replace("|", "/")
        n = len(e.get("wordings") or [])
        seen = f" *(seen {n}× on forms)*" if n else ""
        rows.append(f"| {e['id']} | {q} | {e['category']} | **{RULES.get(e['rule'], e['rule'])}**: {g}{seen} |")
    MD.write_text(
        "# Application Questions — shared knowledge base\n\n"
        "**Generated from `questions.jsonl` by `applier/qbank.py` — do not edit by hand.**\n"
        "Every distinct question job applications have asked any job-doot user. Questions and how to\n"
        "answer them only — personal answers stay in each person's own applier.\n\n"
        "Rules: **From facts** = the applier answers from the profile; **Ask the person** = a personal\n"
        "value the person gives in the dashboard Answers tab; **Never auto-answer** = sensitive, always\n"
        "left for the human.\n\n"
        "| # | Question | Category | How to answer |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")


def _checkout(remote: str):
    if not (DIR / ".git").exists():
        DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--branch", BRANCH, "--single-branch", remote, str(DIR)],
                       capture_output=True, text=True, timeout=180, check=True)
    else:
        _git("fetch", "origin", BRANCH)
        # keep a merge that was committed but not pushed last time (e.g. no write access)
        if _git("rebase", f"origin/{BRANCH}", check=False).returncode != 0:
            _git("rebase", "--abort", check=False)
            _git("reset", "--hard", f"origin/{BRANCH}")


PROMPT = """You maintain a shared bank of job-application form questions. Merge NEW questions into it.

EXISTING ENTRIES (id | question | category | rule):
{entries}

NEW QUESTIONS (as written on forms):
{new}

For each new question decide:
- If it asks the SAME THING as an existing entry (even worded differently or for a different
  company), map it: {{"i": <new index>, "same": <entry id>}}.
- Else create a general entry: {{"i": <index>, "new": {{"question": "<short general wording; replace
  company names / specific tech with <company> / <tech> if that makes it reusable>",
  "category": one of {cats}, "rule": "facts"|"ask"|"never", "guidance": "<one short sentence>"}}}}.
  Several new questions that mean the same thing share one entry: give the later ones
  {{"i": <index>, "same_as_new": <index of the first>}}.
Rules: "facts" = answerable from a normal profile (name, years, skills, education, notice period,
yes/no on a skill). "ask" = a personal value or preference only the person knows (salary, address,
date of birth, why-this-company, availability, relocation). "never" = government ID numbers,
bank/card details, passwords, anything sensitive.
Reply JSON only: {{"items": [ ... one object per new question ... ]}}"""


def _merge(cfg, entries: list[dict], questions: list[str], who: str) -> tuple[int, int]:
    from .brain import _call
    known = {norm(w): e for e in entries for w in [e["question"], *(e.get("wordings") or [])]}
    todo, seen = [], set()
    for q in questions:
        k = norm(q)
        if k and k not in known and k not in seen:
            seen.add(k)
            todo.append(q)
    added = wordings = 0
    for s in range(0, len(todo), BATCH):
        chunk = todo[s:s + BATCH]
        listing = "\n".join(f"{e['id']} | {e['question']} | {e['category']} | {e['rule']}" for e in entries)
        data = _call(cfg, PROMPT.format(entries=listing or "(none)", cats=CATEGORIES,
                                        new="\n".join(f"{i}. {q}" for i, q in enumerate(chunk))),
                     cfg["models"]["primary"])
        by_id = {e["id"]: e for e in entries}
        new_ids: dict[int, dict] = {}
        for it in sorted(data.get("items") or [], key=lambda x: int(x.get("i", 0))):
            try:
                i = int(it["i"])
                q = chunk[i]
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            tgt = None
            if it.get("same") in by_id:
                tgt = by_id[it["same"]]
            elif it.get("same_as_new") is not None and int(it["same_as_new"]) in new_ids:
                tgt = new_ids[int(it["same_as_new"])]
            elif isinstance(it.get("new"), dict):
                n = it["new"]
                tgt = {"id": max([e["id"] for e in entries] or [0]) + 1,
                       "question": str(n.get("question") or q).strip(),
                       "category": n.get("category") if n.get("category") in CATEGORIES else "screening",
                       "rule": n.get("rule") if n.get("rule") in RULES else "ask",
                       "guidance": str(n.get("guidance") or "").strip(),
                       "wordings": [], "added": date.today().isoformat(), "added_by": who}
                entries.append(tgt)
                by_id[tgt["id"]] = tgt
                new_ids[i] = tgt
                added += 1
            if tgt is not None:
                if norm(q) not in {norm(w) for w in tgt.setdefault("wordings", [])}:
                    tgt["wordings"].append(q)
                    wordings += 1
        log.info("qbank: batch %d-%d merged (%d entries now)", s, s + len(chunk), len(entries))
    return added, wordings


def sync(cfg, who: str | None = None) -> str:
    """Pull, merge this machine's qa_bank questions, push. Returns a one-line result."""
    who = who or cfg.get("qbank_user") or cfg["name"]
    remote = subprocess.run(["git", "-C", str(config.ROOT), "remote", "get-url", "origin"],
                            capture_output=True, text=True, check=True).stdout.strip()
    conn = store.connect()
    questions = [r[0] for r in conn.execute("SELECT question FROM qa_bank ORDER BY id")]
    for attempt in range(3):
        _checkout(remote)
        entries = load()
        added, wordings = _merge(cfg, entries, questions, who)
        if added or wordings:
            _save(entries)
            _git("add", "questions.jsonl", "APPLICATION-QUESTIONS.md")
            _git("-c", "user.name=job-doot applier", "-c", "user.email=applier@job-doot.local",
                 "commit", "-m", f"qbank: +{added} new, +{wordings} wordings ({who})")
        ahead = int(_git("rev-list", "--count", f"origin/{BRANCH}..HEAD").stdout.strip() or 0)
        if not ahead:
            return f"qbank: up to date ({len(entries)} entries)"
        push = _git("push", "origin", f"HEAD:{BRANCH}", check=False)
        if push.returncode == 0:
            msg = f"qbank: pushed {ahead} commit(s) (+{added} new, +{wordings} wordings, {len(entries)} entries)"
            log.info(msg)
            return msg
        err = push.stderr.lower()
        if "access rights" in err or "denied" in err or "read only" in err or "403" in err:
            raise RuntimeError("qbank: no write access to GitHub — merge kept locally, "
                               "will push once the key can write: " + push.stderr.strip()[-200:])
        log.warning("qbank: push rejected (attempt %d) — rebasing on remote", attempt + 1)
    raise RuntimeError("qbank: push kept failing")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sync", "show"])
    ap.add_argument("--profile", default="vishal")
    ap.add_argument("--user", help="name recorded as added_by (default: profile qbank_user or name)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "sync":
        print(sync(config.load_profile(a.profile), a.user))
    else:
        for e in load():
            print(f"#{e['id']:>3} [{e['category']}/{e['rule']}] {e['question']}  ({len(e.get('wordings') or [])} wordings)")


if __name__ == "__main__":
    main()

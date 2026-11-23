"""Answers tab: Tejas's REAL answers to the shared question bank.

Spec: .claude/specs/question-bank/spec.md. Questions come from the shared bank checkout
(data/qbank/questions.jsonl, branch shared/question-bank). Answers are saved into the applier's
qa_bank with applicant = "tejas". The applier only reads rows for the profile that is applying,
so these are used ONLY when the applying account is Tejas's own — never by the Vishal test
profile or anyone else's applier. Suggested answers come from the local qa_suggest table
(made on the Pi by applier/suggest.py from PROFILE.md; never shared).
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DATA = Path(os.getenv("APPLIER_DATA_DIR", "/app/data/applier"))
APPLIER_DB = DATA / "applier.db"
BANK = DATA.parent / "qbank" / "questions.jsonl"
APPLICANT = "tejas"   # real account profile name; answers are keyed to it

CATEGORY_ORDER = ["identity", "eligibility", "compensation", "location", "experience",
                  "screening", "documents", "free-text", "sensitive"]


def _bank() -> list[dict]:
    if not BANK.exists():
        return []
    return [json.loads(l) for l in BANK.read_text().splitlines() if l.strip()]


def _conn():
    c = sqlite3.connect(f"file:{APPLIER_DB}?mode=rw", uri=True, timeout=8)
    c.row_factory = sqlite3.Row
    return c


def _read():
    """(saved answers, suggestions) keyed by question text."""
    if not APPLIER_DB.exists():
        return {}, {}
    c = _conn()
    try:
        saved = {r["question"]: r["answer"] for r in c.execute(
            "SELECT question, answer FROM qa_bank WHERE applicant=? AND status='ANSWERED'", (APPLICANT,))}
        sugg = {}
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='qa_suggest'").fetchone():
            for r in c.execute("SELECT question, options FROM qa_suggest"):
                try:
                    sugg[r["question"]] = json.loads(r["options"])[:3]
                except ValueError:
                    pass
        return saved, sugg
    finally:
        c.close()


COVERED = DATA / f"persona_{APPLICANT}_covered.json"   # spec: "Persona replaces per-question answers"


def _covered() -> set[int]:
    """Bank ids the persona already answers (private, local file kept next to the persona)."""
    try:
        return {int(i) for i in json.loads(COVERED.read_text())}
    except (OSError, ValueError, TypeError):
        return set()


def build() -> dict:
    bank = _bank()
    saved, sugg = _read()
    covered = _covered()
    groups = {"ask": [], "facts": [], "never": [], "answered": [], "covered": []}
    for e in bank:
        e["answer"] = saved.get(e["question"], "")
        e["seen"] = len(e.get("wordings") or [])
        e["suggestions"] = sugg.get(e["question"], [])
        rule = e.get("rule") if e.get("rule") in ("ask", "facts", "never") else "ask"
        if e["answer"] and rule != "never":
            g = "answered"
        elif e["id"] in covered and rule != "never":
            g = "covered"
        else:
            g = rule
        groups[g].append(e)
    key = lambda e: (CATEGORY_ORDER.index(e["category"]) if e["category"] in CATEGORY_ORDER else 99, e["id"])
    for g in groups.values():
        g.sort(key=key)
    total_ask = sum(1 for e in bank if e.get("rule") == "ask")
    done_ask = sum(1 for e in groups["answered"] + groups["covered"] if e.get("rule") == "ask")
    return {**groups, "done": done_ask, "total": total_ask, "has_bank": bool(bank),
            "has_suggestions": bool(sugg)}


def save_one(qid: int, answer: str) -> bool:
    """Save (or, if empty, delete) the answer to bank entry `qid`. False = unknown/never entry."""
    q = next((e["question"] for e in _bank() if e["id"] == qid and e.get("rule") != "never"), None)
    if q is None:
        return False
    answer = (answer or "").strip()
    c = _conn()
    try:
        if not answer:
            c.execute("DELETE FROM qa_bank WHERE applicant=? AND question=?", (APPLICANT, q))
        else:
            now = datetime.now().isoformat(timespec="seconds")
            c.execute(
                "INSERT INTO qa_bank(applicant, question, answer, status, first_seen, answered_at, made_up)"
                " VALUES(?,?,?,'ANSWERED',?,?,0)"
                " ON CONFLICT(applicant, question) DO UPDATE SET answer=excluded.answer,"
                " status='ANSWERED', answered_at=excluded.answered_at, made_up=0",
                (APPLICANT, q, answer, now, now))
        c.commit()
    finally:
        c.close()
    return True

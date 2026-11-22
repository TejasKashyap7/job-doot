"""Answers tab: Tejas's REAL answers to the shared question bank.

Spec: .claude/specs/question-bank/spec.md. Questions come from the shared bank checkout
(data/qbank/questions.jsonl, branch shared/question-bank). Answers are saved into the applier's
qa_bank with applicant = "tejas". The applier only reads rows for the profile that is applying,
so these are used ONLY when the applying account is Tejas's own — never by the Vishal test
profile or anyone else's applier.
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


def _saved() -> dict[str, str]:
    if not APPLIER_DB.exists():
        return {}
    c = _conn()
    try:
        return {r["question"]: r["answer"] for r in c.execute(
            "SELECT question, answer FROM qa_bank WHERE applicant=? AND status='ANSWERED'", (APPLICANT,))}
    finally:
        c.close()


def build() -> dict:
    bank, saved = _bank(), _saved()
    groups = {"ask": [], "facts": [], "never": []}
    for e in bank:
        e["answer"] = saved.get(e["question"], "")
        e["seen"] = len(e.get("wordings") or [])
        groups.get(e.get("rule"), groups["ask"]).append(e)
    key = lambda e: (CATEGORY_ORDER.index(e["category"]) if e["category"] in CATEGORY_ORDER else 99, e["id"])
    for g in groups.values():
        g.sort(key=key)
    ask = groups["ask"]
    return {"ask": ask, "facts": groups["facts"], "never": groups["never"],
            "done": sum(1 for e in ask if e["answer"]), "total": len(ask), "has_bank": bool(bank)}


def save(form: dict) -> int:
    """form: {"q<id>": answer}. Empty = delete the saved answer. Returns rows changed."""
    by_id = {str(e["id"]): e["question"] for e in _bank() if e.get("rule") != "never"}
    now = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    n = 0
    try:
        for k, v in form.items():
            if not k.startswith("q") or k[1:] not in by_id:
                continue
            q, v = by_id[k[1:]], (v or "").strip()
            old = c.execute("SELECT answer FROM qa_bank WHERE applicant=? AND question=?",
                            (APPLICANT, q)).fetchone()
            if not v:
                if old:
                    c.execute("DELETE FROM qa_bank WHERE applicant=? AND question=?", (APPLICANT, q))
                    n += 1
                continue
            if old and old["answer"] == v:
                continue
            c.execute(
                "INSERT INTO qa_bank(applicant, question, answer, status, first_seen, answered_at, made_up)"
                " VALUES(?,?,?,'ANSWERED',?,?,0)"
                " ON CONFLICT(applicant, question) DO UPDATE SET answer=excluded.answer,"
                " status='ANSWERED', answered_at=excluded.answered_at, made_up=0",
                (APPLICANT, q, v, now, now))
            n += 1
        c.commit()
    finally:
        c.close()
    return n

"""Backend for the dashboard "Answers" tab.

Two things live here:
  • outstanding() — questions the applier parked because it couldn't answer them from the
    profile (qa_bank rows with status UNANSWERED), e.g. "Address line 1".
  • a profile INTAKE — questions we proactively ask the person (address, etc.), defined
    precisely below.

Answers are written into the applier's OWN SQLite (data/applier/applier.db) as ANSWERED
qa_bank rows. The applier's brain reads ANSWERED rows and reuses them for same-meaning form
fields, so answering here once clears the blocker everywhere.
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

APPLIER_DB = Path(os.getenv("APPLIER_DATA_DIR", "/app/data/applier")) / "applier.db"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _conn():
    APPLIER_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{APPLIER_DB}?mode=rwc", uri=True, timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS qa_bank ("
        " id INTEGER PRIMARY KEY, applicant TEXT NOT NULL, question TEXT NOT NULL,"
        " field_type TEXT, options TEXT, answer TEXT,"
        " status TEXT NOT NULL DEFAULT 'UNANSWERED', job_id INTEGER,"
        " first_seen TEXT NOT NULL, answered_at TEXT, UNIQUE(applicant, question))")
    return conn


# --- profile intake: exactly what we ask the person, be generous with detail ---
INTAKE = [
    {
        "id": "address",
        "title": "Your postal address",
        "intro": "Fill in your home address the way you'd write it on a job application. You only do "
                 "this once — it's saved privately and used to answer address questions for you "
                 "automatically. Don't worry about getting the wording perfect.",
        "fields": [
            {"name": "building", "label": "Flat / house / building number",
             "help": "The flat or house number where you live, plus the building or society name if it has one.",
             "placeholder": "e.g. Flat 302, Green Valley Apartments", "required": True},
            {"name": "street", "label": "Street / road name",
             "help": "The road your building is on. On most forms this is the box called “Address line 1”.",
             "placeholder": "e.g. MG Road, Sector 14", "required": True},
            {"name": "locality", "label": "Area / locality",
             "help": "Your neighbourhood, colony or sector (often the “Address line 2” box). Leave blank if you don't have one.",
             "placeholder": "e.g. DLF Phase 2", "required": False},
            {"name": "city", "label": "City or town",
             "help": "The city or town you live in.",
             "placeholder": "e.g. Gurugram", "required": True},
            {"name": "district", "label": "District",
             "help": "Your district — some Indian forms ask for it on its own. Leave blank if you're not sure.",
             "placeholder": "e.g. Gurugram", "required": False},
            {"name": "state", "label": "State",
             "help": "The state you live in.",
             "placeholder": "e.g. Haryana", "required": True},
            {"name": "pin", "label": "PIN code",
             "help": "Your 6-digit postal PIN code (the number the postman uses).",
             "placeholder": "e.g. 122001", "required": True},
            {"name": "country", "label": "Country",
             "help": "The country you live in.",
             "placeholder": "India", "default": "India", "required": True},
            {"name": "lives_here", "label": "Do you live at this address right now?",
             "help": "Choose “Yes” if this is where you actually stay today. Choose “No” if it's your home-town or an old address.",
             "options": ["Yes", "No"], "required": True},
            {"name": "official", "label": "Is this your permanent address?",
             "help": "“Permanent” means the address printed on your official ID (like Aadhaar). “Current only” means it's just where you're staying now.",
             "options": ["Yes — it's my permanent address",
                         "No — it's only where I currently stay"], "required": True},
        ],
        "done_key": "PIN code / postal code / ZIP code",   # ANSWERED => this group is complete
    },
]


def _answered_set(conn, applicant) -> set:
    return {r["question"] for r in conn.execute(
        "SELECT question FROM qa_bank WHERE applicant=? AND status='ANSWERED'", (applicant,))}


def _help_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS qa_help ("
                 " question TEXT PRIMARY KEY, simple TEXT, explain TEXT, example TEXT, made_at TEXT)")


def get_help(question: str):
    """Cached plain-language version of a raw form question, or None if not generated yet."""
    try:
        conn = _conn()
    except Exception:
        return None
    try:
        _help_table(conn)
        r = conn.execute("SELECT simple, explain, example FROM qa_help WHERE question=?",
                         (question,)).fetchone()
        return {"simple": r["simple"], "explain": r["explain"], "example": r["example"]} if r else None
    finally:
        conn.close()


def make_help(question: str) -> dict:
    """Return plain-language help for a raw form question, generating via Claude and caching."""
    cached = get_help(question)
    if cached:
        return cached
    simple, explain, example = question, "", ""
    try:
        import services.claude_client as cc
        data = cc.chat_json(
            "You rewrite confusing job-application form questions into plain, simple English for a "
            "non-technical job seeker who speaks English as a second language. Reply with JSON only.",
            'A job application form showed this field:\n"' + question + '"\n\n'
            'Return JSON with three short keys:\n'
            '{"simple": "<the question in plain everyday words, max 12 words>",'
            ' "explain": "<one simple sentence telling the person what to type>",'
            ' "example": "<a short realistic example answer they could give>"}',
            model="haiku")
        simple = (str(data.get("simple")) or question)[:140]
        explain = str(data.get("explain") or "")[:240]
        example = str(data.get("example") or "")[:120]
    except Exception:
        pass
    try:
        conn = _conn()
        _help_table(conn)
        conn.execute("INSERT OR REPLACE INTO qa_help(question, simple, explain, example, made_at)"
                     " VALUES(?,?,?,?,?)", (question, simple, explain, example, _now()))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {"simple": simple, "explain": explain, "example": example}


def help_for_id(applicant: str, qa_id: int) -> dict:
    conn = _conn()
    try:
        r = conn.execute("SELECT question FROM qa_bank WHERE id=? AND applicant=?",
                         (qa_id, applicant)).fetchone()
    finally:
        conn.close()
    return make_help(r["question"]) if r else {"simple": "", "explain": "", "example": ""}


def outstanding(applicant: str) -> list[dict]:
    try:
        conn = _conn()
    except Exception:
        return []
    try:
        _help_table(conn)
        helps = {r["question"]: {"simple": r["simple"], "explain": r["explain"], "example": r["example"]}
                 for r in conn.execute("SELECT question, simple, explain, example FROM qa_help")}
        rows = conn.execute(
            "SELECT id, question, field_type, options, job_id FROM qa_bank"
            " WHERE applicant=? AND status='UNANSWERED' ORDER BY id", (applicant,)).fetchall()
        return [{"id": r["id"], "question": r["question"],
                 "options": [o for o in (r["options"] or "").split(" | ") if o],
                 "job_id": r["job_id"], "help": helps.get(r["question"])} for r in rows]
    finally:
        conn.close()


def pending_intake(applicant: str) -> list[dict]:
    try:
        conn = _conn()
    except Exception:
        return list(INTAKE)
    try:
        done = _answered_set(conn, applicant)
        return [g for g in INTAKE if g["done_key"] not in done]
    finally:
        conn.close()


def _upsert(conn, applicant, question, answer):
    conn.execute(
        "INSERT INTO qa_bank(applicant, question, field_type, options, answer, status,"
        " first_seen, answered_at) VALUES(?,?,?,?,?,'ANSWERED',?,?)"
        " ON CONFLICT(applicant, question) DO UPDATE SET answer=excluded.answer,"
        " status='ANSWERED', answered_at=excluded.answered_at",
        (applicant, question.strip(), None, "", (answer or "").strip(), _now(), _now()))


def save_question(applicant: str, qa_id: int, text: str) -> bool:
    if not (text or "").strip():
        return False
    conn = _conn()
    try:
        cur = conn.execute(
            "UPDATE qa_bank SET answer=?, status='ANSWERED', answered_at=? WHERE id=? AND applicant=?",
            (text.strip(), _now(), qa_id, applicant))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def save_intake(applicant: str, group_id: str, values: dict) -> bool:
    group = next((g for g in INTAKE if g["id"] == group_id), None)
    if not group:
        return False
    missing = [f["label"] for f in group["fields"]
               if f.get("required") and not (values.get(f["name"]) or "").strip()]
    if missing:
        return False
    conn = _conn()
    try:
        if group_id == "address":
            v = {f["name"]: (values.get(f["name"]) or "").strip() for f in group["fields"]}
            line1 = ", ".join(x for x in (v["building"], v["street"]) if x)
            state_pin = " ".join(x for x in (v["state"], v["pin"]) if x)
            full = ", ".join(x for x in (line1, v["locality"], v["city"], v["district"],
                                         state_pin, v["country"]) if x)
            pairs = [
                ("Full residential / mailing address", full),
                ("Address line 1 (house/building and street)", line1),
                ("Address line 2 / area / locality", v["locality"]),
                ("City / town", v["city"]),
                ("District", v["district"]),
                ("State / province", v["state"]),
                ("PIN code / postal code / ZIP code", v["pin"]),
                ("Country", v["country"]),
                ("Do you currently live at this address?", v["lives_here"]),
                ("Is this your permanent address?", v["official"]),
            ]
            for q, a in pairs:
                if a:
                    _upsert(conn, applicant, q, a)
        conn.commit()
        return True
    finally:
        conn.close()

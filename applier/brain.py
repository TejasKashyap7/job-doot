"""Headless Claude Code brain (Haiku first, Sonnet as one retry).

next_actions(): Haiku looks at a page snapshot and decides what to click/type next
(spec "Haiku drives the browser", 2026-11-05). answer_fields(): the older field-only
mode, kept for driver: script.
"""
import json
import logging
import os
import re
import subprocess
import tempfile

log = logging.getLogger(__name__)

HONEST_RULES = """HONESTY (hard rules):
- Answer ONLY from the applicant facts and the answered questions below. Never invent
  experience, skills, degrees, certifications, numbers, links or employers.
- Years of experience with a skill/tool the applicant does not list = 0.
- Yes/No "do you have experience with X" where X is not in the facts = No.
- A REQUIRED question you cannot answer truthfully from the facts or the answered questions:
  do NOT guess — put it in "unknown" (browser: and set status "ask_human").
- "made_up" must stay empty.
"""

# Test (dummy) accounts only — .claude/specs/apply-agent/assumption.md
TEST_RULES = """TEST ACCOUNT (made-up answers allowed):
- The applicant facts and the answered questions always win — use them first, unchanged.
- Any other question (required or not): INVENT a realistic, believable answer that fits this
  applicant and stays consistent with the facts and with earlier answers. It must read like a
  real person's answer: never "test", "N/A", "xyz", "abc", "123456", "lorem", dummy emails or
  obviously fake numbers. Keep claims modest and plausible.
- List EVERY invented answer in "made_up" (question as written + your answer).
- Never invent government ID numbers (PAN, Aadhaar, passport, SSN, national ID): put that field
  in "unknown" (browser: status "ask_human").
- Gender / title (Mr./Ms.): pick a "prefer not to say" option if one exists, else "unknown".
"""


def _rules(cfg) -> str:
    return TEST_RULES if cfg.get("test_mode") else HONEST_RULES


PROMPT = """You fill in a LinkedIn Easy Apply form for ONE applicant.

{rules}- Select/radio answers MUST be copied exactly from that field's "options".
- Numeric fields: a plain number only.
- Optional fields you cannot answer: leave them out.
- Checkbox fields: answer "yes" to tick or "no" to leave unticked (tick consent /
  terms-of-application boxes only if required).
- Name fields: split the name from the facts (first / last). URLs (LinkedIn) only from the
  facts; leave portfolio/GitHub/website out if the facts have none.
- Cover letter / "why do you want to join" / "tell us about yourself" text fields: write
  3-4 short, honest sentences from the facts and the job title/company. Never invent
  experience, projects or skills; it is fine to say the applicant is early-career and keen
  to learn.

Reply with ONLY this JSON, nothing else:
{{"answers": {{"<field id>": "<value>"}}, "unknown": ["<field id>"],
 "made_up": [{{"question": "<field label as written>", "answer": "<what you invented>"}}]}}

APPLICANT FACTS:
{facts}

ANSWERED QUESTIONS (reuse for same-meaning questions, even if worded differently):
{qa}

JOB: {title} at {company}
{errors}
FIELDS TO FILL:
{fields}
"""


class BrainError(Exception):
    pass


class BrainQuota(BrainError):
    """Claude subscription limit reached (HTTP 429 / weekly or 5-hour limit). Not the
    job's fault: skip without counting a failure; applying resumes after the reset."""


def _call(cfg, prompt: str, model: str, image: str | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
    with tempfile.TemporaryDirectory() as empty:  # nothing for it to read (except the screenshot)
        cmd = [cfg["claude_bin"], "-p", prompt, "--model", model, "--output-format", "json"]
        if image:
            import shutil
            shutil.copy(image, os.path.join(empty, "page.png"))
            cmd += ["--allowedTools", "Read"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=240, cwd=empty, env=env)
    if out.returncode != 0:
        blob = (out.stdout or "") + (out.stderr or "")
        if '"api_error_status":429' in blob or "hit your" in blob and "limit" in blob:
            m = re.search(r'"result":"([^"]*limit[^"]*)"', blob)
            raise BrainQuota(m.group(1) if m else "Claude usage limit reached")
        raise BrainError(f"claude exit {out.returncode}: {out.stderr[-300:] or out.stdout[-300:]}")
    try:
        result = json.loads(out.stdout).get("result", "")
    except json.JSONDecodeError:
        result = out.stdout
    m = re.search(r"\{.*\}", result, re.S)
    if not m:
        raise BrainError(f"no JSON in reply: {result[:200]}")
    return json.loads(m.group(0))


def _made_up(cfg, data: dict) -> list[dict]:
    if not cfg.get("test_mode"):
        return []
    return [{"question": str(m["question"])[:500], "answer": str(m["answer"])[:500]}
            for m in (data.get("made_up") or [])
            if isinstance(m, dict) and m.get("question") and m.get("answer") not in (None, "")]


def _validate(data: dict, fields: list[dict]) -> dict:
    by_id = {f["id"]: f for f in fields}
    answers = {k: str(v) for k, v in (data.get("answers") or {}).items() if k in by_id}
    unknown = [u for u in (data.get("unknown") or []) if u in by_id]
    for fid, val in list(answers.items()):
        f = by_id[fid]
        if f.get("options") and val not in f["options"]:
            # tolerate case/space differences, otherwise treat as unknown
            match = next((o for o in f["options"] if o.strip().lower() == val.strip().lower()), None)
            if match:
                answers[fid] = match
            else:
                answers.pop(fid)
                if f.get("required"):
                    unknown.append(fid)
    missing = [f["id"] for f in fields if f.get("required") and f["id"] not in answers
               and f["id"] not in unknown]
    if missing:
        raise BrainError(f"required fields left unanswered: {missing}")
    return {"answers": answers, "unknown": unknown}


def answer_fields(cfg, fields: list[dict], qa: list[dict], job: dict, errors: str = "") -> dict:
    qa_text = "\n".join(f"Q: {q['question']}\nA: {q['answer']}" for q in qa) or "(none yet)"
    slim = [{k: f[k] for k in ("id", "type", "label", "required", "options") if k in f} for f in fields]
    prompt = PROMPT.format(
        rules=_rules(cfg), facts=cfg["facts"].strip(), qa=qa_text, title=job.get("title"), company=job.get("company"),
        errors=f"\nTHE FORM REJECTED THE LAST ANSWERS WITH: {errors}\n" if errors else "",
        fields=json.dumps(slim, ensure_ascii=False, indent=1),
    )
    last = None
    for model in (cfg["models"]["primary"], cfg["models"]["retry"]):
        try:
            data = _call(cfg, prompt, model)
            res = _validate(data, fields)
            res["made_up"] = _made_up(cfg, data)
            return res
        except BrainQuota:
            raise  # same account for both models — retrying with Sonnet won't help
        except (BrainError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            log.warning("brain (%s) failed: %s", model, exc)
            last = exc
    raise BrainError(str(last))



# ---------------------------------------------------------------------------
# Haiku drives the browser
# ---------------------------------------------------------------------------

AGENT_PROMPT = """You are applying for a job in a real web browser on behalf of ONE applicant,
the way a careful person would: look at what is on the page, then act.

GOAL: submit a job application for "{title}" at "{company}".
{scope}

HOW YOU SEE THE PAGE: a numbered list of everything clickable/typeable, each with its role,
label, the question written near it, current value, options, and the page REGION it sits in
(dialog / form / search / nav / header / footer / cookie-banner / page). Plus the page text.
Elements in the "search" region are the site's JOB SEARCH bar — never fill them; they are not
the application. A job DESCRIPTION page usually has an "Apply" / "Apply now" / "Easy Apply" /
"I'm interested" button or link: click it to reach the form. Close or accept cookie banners
and pop-ups that get in the way. If you need to see more of the page, scroll.

LINKEDIN: "Apply on company website" / "Apply" with an arrow opens the company's site in a NEW
TAB — the browser switches you there automatically. LinkedIn's own "Did you finish applying?" /
"Did you apply?" question: NEVER answer Yes unless an application really was confirmed; close it
or answer No.

{rules}- Select / radio answers must be one of that element's options, copied exactly.
- Cover letter / "why do you want to join" boxes: 3-4 short honest sentences from the facts and
  the job title/company; early-career and keen to learn is fine.
- Tick consent / terms checkboxes only when required to apply. Never subscribe to newsletters.
- Resume / CV upload: the applicant's resume file ({resume_name}) is ALWAYS available — use
  action "upload_resume" on the file input or the upload / attach button. Never ask the human
  for the resume and never put a resume / CV field in "unknown".
- Never enter a password, create an account, pay, or solve a CAPTCHA: status "ask_human" with why.

ACTIONS (do them in order; put ALL the fields of this page in one reply, then at most ONE
click that moves on — Next / Continue / Review / Submit / Apply — as the LAST action):
  {{"do":"click","n":N}}                      button, link, radio, option, tab, checkbox
  {{"do":"type","n":N,"text":"..."}}          text boxes (replaces what is there)
  {{"do":"select","n":N,"option":"..."}}      <select> dropdowns (role select) only
  {{"do":"check","n":N,"on":true}}            checkbox on/off
  {{"do":"upload_resume","n":N}}              file input or upload button
  {{"do":"key","key":"Enter"|"Escape"|"Tab"}}
  {{"do":"scroll","dir":"down"|"up"}}
  {{"do":"back"}}                             browser back
  {{"do":"wait"}}                             page still loading
For a custom dropdown / typeahead (role combobox, button that opens a list): type or click it,
then wait for the next page view to pick the option.

STATUS:
  "continue"   — you gave actions; show me the page again afterwards
  "applied"    — the page CONFIRMS the application was sent / received / submitted (no actions)
  "ask_human"  — a required answer is unknown, or a password/account/CAPTCHA/payment step
  "give_up"    — this cannot be applied to (job closed, broken page, nothing works); say why
  "need_screenshot" — the text list makes no sense and you need to see the page

Reply with ONLY this JSON:
{{"page":"<one line: what this page is>","actions":[...],"status":"continue",
  "unknown":[{{"n":N,"question":"<the question as written>"}}],"why":"<for non-continue>",
  "made_up":[{{"question":"<the question as written>","answer":"<what you invented>"}}]}}
"why" is shown to the job seeker in a notification: write it in 1-3 SIMPLE sentences for a
non-technical person — what you saw on the page, what you tried, and why you stopped.
No codes, no element numbers. Example: "The company page only had a job-search box and a
'Sign in' button; applying needs an account, which I'm not allowed to create."

APPLICANT FACTS:
{facts}

ANSWERED QUESTIONS (reuse for same-meaning questions):
{qa}

WHAT YOU DID SO FAR (most recent last):
{history}
{note}
CURRENT PAGE
url: {url}
title: {page_title}
errors shown: {errors}
{screenshot}
ELEMENTS:
{elements}

PAGE TEXT (trimmed):
{text}
"""

ALLOWED = {"click", "type", "select", "check", "upload_resume", "key", "scroll", "back", "wait"}
RESUME_Q = re.compile(r"\b(resume|résumé|cv|curriculum vitae)\b", re.I)
STATUSES = {"continue", "applied", "ask_human", "give_up", "need_screenshot"}


def _validate_plan(data: dict, snap: dict) -> dict:
    by_n = {e["n"]: e for e in snap["elements"]}
    status = data.get("status")
    if status not in STATUSES:
        raise BrainError(f"bad status {status!r}")
    actions = []
    for a in data.get("actions") or []:
        do = a.get("do")
        if do not in ALLOWED:
            raise BrainError(f"action not allowed: {a}")
        if do in ("click", "type", "select", "check", "upload_resume"):
            try:
                a["n"] = int(a.get("n"))
            except (TypeError, ValueError):
                raise BrainError(f"action without element: {a}")
            if a["n"] not in by_n:
                raise BrainError(f"element [{a['n']}] does not exist")
            el = by_n[a["n"]]
            if el["role"] == "password":
                raise BrainError("tried to touch a password field")
            if el["region"] == "search" and do in ("type", "select"):
                raise BrainError(f"tried to fill the site's search bar [{a['n']}]")
            if do == "select":
                opts = el.get("options") or []
                val = str(a.get("option", ""))
                match = next((o for o in opts if o == val), None) or \
                    next((o for o in opts if o.strip().lower() == val.strip().lower()), None)
                if not match:
                    raise BrainError(f"option {val!r} not in [{a['n']}] options")
                a["option"] = match
            if do == "type":
                a["text"] = str(a.get("text", ""))
        if do == "key" and a.get("key") not in ("Enter", "Escape", "Tab"):
            raise BrainError(f"key not allowed: {a}")
        actions.append(a)
    unknown = [u for u in (data.get("unknown") or []) if isinstance(u, dict) and u.get("question")]
    def _is_resume(u):
        try:
            el = by_n.get(int(u.get("n")))
        except (TypeError, ValueError):
            el = None
        return (el is not None and el["role"] == "file") or bool(RESUME_Q.search(str(u["question"])))
    real = [u for u in unknown if not _is_resume(u)]
    if status == "ask_human" and unknown and not real:
        raise BrainError("the resume file IS available — use upload_resume on the resume/CV field "
                         "instead of asking the human")
    unknown = real
    if status == "continue" and not actions:
        raise BrainError("status continue but no actions")
    return {"page": str(data.get("page", ""))[:200], "actions": actions, "status": status,
            "unknown": unknown, "why": str(data.get("why", ""))[:600]}


def next_actions(cfg, snap: dict, rendered: str, job: dict, qa: list[dict], history: list[str],
                 note: str = "", scope: str = "", image: str | None = None) -> dict:
    qa_text = "\n".join(f"Q: {q['question']}\nA: {q['answer']}" for q in qa) or "(none yet)"
    prompt = AGENT_PROMPT.format(
        rules=_rules(cfg), title=job.get("title"), company=job.get("company"), scope=scope,
        resume_name=os.path.basename(str(cfg.get("resume_pdf") or "resume.pdf")),
        facts=cfg["facts"].strip(), qa=qa_text,
        history="\n".join(history[-8:]) or "(just opened the job page)",
        note=f"\nNOTE FROM THE BROWSER: {note}\n" if note else "",
        url=snap["url"][:300], page_title=snap["title"][:150],
        errors="; ".join(snap["errors"])[:600] or "none",
        screenshot="A SCREENSHOT of this page is in the file page.png — Read it.\n" if image else "",
        elements=rendered, text=snap["text"],
    )
    last = None
    for model in (cfg["models"]["primary"], cfg["models"]["retry"]):
        try:
            data = _call(cfg, prompt, model, image)
            plan = _validate_plan(data, snap)
            plan["made_up"] = _made_up(cfg, data)
            return plan
        except BrainQuota:
            raise
        except (BrainError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            log.warning("brain (%s) plan rejected: %s", model, exc)
            last = exc
            prompt += f"\n\nYOUR PREVIOUS REPLY WAS REJECTED: {exc}. Fix it and reply with JSON only.\n"
    raise BrainError(str(last))

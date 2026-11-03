"""Form answering with headless Claude Code (Haiku first, Sonnet as one retry).

Clicking never goes through the LLM — this module only maps form fields to answers.
"""
import json
import logging
import os
import re
import subprocess
import tempfile

log = logging.getLogger(__name__)

PROMPT = """You fill in a LinkedIn Easy Apply form for ONE applicant.

Use ONLY the applicant facts and the answered questions below. Never invent
experience, skills, degrees, certifications or numbers. Honesty rules:
- Years of experience with a skill/tool the applicant does not list = 0.
- Yes/No "do you have experience with X" where X is not in the facts = No.
- Select/radio answers MUST be copied exactly from that field's "options".
- Numeric fields: a plain number only.
- If a REQUIRED field cannot be answered truthfully from the facts or the answered
  questions, put its id in "unknown" instead of guessing.
- Optional fields you cannot answer: leave them out.
- Checkbox fields: answer "yes" to tick or "no" to leave unticked (tick consent /
  terms-of-application boxes only if required).

Reply with ONLY this JSON, nothing else:
{{"answers": {{"<field id>": "<value>"}}, "unknown": ["<field id>"]}}

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


def _call(cfg, prompt: str, model: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
    with tempfile.TemporaryDirectory() as empty:  # nothing for it to read
        out = subprocess.run(
            [cfg["claude_bin"], "-p", prompt, "--model", model, "--output-format", "json"],
            capture_output=True, text=True, timeout=180, cwd=empty, env=env,
        )
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
        facts=cfg["facts"].strip(), qa=qa_text, title=job.get("title"), company=job.get("company"),
        errors=f"\nTHE FORM REJECTED THE LAST ANSWERS WITH: {errors}\n" if errors else "",
        fields=json.dumps(slim, ensure_ascii=False, indent=1),
    )
    last = None
    for model in (cfg["models"]["primary"], cfg["models"]["retry"]):
        try:
            return _validate(_call(cfg, prompt, model), fields)
        except BrainQuota:
            raise  # same account for both models — retrying with Sonnet won't help
        except (BrainError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            log.warning("brain (%s) failed: %s", model, exc)
            last = exc
    raise BrainError(str(last))

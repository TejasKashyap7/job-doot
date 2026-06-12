"""Critic agent — reviews a LaTeX resume against a JD and returns shortcomings + verdict."""
from __future__ import annotations

import logging
from typing import TypedDict

from agents.prompts import CRITIC_SYSTEM
from services.groq_client import chat_json

log = logging.getLogger(__name__)


class CriticResult(TypedDict):
    shortcomings: list[dict]   # [{"id": int, "severity": str, "issue": str}, ...]
    verdict: str               # "APPROVED" or "NEEDS WORK"
    reason: str


def review(latex_resume: str, job_title: str, company: str, jd: str) -> CriticResult:
    user = (
        f"JOB TITLE: {job_title}\n"
        f"COMPANY: {company}\n\n"
        f"JOB DESCRIPTION:\n{jd}\n\n"
        f"--- RESUME (LaTeX source) ---\n{latex_resume}\n"
        f"--- END RESUME ---"
    )
    raw = chat_json(CRITIC_SYSTEM, user, temperature=0.2, max_tokens=1500)
    # normalize
    shortcomings = raw.get("shortcomings") or []
    verdict = (raw.get("verdict") or "NEEDS WORK").upper().strip()
    if verdict not in {"APPROVED", "NEEDS WORK"}:
        verdict = "NEEDS WORK"
    log.info("Critic verdict=%s (%d shortcomings)", verdict, len(shortcomings))
    return CriticResult(
        shortcomings=shortcomings,
        verdict=verdict,
        reason=raw.get("reason") or "",
    )

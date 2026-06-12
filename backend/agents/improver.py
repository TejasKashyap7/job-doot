"""Improver agent — rewrites the LaTeX resume to address critic shortcomings.

Output is delimiter-formatted, not JSON, because LaTeX inside a JSON string
is painful to round-trip. We parse the three sections directly."""
from __future__ import annotations

import json
import logging
import re
from typing import TypedDict

from agents.prompts import IMPROVER_SYSTEM
from services.groq_client import chat_text

log = logging.getLogger(__name__)


class ImproverResult(TypedDict):
    latex: str
    changelog: str
    unfixable: str


_LATEX_RE = re.compile(r"LATEX_START\s*\n(.*?)\nLATEX_END", re.DOTALL)
_CHANGELOG_RE = re.compile(r"CHANGELOG_START\s*\n(.*?)\nCHANGELOG_END", re.DOTALL)
_UNFIXABLE_RE = re.compile(r"UNFIXABLE:\s*(.*?)$", re.DOTALL | re.MULTILINE)


def _parse(raw: str, fallback_latex: str) -> ImproverResult:
    m_latex = _LATEX_RE.search(raw)
    m_change = _CHANGELOG_RE.search(raw)
    m_unfix = _UNFIXABLE_RE.search(raw)

    if not m_latex:
        log.error("Improver output missing LATEX_START/END block; falling back to previous LaTeX")
        latex = fallback_latex
    else:
        latex = m_latex.group(1).strip()
        # Strip ```latex fences if model added them inside the block
        latex = re.sub(r"^```(?:latex)?\s*\n?", "", latex)
        latex = re.sub(r"\n?```$", "", latex)

    return ImproverResult(
        latex=latex,
        changelog=(m_change.group(1).strip() if m_change else ""),
        unfixable=(m_unfix.group(1).strip() if m_unfix else "none"),
    )


def improve(latex_resume: str, job_title: str, company: str, jd: str,
            shortcomings: list[dict]) -> ImproverResult:
    user = (
        f"JOB TITLE: {job_title}\n"
        f"COMPANY: {company}\n\n"
        f"JOB DESCRIPTION:\n{jd}\n\n"
        f"SHORTCOMINGS TO ADDRESS (from critic):\n"
        f"{json.dumps(shortcomings, indent=2)}\n\n"
        f"--- CURRENT RESUME (LaTeX source) ---\n{latex_resume}\n"
        f"--- END RESUME ---\n\n"
        f"Rewrite the LaTeX to address the shortcomings above, obeying the absolute rules. "
        f"Use the exact delimiter format specified."
    )
    raw = chat_text(IMPROVER_SYSTEM, user, temperature=0.3, max_tokens=6000)
    return _parse(raw, fallback_latex=latex_resume)

"""Mechanical, no-AI tailoring checks (Flaw 2).

Two cheap facts computed after each resume is tailored, so a resume the critic
wrongly stamped "APPROVED" still gets flagged for a human to eyeball:

1. change_ratio  — how much of the tailored LaTeX is identical to the master.
                   ~1.0 means the improver effectively did nothing (e.g. the
                   critic approved on round one and shipped the untouched master).
2. skill_coverage — of the LOCKED_SKILL_SET skills this JD asks for, how many
                   actually appear on the tailored resume.

Both are pure Python (difflib + word matching) — no Groq calls, no new deps.
They judge only the mechanical failures; a human still reads the flagged ones.
"""
from __future__ import annotations

import difflib
import re

# similarity >= this => tailored resume is basically the master => flag "unchanged"
SIMILARITY_FLAG_THRESHOLD = 0.97
# coverage < this (with the JD asking for known skills) => flag "review"
COVERAGE_FLAG_THRESHOLD = 0.5

# Canonical skill -> lowercase match aliases. Grounded in LOCKED_SKILL_SET
# (agents/prompts.py); aliases handle wording variants (RAG vs
# "retrieval-augmented generation") so real matches are not missed.
# MAINTENANCE: when LOCKED_SKILL_SET changes, update this map to match.
SKILL_ALIASES: dict[str, list[str]] = {
    "python": ["python"],
    "c++": ["c++"],
    "groq": ["groq"],
    "gemini": ["gemini"],
    "langchain": ["langchain"],
    "langgraph": ["langgraph"],
    "mcp": ["mcp", "model context protocol"],
    "rag": ["rag", "retrieval-augmented", "retrieval augmented",
            "retrieval augmented generation"],
    "multi-agent": ["multi-agent", "multi agent", "agentic"],
    "prompt engineering": ["prompt engineering", "prompting"],
    "llm": ["llm", "large language model", "large language models",
            "genai", "generative ai"],
    "chromadb": ["chromadb", "chroma"],
    "pinecone": ["pinecone"],
    "faiss": ["faiss"],
    "embeddings": ["embedding", "embeddings", "sentence-transformers",
                   "sentence transformers"],
    "vector db": ["vector db", "vector database", "vector databases", "vector store"],
    "sarvam": ["sarvam"],
    "asr": ["asr", "speech recognition", "speech-to-text", "speech to text"],
    "diarization": ["diarization"],
    "tensorflow": ["tensorflow"],
    "keras": ["keras"],
    "pytorch": ["pytorch"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "transfer learning": ["transfer learning"],
    "efficientnet": ["efficientnet"],
    "mobilenet": ["mobilenet"],
    "cnn": ["cnn", "convolutional"],
    "onnx": ["onnx"],
    "federated learning": ["federated learning"],
    "yolo": ["yolo", "yolov5"],
    "object detection": ["object detection"],
    "computer vision": ["computer vision", "image classification", "image segmentation"],
    "sentinel-2": ["sentinel-2", "sentinel 2", "satellite imagery",
                   "remote sensing", "ndvi"],
    "fastapi": ["fastapi"],
    "pydantic": ["pydantic"],
    "docker": ["docker"],
    "raspberry pi": ["raspberry pi", "raspberrypi"],
    "cloudflare": ["cloudflare"],
    "supabase": ["supabase"],
    "linux": ["linux"],
    "deep learning": ["deep learning"],
    "machine learning": ["machine learning"],
    "nlp": ["nlp", "natural language processing"],
}


def _compile(aliases: list[str]) -> re.Pattern:
    # Token boundary that also works for tokens ending in non-word chars (c++):
    # not preceded/followed by an alphanumeric. Avoids "rag" matching "storage".
    parts = [r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])" for a in aliases]
    return re.compile("|".join(parts))


_SKILL_PATTERNS = {canon: _compile(aliases) for canon, aliases in SKILL_ALIASES.items()}

_LATEX_COMMENT = re.compile(r"(?<!\\)%.*")
_LATEX_CMD = re.compile(r"\\[a-zA-Z]+\*?")


def strip_latex(latex: str) -> str:
    """Reduce LaTeX source to lowercased plain text so we match rendered words,
    not markup. Drops comments, \\commands, and structural symbols."""
    text = _LATEX_COMMENT.sub(" ", latex)
    text = _LATEX_CMD.sub(" ", text)
    text = re.sub(r"[{}\\$&#~^_]", " ", text)
    return text.lower()


def change_ratio(master_latex: str, tailored_latex: str) -> float:
    """0..1 — fraction of text identical between master and tailored resume."""
    return difflib.SequenceMatcher(None, master_latex, tailored_latex).ratio()


def skill_coverage(jd: str, resume_text: str):
    """(coverage, demanded, missing). coverage is None when the JD mentions no
    known skill (nothing to check). resume_text must be pre-stripped/lowercased."""
    jd_l = jd.lower()
    demanded: list[str] = []
    missing: list[str] = []
    for canon, pat in _SKILL_PATTERNS.items():
        if pat.search(jd_l):
            demanded.append(canon)
            if not pat.search(resume_text):
                missing.append(canon)
    coverage = (len(demanded) - len(missing)) / len(demanded) if demanded else None
    return coverage, demanded, missing


def confidence_label(similarity: float | None, coverage: float | None) -> str | None:
    """Derive the dashboard tag from the two stored numbers. Recomputable any
    time, so it is not stored. None => no resume/checks yet (no badge)."""
    if similarity is None:
        return None
    if similarity >= SIMILARITY_FLAG_THRESHOLD:
        return "unchanged"
    if coverage is not None and coverage < COVERAGE_FLAG_THRESHOLD:
        return "review"
    return "ok"


def evaluate(master_latex: str, tailored_latex: str, jd: str) -> dict:
    """Run both checks for one tailored resume."""
    similarity = change_ratio(master_latex, tailored_latex)
    coverage, demanded, missing = skill_coverage(jd, strip_latex(tailored_latex))
    return {
        "similarity": similarity,
        "coverage": coverage,
        "demanded_skills": demanded,
        "missing_skills": missing,
        "confidence": confidence_label(similarity, coverage),
    }

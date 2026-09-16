"""Parses the PROFILE_EXPORT_START/END YAML block produced by the intake prompt
(.claude/specs/multi-user/intake-prompt.md) into the same free-text style used by
seed_tejas.py / prompts.py, so a new signup reads exactly like a hand-written
profile at prompt-build time.
"""
from __future__ import annotations

import re

import yaml

_BLOCK_RE = re.compile(r"PROFILE_EXPORT_START\s*\n(.*?)\nPROFILE_EXPORT_END", re.DOTALL)


class ProfileImportError(ValueError):
    pass


def _render_skill_set(skills: dict) -> str:
    if not isinstance(skills, dict) or not skills:
        raise ProfileImportError("locked_skill_set must be a non-empty mapping of category -> [skills]")
    lines = []
    for category, items in skills.items():
        if not items:
            continue
        lines.append(f"{category}: " + ", ".join(str(i) for i in items))
    return "\n".join(lines)


def _render_project_library(projects: list) -> str:
    if not isinstance(projects, list) or not projects:
        raise ProfileImportError("project_library must be a non-empty list")
    blocks = []
    for p in projects:
        name = p.get("name", "Untitled project")
        tech = ", ".join(p.get("tech") or [])
        link = p.get("live_link") or "none"
        facts = p.get("verified_facts") or []
        bans = p.get("do_not_claim") or []
        block = [f"=== PROJECT: {name} (LIVE: {link}) ==="]
        block.append(f"Tech: {tech}.")
        block.append("Verified facts:")
        block.extend(f"- {f}" for f in facts)
        if bans:
            block.append("DO NOT CLAIM: " + "; ".join(bans) + ".")
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def _render_role_prefs(prefs: dict) -> str:
    if not isinstance(prefs, dict):
        raise ProfileImportError("role_type_preferences must be a mapping")
    lines = ["ROLE-TYPE PREFERENCE (this candidate's own ranking — weigh the TYPE of role, "
             "not just skill overlap):"]
    if prefs.get("most_preferred"):
        lines.append("STRONGLY PREFERRED (allow 8-10 when skills also match): " +
                      ", ".join(prefs["most_preferred"]) + ".")
    if prefs.get("also_good"):
        lines.append("GENUINE CORE ENGINEERING (7-8): " + ", ".join(prefs["also_good"]) + ".")
    if prefs.get("penalize"):
        lines.append("PENALIZE — CAP AT 5-6 even if skill keywords match: " +
                      ", ".join(prefs["penalize"]) + ".")
    if prefs.get("out_of_scope"):
        lines.append("OUT-OF-SCOPE ROLES (score 0 regardless): " +
                      ", ".join(prefs["out_of_scope"]) + ".")
    if prefs.get("notes"):
        lines.append(str(prefs["notes"]).strip())
    lines.append('When you cap a score for role-type, SAY SO as the FIRST entry in top_gaps.')
    return "\n".join(lines)


def _render_location_prefs(loc: dict) -> str:
    if not isinstance(loc, dict):
        raise ProfileImportError("location_prefs must be a mapping")
    cities = ", ".join(loc.get("cities") or []) or "unspecified"
    remote = "yes" if loc.get("remote_ok") else "no"
    relocate = "yes" if loc.get("relocate_ok") else "no"
    return f"Cities: {cities}. Remote OK: {remote}. Relocation OK: {relocate}."


def parse_profile_export(raw_text: str) -> dict:
    """Returns a dict of the fields ready to assign onto a User row (plus
    'username' and 'groq_keys'/'telegram' for the caller to use separately).
    Raises ProfileImportError with a human-readable message on any problem —
    callers should show that back to the user rather than a stack trace."""
    m = _BLOCK_RE.search(raw_text)
    body = m.group(1) if m else raw_text  # tolerate a paste without the delimiter lines

    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as e:
        raise ProfileImportError(f"Could not parse the profile export as YAML: {e}") from e
    if not isinstance(data, dict):
        raise ProfileImportError("Profile export did not parse to a YAML mapping")

    required = ["candidate_profile", "locked_skill_set", "project_library",
                "role_type_preferences", "location_prefs"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ProfileImportError(f"Profile export is missing required field(s): {', '.join(missing)}")

    try:
        result = {
            "candidate_profile": str(data["candidate_profile"]).strip(),
            "locked_skill_set": _render_skill_set(data["locked_skill_set"]),
            "project_library": _render_project_library(data["project_library"]),
            "role_type_prefs": _render_role_prefs(data["role_type_preferences"]),
            "location_prefs": _render_location_prefs(data["location_prefs"]),
            "salary_pref": str(data.get("salary_pref") or "not disclosed"),
        }
    except ProfileImportError:
        raise
    except (TypeError, AttributeError, KeyError) as e:
        raise ProfileImportError(f"Profile export has an unexpected shape: {e}") from e

    telegram = data.get("telegram") or {}
    result["telegram_enabled"] = bool(telegram.get("enabled")) and telegram.get("bot_token") not in (None, "n/a", "")
    result["telegram_bot_token"] = telegram.get("bot_token") if result["telegram_enabled"] else None
    result["telegram_chat_id"] = str(telegram.get("chat_id")) if result["telegram_enabled"] and telegram.get("chat_id") else None

    keys = data.get("groq_keys") or []
    if not isinstance(keys, list) or not keys:
        raise ProfileImportError("groq_keys must be a non-empty list — tailoring needs at least one key")
    result["groq_keys"] = [str(k).strip() for k in keys if str(k).strip()]

    suggested_username = data.get("username")
    result["suggested_username"] = str(suggested_username).strip() if suggested_username else None

    return result

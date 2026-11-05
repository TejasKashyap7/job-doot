"""Applicant profile loading. One YAML per applicant in applier/profiles/ (gitignored)."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("APPLIER_DATA", ROOT / "data" / "applier"))
PROFILES = ROOT / "applier" / "profiles"

DEFAULTS = {
    "chromium": "/usr/bin/chromium",
    "debug_port": 9223,
    "backend_container": "jobhunter-backend",
    "pick_jobs_from_user_id": 1,
    "notify_user_id": 1,
    "min_score": 7,
    "timezone": "Asia/Kolkata",
    "active_hours": [10, 20],     # slots start between these hours (local time)
    "slots_per_day": [6, 8],      # random count per day
    "min_slot_gap_min": 45,
    "max_per_slot": 2,            # applications per slot (spec: 1-2)
    "max_views_per_slot": 12,     # job pages opened per slot while looking for 1-2 to apply to
    "digest_time": "21:30",
    "claude_bin": "~/.local/bin/claude",
    "models": {"primary": "haiku", "retry": "sonnet"},
}


def _expand(v):
    return str(Path(os.path.expanduser(v))) if isinstance(v, str) and v.startswith("~") else v


def load_profile(name: str) -> dict:
    path = PROFILES / f"{name}.yaml"
    raw = yaml.safe_load(path.read_text()) or {}
    cfg = {**DEFAULTS, **raw}
    cfg["models"] = {**DEFAULTS["models"], **(raw.get("models") or {})}
    for key in ("browser_profile_dir", "resume_pdf", "chromium", "claude_bin"):
        cfg[key] = _expand(cfg.get(key))
    cfg["name"] = cfg.get("name") or name
    for key in ("browser_profile_dir", "resume_pdf", "facts"):
        if not cfg.get(key):
            raise ValueError(f"profile {name}: '{key}' is required")
    return cfg

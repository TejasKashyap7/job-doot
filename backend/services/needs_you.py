"""Data for the /needs-you page: every job the applier parked as "needs you", grouped by
problem tag. Spec: .claude/specs/dashboard/needs-you.md. Reads data/applier/applier.db read-only."""
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from services.problem_tags import GREY, NEEDS_YOU_ORDER, classify, plain_reason, site_of, tag_info, url_of

APPLIER_DIR = Path(os.getenv("APPLIER_DATA_DIR", "/app/data/applier"))
OVERVIEW_PARTS = 6      # segmented bar: <= 6 parts, the tail folds into "Other"
TOP_BARS = 8            # ranked bars per section, then "Others"


def _rows(days: int) -> list[dict]:
    db = APPLIER_DIR / "applier.db"
    if not db.exists():
        return []
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
    try:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='attempts'").fetchone():
            return []
        since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds") if days > 0 else ""
        cur = c.execute(
            "SELECT created_at, company, title, url, detail FROM attempts "
            "WHERE detail LIKE 'needs_human:%' AND created_at >= ? ORDER BY created_at DESC", (since,))
        return [dict(zip(("at", "company", "title", "job_url", "detail"), r)) for r in cur]
    finally:
        c.close()


def _bars(counter: Counter) -> list[dict]:
    items = counter.most_common()
    top, rest = items[:TOP_BARS], items[TOP_BARS:]
    # scale to the real entries; the folded tail is grey and capped so it never dominates
    peak = max((n for _, n in top), default=1)
    bars = [{"name": k, "n": n, "pct": round(100 * n / peak, 1), "other": False} for k, n in top]
    if rest:
        n = sum(c for _, c in rest)
        bars.append({"name": f"Others ({len(rest)})", "n": n, "pct": min(100.0, round(100 * n / peak, 1)),
                     "other": True})
    return bars


def build(days: int = 0) -> dict:
    rows = _rows(days)
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key, label = classify(r["detail"])
        r["tag"], r["label"] = key, label
        r["site"] = site_of(url_of(r["detail"]) or r["job_url"])
        r["link"] = url_of(r["detail"]) or r["job_url"]
        r["reason"] = plain_reason(r["detail"])
        r["day"] = (r["at"] or "")[:10]
        groups[key].append(r)

    order = sorted(groups, key=lambda k: (-len(groups[k]),
                                          NEEDS_YOU_ORDER.index(k) if k in NEEDS_YOU_ORDER else 99))
    total = len(rows)
    sections = []
    for key in order:
        g = groups[key]
        info = tag_info(key, g[0]["label"])
        sections.append({
            "key": key.replace(":", "-").replace(" ", "-"), "label": info.label, "color": info.color,
            "means": info.means, "next": info.next, "n": len(g),
            "share": round(100 * len(g) / total) if total else 0,
            "companies": _bars(Counter(r["company"] or "Unknown" for r in g)),
            "sites": _bars(Counter(r["site"] for r in g)) if key == "account_wall" else [],
            "jobs": g,
        })

    # overview: fixed colour per tag (never by rank); tail beyond 6 parts -> "Other" (grey)
    parts = [{"label": s["label"], "n": s["n"], "color": s["color"], "key": s["key"]}
             for s in sections[:OVERVIEW_PARTS]]
    tail = sections[OVERVIEW_PARTS:]
    if tail:
        parts.append({"label": "Other", "n": sum(s["n"] for s in tail), "color": GREY, "key": ""})
    start = 0.0
    for p in parts:
        p["pct"] = 100 * p["n"] / total if total else 0
        # donut slice on a circle whose circumference is 100: dash = share (minus a 2px-ish gap),
        # offset rotates it to start where the previous slice ended (12 o'clock first)
        gap = 0.8 if len(parts) > 1 else 0
        p["dash"] = max(p["pct"] - gap, 0.3)
        p["offset"] = 25 - start
        start += p["pct"]
    return {"total": total, "days": days, "parts": parts, "sections": sections}

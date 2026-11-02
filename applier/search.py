"""Test-mode job source: a LinkedIn job search in the applicant's own browser, Easy Apply
filter on, like a person would do it. Results are not scored (see spec, "Test mode")."""
import logging
import random
import re
import urllib.parse

from . import safety
from .human import Human, pause

log = logging.getLogger(__name__)
MAX_CARDS = 8

CARDS_JS = r"""
() => {
  const out = {};
  const add = (id, el) => {
    if (!/^\d+$/.test(id) || out[id]) return;
    const card = el.closest('li, [data-job-id], .job-card-container') || el;
    const lines = (card.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
    out[id] = { title: lines[0] || '', company: lines.find((l, i) => i > 0 && l !== lines[0]) || '' };
  };
  document.querySelectorAll('[data-job-id],[data-occludable-job-id]').forEach(e =>
    add(e.getAttribute('data-job-id') || e.getAttribute('data-occludable-job-id'), e));
  document.querySelectorAll('a[href*="/jobs/view/"], a[href*="currentJobId="]').forEach(a => {
    const m = a.href.match(/jobs\/view\/(\d+)|currentJobId=(\d+)/); if (m) add(m[1] || m[2], a); });
  return out;
}
"""


class SafetyStop(Exception):
    pass


def search_jobs(page, cfg) -> list[dict]:
    kw = random.choice(cfg.get("search_keywords") or ["AI Engineer"])
    params = {"keywords": kw, "location": cfg.get("search_location", "India"),
              "f_AL": "true", "f_TPR": "r604800"}
    page.goto("https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(params),
              wait_until="domcontentloaded")
    pause(4, 7)
    if (hit := safety.check(page)):
        raise SafetyStop(hit)
    human = Human(page)
    vw, vh = human._viewport()
    human.cursor.move_to({"x": vw * random.uniform(0.2, 0.35), "y": vh * random.uniform(0.4, 0.6)})
    for _ in range(random.randint(2, 4)):          # skim the results list
        human.wheel(random.randint(300, 700))
        pause(1.5, 4)
    found = page.evaluate(CARDS_JS)
    jobs = {int(i): {"title": v["title"], "company": v["company"]} for i, v in found.items()}
    if len(jobs) <= 1:
        # 2026 search page (/jobs/search-results/): cards carry no job ids; the id of the
        # clicked card shows up in the URL as currentJobId. Browse cards like a person.
        cards = page.locator("li").filter(has_text="Easy Apply")
        human.wheel(-2000)
        pause(1, 2)
        for i in range(min(cards.count(), MAX_CARDS + 4)):
            if len(jobs) >= MAX_CARDS:
                break
            card = cards.nth(i)
            try:
                if not card.is_visible():
                    continue
                lines = [l.strip() for l in card.inner_text().split("\n") if l.strip()]
                link = card.locator("a").first
                human.click(link if link.count() else card)
                pause(1.5, 4)
                m = re.search(r"currentJobId=(\d+)", page.url)
                if not m:
                    continue
                lines = [re.sub(r"^Selected, |\s*\(Verified job\)$", "", l) for l in lines]
                jobs.setdefault(int(m.group(1)), {"title": lines[0] if lines else "",
                                                  "company": lines[1] if len(lines) > 1 else ""})
            except Exception as exc:
                log.info("card %d skipped: %s", i, str(exc)[:80])
    log.info("search '%s' -> %d jobs", kw, len(jobs))
    out = [{"id": i, "url": f"https://www.linkedin.com/jobs/view/{i}/",
            "title": (v["title"] or f"LinkedIn job {i}")[:120], "company": v["company"][:80],
            "score": None, "keyword": kw} for i, v in jobs.items()]
    random.shuffle(out)
    return out

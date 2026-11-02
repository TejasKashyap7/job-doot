"""Test-mode job source: a LinkedIn job search in the applicant's own browser, Easy Apply
filter on, like a person would do it. Results are not scored (see spec, "Test mode")."""
import random
import urllib.parse

from . import safety
from .human import Human, pause

CARDS_JS = r"""
() => {
  const out = {};
  const add = (id, el) => {
    if (!/^\d+$/.test(id) || out[id]) return;
    const card = el.closest('li, [data-job-id], .job-card-container') || el;
    const lines = (card.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
    out[id] = { title: lines[0] || '', company: lines.find((l, i) => i > 0 && l !== lines[0]) || '' };
  };
  document.querySelectorAll('[data-job-id]').forEach(e => add(e.getAttribute('data-job-id'), e));
  document.querySelectorAll('a[href*="/jobs/view/"]').forEach(a => {
    const m = a.href.match(/jobs\/view\/(\d+)/); if (m) add(m[1], a); });
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
    jobs = [{"id": int(i), "url": f"https://www.linkedin.com/jobs/view/{i}/",
             "title": v["title"][:120] or f"LinkedIn job {i}", "company": v["company"][:80],
             "score": None, "keyword": kw} for i, v in found.items()]
    random.shuffle(jobs)
    return jobs

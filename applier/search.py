"""Test-mode job source: a LinkedIn job search in the applicant's own browser, Easy Apply
filter on, like a person would do it. Results are not scored (see spec, "Test mode")."""
import logging
import random
import re
import time
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
        # 2026 search page (/jobs/search-results/): results load slowly and cards carry no
        # job ids. Each card shows an "Easy Apply" tag; clicking a card selects it and puts
        # its id in the URL (currentJobId). Browse cards like a person.
        tags = page.get_by_text("Easy Apply", exact=True)
        for _ in range(20):
            if tags.count() > 2:
                break
            time.sleep(1)
        m = re.search(r"currentJobId=(\d+)", page.url)
        if m:
            jobs.setdefault(int(m.group(1)), {"title": "", "company": ""})
        clicked = 0
        for i in range(tags.count()):
            if len(jobs) >= MAX_CARDS or clicked >= MAX_CARDS + 2:
                break
            tag = tags.nth(i)
            try:
                if not tag.is_visible():
                    continue
                # skip the "Easy Apply" filter pill (a button) — clicking it would toggle the filter
                if tag.evaluate("""e => { const b = e.closest('button,[role=button],[aria-pressed],[role=checkbox]');
                                      return !!b && (b.innerText || '').trim().length < 25; }"""):
                    continue
                card_text = tag.evaluate("""e => { let n = e;
                    for (let k = 0; k < 8 && n.parentElement; k++) { n = n.parentElement;
                      if ((n.innerText || '').split('\\n').filter(Boolean).length >= 4) break; }
                    return n.innerText || ''; }""")
                human.click(tag)
                clicked += 1
                pause(1.5, 4)
                m = re.search(r"currentJobId=(\d+)", page.url)
                if not m:
                    continue
                lines = [re.sub(r"^Selected, |\s*\(Verified job\)$", "", l.strip())
                         for l in card_text.split("\n") if l.strip()]
                jobs[int(m.group(1))] = {"title": lines[0] if lines else "",
                                         "company": lines[1] if len(lines) > 1 else ""}
            except Exception as exc:
                log.info("card %d skipped: %s", i, str(exc)[:80])
        log.info("browsed %d cards", clicked)
    log.info("search '%s' -> %d jobs", kw, len(jobs))
    out = [{"id": i, "url": f"https://www.linkedin.com/jobs/view/{i}/",
            "title": (v["title"] or f"LinkedIn job {i}")[:120], "company": v["company"][:80],
            "score": None, "keyword": kw} for i, v in jobs.items()]
    random.shuffle(out)
    return out

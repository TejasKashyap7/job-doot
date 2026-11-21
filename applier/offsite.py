"""Phase 2: apply on the company's own site (the LinkedIn "Apply ↗" button).

Never stalls: CAPTCHAs, account/sign-in walls, email verification and unknown pages
are parked as needs_human (listed in the daily digest) and the run moves on. The agent
does not attempt CAPTCHAs. Design: .claude/specs/apply-agent/approach.md (Phase 2).
"""
import logging
import re
import time

from . import store
from .brain import BrainError, BrainQuota, answer_fields
from .easy_apply import EXTRACT_JS, _errors, _fill, _needs_answer, _snapshot, _visible
from .human import Human, pause

log = logging.getLogger(__name__)

MAX_PAGES = 6

FILL_ATS = ("greenhouse", "lever.co", "ashbyhq", "smartrecruiters", "workable", "recruitee",
            "breezy", "keka", "darwinbox", "zohorecruit", "freshteam", "jobvite", "bamboohr")
ACCOUNT_ATS = ("myworkdayjobs", "workday", "taleo", "icims", "successfactors", "oraclecloud",
               "brassring", "avature", "phenompeople")

CAPTCHA_JS = r"""
() => {
  const box = e => e.getBoundingClientRect();
  const shown = e => { const r = box(e), s = getComputedStyle(e);
    return r.width > 30 && r.height > 30 && s.visibility !== 'hidden' && s.display !== 'none'; };
  for (const f of document.querySelectorAll('iframe')) {
    const s = f.src || '';
    if (!shown(f)) continue;
    if (/recaptcha\/(api2|enterprise)\/anchor/.test(s) && box(f).height > 62) return 'recaptcha checkbox';
    if (/recaptcha\/(api2|enterprise)\/bframe/.test(s) && box(f).height > 100) return 'recaptcha challenge';
    if (/hcaptcha\.com/.test(s)) return 'hcaptcha';
    if (/challenges\.cloudflare\.com/.test(s)) return 'cloudflare turnstile';
  }
  for (const w of document.querySelectorAll('.cf-turnstile, .h-captcha, #px-captcha'))
    if (shown(w)) return 'captcha widget';
  return null;
}
"""

# Pick the form with the most visible fields and mark it as the root.
ROOT_JS = r"""
() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const count = el => [...el.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(vis).length;
  let best = null, n = 0;
  for (const f of document.querySelectorAll('form')) { const c = count(f); if (c > n) { best = f; n = c; } }
  document.querySelectorAll('[data-ja-root]').forEach(e => e.removeAttribute('data-ja-root'));
  (best && n >= 2 ? best : document.body).setAttribute('data-ja-root', '1');
  return { fields: best ? n : count(document.body), password: [...document.querySelectorAll('input[type=password]')].some(vis) };
}
"""

SUBMIT_TEXT = [("submit application", "submit"), ("submit your application", "submit"),
               ("send application", "submit"), ("submit", "submit"), ("apply now", "submit"),
               ("apply", "submit"), ("next", "next"), ("continue", "next"), ("save and continue", "next")]
SKIP_BUTTON = re.compile(r"linkedin|indeed|google|autofill|upload|attach|dropbox|drive|remove|cancel|back", re.I)
DONE_RE = re.compile(r"thank you for (applying|your application|your interest)|application (has been |was )?"
                     r"(received|submitted|sent)|successfully (applied|submitted)|we(?:'ve| have) received your",
                     re.I)
WALL_RE = re.compile(r"create (an |your )?account|sign in to apply|log ?in to apply|verify your email|"
                     r"enter the (code|otp)|one[- ]time (password|code)", re.I)


def _needs_human(why: str, url: str) -> tuple[str, str, int]:
    return "skipped", f"needs_human:{why} | {url}"[:500], 0


def _open_company_site(page, human: Human):
    """Click LinkedIn's offsite Apply button; return the company-site page (new tab or same tab)."""
    btn = None
    for sel in ("button.jobs-apply-button:not(:has-text('Easy'))", "a.jobs-apply-button",
                "button[aria-label*='company website' i]", "a[aria-label*='company website' i]"):
        btn = _visible(page.locator(sel))
        if btn:
            break
    if not btn:
        cand = page.get_by_role("button", name=re.compile(r"^\s*Apply\b(?!.*Easy)", re.I))
        btn = _visible(cand) or _visible(page.get_by_role("link", name=re.compile(r"^\s*Apply\b(?!.*Easy)", re.I)))
    if not btn:
        return None
    ctx = page.context
    before = list(ctx.pages)
    human.click(btn)
    pause(2.5, 4.5)
    for _ in range(2):  # LinkedIn interstitials: "Share your profile?" / safety reminder
        cont = _visible(page.locator("dialog button:has-text('Continue'), [role=dialog] button:has-text('Continue'), "
                                     "dialog a:has-text('Continue'), button:has-text('Continue applying')"))
        if not cont:
            break
        human.click(cont)
        pause(2.5, 4.5)
    new = [p for p in ctx.pages if p not in before]
    target = new[-1] if new else (page if "linkedin.com" not in page.url else None)
    if target:
        try:
            target.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass
        pause(3, 5)
    return target


def _ats(url: str) -> str:
    u = url.lower()
    if any(a in u for a in ACCOUNT_ATS):
        return "account"
    if any(a in u for a in FILL_ATS):
        return "fill"
    return "generic"


def _primary(root):
    btns = root.locator("button, input[type=submit], a[role=button]")
    best = None
    for i in range(btns.count()):
        b = btns.nth(i)
        try:
            if not b.is_visible():
                continue
            txt = " ".join(((b.inner_text() or b.get_attribute("value") or b.get_attribute("aria-label") or "")
                            .lower()).split())
        except Exception:
            continue
        if not txt or SKIP_BUTTON.search(txt):
            continue
        for rank, (key, kind) in enumerate(SUBMIT_TEXT):
            if txt == key or txt.startswith(key):
                if best is None or rank < best[0]:
                    best = (rank, b, kind)
                break
    return (best[1], best[2]) if best else (None, None)


def _upload_resume(site, root, human: Human, cfg) -> bool:
    inputs = root.locator("input[type=file]")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        ctx = inp.evaluate("""e => { let n = e; for (let k = 0; k < 5 && n.parentElement; k++) n = n.parentElement;
                                     return (e.name + ' ' + e.id + ' ' + (n.innerText || '')).toLowerCase(); }""")
        if "cover" in ctx and "resume" not in ctx and "cv" not in ctx:
            continue
        if "resume" in ctx or "cv" in ctx or i == 0:
            inp.set_input_files(cfg["resume_pdf"])
            log.info("  offsite: resume uploaded")
            pause(2, 4)
            return True
    btn = _visible(root.locator("button:has-text('Upload'), label:has-text('Upload'), button:has-text('Attach')"))
    if btn:
        try:
            with site.expect_file_chooser(timeout=8000) as fc:
                human.click(btn)
            fc.value.set_files(cfg["resume_pdf"])
            log.info("  offsite: resume uploaded via chooser")
            pause(2, 4)
            return True
        except Exception as exc:
            log.info("  offsite: upload button gave no chooser: %s", str(exc)[:80])
    return False


def _fill_site(site, cfg, conn, job, human: Human) -> tuple[str, str, int]:
    applicant = cfg["name"]
    url = site.url
    last_err, stuck, uploaded = "", 0, False
    for step in range(1, MAX_PAGES + 1):
        info = site.evaluate(ROOT_JS)
        if (cap := site.evaluate(CAPTCHA_JS)):
            return _needs_human(f"captcha ({cap})", url)
        body = site.inner_text("body")[:20000]
        if info["password"] or (info["fields"] < 3 and WALL_RE.search(body)):
            return _needs_human("account / sign-in required", url)
        if info["fields"] < 2:
            # Description page: click "Apply" / "Apply for this job" first.
            go = _visible(site.locator("a, button").filter(
                has_text=re.compile(r"^\s*(apply( now| for this (job|position|role)| to this job)?|i'?m interested)\s*$", re.I)))
            if go and step <= 2:
                human.click(go)
                pause(3, 5)
                continue
            return _needs_human("no application form found", url)

        root = site.locator("[data-ja-root]").first
        if not uploaded:
            uploaded = _upload_resume(site, root, human, cfg)
        fields = root.evaluate(EXTRACT_JS)
        todo = [f for f in fields if _needs_answer(f)]
        log.info("  offsite step %d (%s): %d fields, to fill: %s", step, url[:60], len(fields),
                 [f["label"][:35] for f in todo])
        if todo:
            try:
                res = answer_fields(cfg, todo, store.answered(conn, applicant), job, last_err)
            except BrainQuota as exc:
                return "skipped", f"quota:{exc}"[:300], step
            except BrainError as exc:
                _snapshot(site, job["id"], "offsite-brain")
                return "failed", f"brain:{exc}"[:300], step
            store.record_made_up(conn, applicant, res.get("made_up"), job["id"])
            if res["unknown"]:
                for fid in res["unknown"]:
                    f = next(x for x in todo if x["id"] == fid)
                    store.add_question(conn, applicant, f["label"], f["type"], f.get("options"), job["id"])
                labels = "; ".join(next(x["label"] for x in todo if x["id"] == u) for u in res["unknown"])
                return "skipped", f"question:{labels}"[:500], step
            _fill(site, root, human, todo, res["answers"])

        if (cap := site.evaluate(CAPTCHA_JS)):
            return _needs_human(f"captcha ({cap})", url)
        btn, kind = _primary(root)
        if not btn:
            btn, kind = _primary(site.locator("body"))
        if not btn:
            _snapshot(site, job["id"], "offsite-nobutton")
            return "failed", f"offsite_no_submit_button | {url}"[:300], step
        before = " ".join(site.inner_text("body").split())[:600]
        log.info("  offsite: clicking %s", kind)
        human.click(btn)
        pause(3.5, 6)

        text = site.inner_text("body")[:20000]
        if DONE_RE.search(text) or re.search(r"/(confirmation|thank|success)", site.url, re.I):
            return "applied", f"offsite:{_ats(url)} | {url}"[:300], step
        if (cap := site.evaluate(CAPTCHA_JS)):
            return _needs_human(f"captcha after submit ({cap})", url)
        if WALL_RE.search(text) and not DONE_RE.search(text):
            return _needs_human("verification / account step after submit", url)
        err = _errors(site.locator("body"))
        after = " ".join(text.split())[:600]
        if err or after == before:
            stuck += 1
            last_err = err or "the form did not accept the submission; a required answer is missing or invalid"
            log.info("  offsite: not accepted (%d): %s", stuck, last_err[:160])
            if stuck >= 2:
                _snapshot(site, job["id"], "offsite-stuck")
                return "failed", f"offsite_stuck:{last_err} | {url}"[:300], step
        else:
            stuck, last_err = 0, ""
    _snapshot(site, job["id"], "offsite-pages")
    return "failed", f"offsite_too_many_pages | {url}"[:300], MAX_PAGES


def apply_offsite(page, cfg, conn, job: dict, human: Human) -> tuple[str, str, int]:
    site = _open_company_site(page, human)
    if site is None:
        return "skipped", "not_easy_apply", 0
    try:
        url = site.url
        log.info("  offsite: company site %s (%s)", url[:90], _ats(url))
        if _ats(url) == "account":
            return _needs_human("account-based ATS", url)
        return _fill_site(site, cfg, conn, job, Human(site))
    except Exception as exc:
        log.exception("offsite crashed")
        return "failed", f"offsite_crash:{type(exc).__name__}: {exc}"[:300], 0
    finally:
        if site is not page:
            try:
                site.close()
            except Exception:
                pass

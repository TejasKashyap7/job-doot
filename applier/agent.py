"""Haiku drives the browser: snapshot -> Haiku decides -> ghost-cursor acts -> repeat.

No page limit and no time limit (Tejas, 2026-11-05). The only stop besides Haiku's own
status is stuck detection: the page looks exactly the same after Haiku's actions 3 times
in a row. Spec: .claude/specs/apply-agent/approach.md -> "Haiku drives the browser".

Returns (status, detail, steps) like easy_apply.apply_to_job:
  applied   "agent:<host>"
  skipped   "question:<q>" | "needs_human:<why> | <url>" | "quota:<msg>" | "not_easy_apply"
  failed    "site:<why> | <url>"  (site problem — does NOT count toward the 3-strike pause)
            "brain:<err>"          (counts)
  paused    "safety:<hit>"         (LinkedIn safety signal — pauses everything)
"""
import logging
import re
import time
from urllib.parse import urlparse

from . import safety, snapshot, store
from .brain import BrainError, BrainQuota, next_actions
from .config import DATA
from .human import Human, pause

log = logging.getLogger(__name__)

STUCK_LIMIT = 3

DONE_RE = re.compile(
    r"thank you for (applying|your application|your interest)|application (has been |was )?"
    r"(received|submitted|sent)|successfully (applied|submitted)|we(?:'ve| have) received your|"
    r"your application (is|has been) (on its way|submitted|received)|you(?:'ve| have) applied", re.I)

ATS_HOSTS = ("greenhouse", "lever.co", "ashbyhq", "smartrecruiters", "workable", "recruitee",
             "breezy", "keka", "darwinbox", "zohorecruit", "freshteam", "jobvite", "bamboohr",
             "myworkdayjobs", "workday", "taleo", "icims", "successfactors", "oraclecloud",
             "brassring", "avature", "phenompeople", "jobs2web", "teamtailor", "personio",
             "hirist", "naukri", "instahyre", "rippling", "pinpointhq", "applytojob", "jazzhr",
             "eightfold", "dayforce", "ultipro", "paylocity", "adp.com")
OFF_LIMITS = ("facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com",
              "accounts.google.com", "glassdoor", "indeed.com", "wa.me", "whatsapp", "t.me")

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


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _base(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "ac", "gov") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _is_linkedin(url: str) -> bool:
    return _host(url).endswith("linkedin.com")


def _shot(page, job_id, tag) -> str | None:
    try:
        shots = DATA / "shots"
        shots.mkdir(parents=True, exist_ok=True)
        path = shots / f"{time.strftime('%Y%m%d-%H%M%S')}_{job_id}_{tag}.png"
        page.screenshot(path=str(path))
        for old in sorted(shots.glob("*.png"))[:-80]:
            old.unlink()
        return str(path)
    except Exception as exc:
        log.warning("screenshot failed: %s", exc)
        return None


def _discard_linkedin(page, human):
    """Close a half-filled Easy Apply dialog without sending it."""
    try:
        for sel in ("button[aria-label='Dismiss']", "dialog button:has-text('Discard')",
                    "button:has-text('Discard')"):
            loc = page.locator(sel)
            for i in range(loc.count()):
                if loc.nth(i).is_visible():
                    human.click(loc.nth(i))
                    pause(1, 2)
                    break
    except Exception:
        pass


class Agent:
    def __init__(self, page, cfg, conn, job, human: Human):
        self.page, self.cfg, self.conn, self.job = page, cfg, conn, job
        self.human = human
        self.ctx = page.context
        self.start_page = page
        self.company_base: str | None = None
        self.history: list[str] = []
        self.note = ""
        self.steps = 0
        self.left_scope = 0
        self.new_pages: list = []
        self.ctx.on("page", lambda p: self.new_pages.append(p))

    # ---------- page bookkeeping ----------
    def _switch_to_newest(self, wait: float = 0) -> bool:
        """A click may open the company site in a new tab, sometimes seconds later
        (LinkedIn shows its own popups first). Wait up to `wait` s for one."""
        end = time.time() + wait
        while True:
            fresh = [p for p in self.new_pages if not p.is_closed()]
            if fresh or time.time() >= end:
                break
            self.page.wait_for_timeout(500)
        self.new_pages.clear()
        if not fresh:
            return False
        self.page = fresh[-1]
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass
        pause(2.5, 4.5)
        self.page.bring_to_front()
        self.human = Human(self.page)
        self.history.append(f"   → a new tab opened and I switched to it: {self.page.url[:120]}")
        return True

    def _in_scope(self, url: str) -> bool:
        if _is_linkedin(url):
            return "/jobs" in url or "/checkpoint" in url or "/authwall" in url or "/login" in url
        host = _host(url)
        if not host or any(b in host for b in OFF_LIMITS):
            return False
        if not self.cfg.get("offsite"):
            return False
        if self.company_base is None:          # first company site reached from LinkedIn
            self.company_base = _base(host)
            return True
        return _base(host) == self.company_base or any(a in host for a in ATS_HOSTS)

    def _close_extra_tabs(self):
        for p in list(self.ctx.pages):
            if p is not self.start_page and not p.is_closed():
                try:
                    p.close()
                except Exception:
                    pass

    # ---------- doing one action ----------
    def _do(self, a: dict, snap: dict) -> str:
        do = a["do"]
        if do == "scroll":
            self.human.wheel(600 if a.get("dir", "down") == "down" else -600)
            pause(0.6, 1.4)
            return f"scrolled {a.get('dir', 'down')}"
        if do == "wait":
            pause(3, 6)
            return "waited"
        if do == "back":
            self.page.go_back(wait_until="domcontentloaded")
            pause(2, 4)
            return "went back"
        if do == "key":
            self.page.keyboard.press(a["key"])
            pause(0.5, 1.5)
            return f"pressed {a['key']}"

        el = snapshot.locate(self.page, snap, a["n"])
        if el is None:
            raise RuntimeError(f"[{a['n']}] is gone from the page")
        info = next(e for e in snap["elements"] if e["n"] == a["n"])
        name = f"[{a['n']}] {info['role']} \"{info['label'][:50]}\""
        if do == "click":
            self.human.click(el)
            return f"clicked {name}"
        if do == "type":
            if el.evaluate("e => e.isContentEditable"):
                self.human.click(el)
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")
                for ch in a["text"]:
                    self.page.keyboard.type(ch)
                    time.sleep(0.08)
            else:
                self.human.type(el, a["text"])
            return f"typed into {name}: {a['text'][:60]!r}"
        if do == "select":
            self.human.hover(el)
            el.select_option(label=a["option"])
            pause(0.4, 1.0)
            return f"selected {a['option']!r} in {name}"
        if do == "check":
            want = bool(a.get("on", True))
            try:
                cur = el.is_checked()
            except Exception:
                cur = info.get("checked", False)
            if cur != want:
                if info["role"] == "checkbox" and not el.is_visible():
                    eid = el.get_attribute("id")
                    lab = self.page.locator(f'label[for="{eid}"]').first if eid else None
                    self.human.click(lab if lab is not None and lab.count() else el)
                else:
                    self.human.click(el)
            return f"{'ticked' if want else 'unticked'} {name}"
        if do == "upload_resume":
            pdf = self.cfg["resume_pdf"]
            is_file = el.evaluate("e => e.tagName === 'INPUT' && e.type === 'file'")
            if is_file:
                el.set_input_files(pdf)
            else:
                with self.page.expect_file_chooser(timeout=8000) as fc:
                    self.human.click(el)
                fc.value.set_files(pdf)
            pause(2.5, 4.5)
            return f"uploaded the resume via {name}"
        raise RuntimeError(f"unknown action {do}")

    # ---------- stops the AI cannot override ----------
    def _hard_stops(self, snap) -> tuple[str, str] | None:
        url = self.page.url
        if _is_linkedin(url):
            if (hit := safety.check(self.page)):
                return "paused", f"safety:{hit}"
        else:
            try:
                cap = self.page.evaluate(CAPTCHA_JS)
            except Exception:
                cap = None
            if cap:
                return "skipped", f"needs_human:captcha ({cap}) | {url}"
        if snap["password"] and not _is_linkedin(url):
            return "skipped", f"needs_human:account / sign-in required | {url}"
        if snap["card"]:
            return "skipped", f"needs_human:payment page | {url}"
        return None

    def _confirmed(self, snap) -> bool:
        txt = snap["text"]
        if _is_linkedin(self.page.url):
            low = txt.lower()
            return "application was sent" in low or "application sent" in low or \
                ("applied" in low and "your application" in low)
        return bool(DONE_RE.search(txt) or re.search(r"/(confirmation|thank|success)", self.page.url, re.I))

    # ---------- main loop ----------
    def run(self) -> tuple[str, str, int]:
        applicant = self.cfg["name"]
        scope = ("You may follow the job's 'Apply' link to the company's own careers site."
                 if self.cfg.get("offsite") else
                 "Only LinkedIn Easy Apply is allowed. If this job only has an external 'Apply' "
                 "(company website), use status give_up with why 'not easy apply'.")
        last_sig, stuck, need_shot = None, 0, False
        while True:
            self.steps += 1
            try:
                snap = snapshot.take(self.page)
            except Exception as exc:
                pause(2, 4)
                snap = snapshot.take(self.page)
                log.info("  snapshot retry after: %s", exc)
            if (stop := self._hard_stops(snap)):
                return (*stop, self.steps)

            sig = snapshot.signature(snap)
            if sig == last_sig:
                stuck += 1
                if stuck >= STUCK_LIMIT:
                    _shot(self.page, self.job["id"], "agent-stuck")
                    seen = next((h.split("page: ", 1)[1] for h in reversed(self.history) if "page: " in h), "the page")
                    tried = "; ".join(h.strip("   ✓✗") for h in self.history[-4:] if h.strip().startswith(("✓", "✗")))[:250]
                    why = (f"I kept trying but the page stayed exactly the same {STUCK_LIMIT} times in a row, so I "
                           f"stopped. I was on: {seen[:120]}. Last things I did: {tried or 'nothing worked'}.")
                    return "failed", f"site:{why} | {self.page.url}"[:900], self.steps
                self.note = (f"The page did NOT change after your last actions ({stuck}x). "
                             "Something is missing or invalid, or you clicked the wrong thing. Try differently.")
            else:
                stuck = 0
            last_sig = sig

            image = _shot(self.page, self.job["id"], "agent-view") if need_shot else None
            need_shot = False
            rendered = snapshot.render(snap)
            try:
                plan = next_actions(self.cfg, snap, rendered, self.job, store.answered(self.conn, applicant),
                                    self.history, self.note, scope, image)
            except BrainQuota as exc:
                return "skipped", f"quota:{exc}"[:300], self.steps
            except BrainError as exc:
                _shot(self.page, self.job["id"], "agent-brain")
                return "failed", f"brain:{exc}"[:300], self.steps
            self.note = ""
            log.info("  [%d] %s | %s | %s", self.steps, plan["page"][:90], plan["status"],
                     "; ".join(f"{a['do']} {a.get('n', a.get('dir', a.get('key', '')))}" for a in plan["actions"])[:200])
            self.history.append(f"step {self.steps} — page: {plan['page'][:100]}")

            st = plan["status"]
            if st == "need_screenshot":
                need_shot, last_sig = True, None
                continue
            if st == "applied":
                if self._confirmed(snap):
                    return "applied", f"agent:{_host(self.page.url)}", self.steps
                self.note = "You said applied, but no confirmation text is visible. Check the page again."
                self.history.append("   → no confirmation visible yet")
                last_sig = None
                continue
            if st == "ask_human":
                if plan["unknown"]:
                    for u in plan["unknown"]:
                        el = next((e for e in snap["elements"] if e["n"] == u.get("n")), {})
                        store.add_question(self.conn, applicant, u["question"], el.get("role", "text"),
                                           el.get("options"), self.job["id"])
                    if _is_linkedin(self.page.url):
                        _discard_linkedin(self.page, self.human)
                    qs = "; ".join(u["question"] for u in plan["unknown"])
                    return "skipped", f"question:{qs}"[:500], self.steps
                return "skipped", f"needs_human:{plan['why'] or 'Haiku asked for help'} | {self.page.url}"[:900], self.steps
            if st == "give_up":
                why = plan["why"] or "gave up"
                if "not easy apply" in why.lower():
                    return "skipped", "not_easy_apply", self.steps
                _shot(self.page, self.job["id"], "agent-gaveup")
                if _is_linkedin(self.page.url):
                    _discard_linkedin(self.page, self.human)
                return "failed", f"site:{why} | {self.page.url}"[:900], self.steps

            # continue: carry out the actions with the ghost cursor
            for i, a in enumerate(plan["actions"]):
                before_url = self.page.url
                self.new_pages.clear()
                try:
                    did = self._do(a, snap)
                except Exception as exc:
                    self.history.append(f"   ✗ {a['do']} {a.get('n', '')} failed: {str(exc)[:120]}")
                    self.note = f"Action {a} failed: {str(exc)[:150]}"
                    break
                self.history.append(f"   ✓ {did}")
                pause(0.4, 1.4)
                el = next((e for e in snap["elements"] if e["n"] == a.get("n")), {})
                may_open = a["do"] == "click" and (i == len(plan["actions"]) - 1 or el.get("new_tab")
                                                   or re.search(r"\bapply\b", el.get("label", ""), re.I))
                opened = self._switch_to_newest(wait=8 if may_open else 0.5)
                if opened or self.page.url != before_url:
                    if not self._in_scope(self.page.url):
                        self.left_scope += 1
                        bad = self.page.url
                        if opened:
                            self.page.close()
                            self.page = self.ctx.pages[-1]
                            self.human = Human(self.page)
                        else:
                            self.page.go_back(wait_until="domcontentloaded")
                        self.history.append(f"   ✗ that went to {bad[:100]} — outside this application, went back")
                        if self.left_scope >= 2:
                            return "failed", ("site:My clicks kept taking me away from the job application "
                                              f"(to {_host(bad)}), so I stopped. | {before_url}")[:900], self.steps
                        self.note = "Your last click left the job application. Do not click it again."
                    break  # new page: look again before doing more
            pause(2.0, 4.0)


def run(page, cfg, conn, job, human: Human) -> tuple[str, str, int]:
    agent = Agent(page, cfg, conn, job, human)
    try:
        return agent.run()
    finally:
        agent._close_extra_tabs()

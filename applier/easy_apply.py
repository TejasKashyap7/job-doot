"""Drive one LinkedIn Easy Apply application, step by step.

Returns (status, detail, steps) where status is applied|skipped|failed|paused and
detail starts with a short machine reason, e.g. "not_easy_apply", "question: ...".
"""
import logging
import random
import re
import time

from . import safety, store
from .brain import BrainError, BrainQuota, answer_fields
from .human import Human, pause

log = logging.getLogger(__name__)

MAX_STEPS = 15

# Marks every form control in the dialog with data-ja="<id>" and describes it.
EXTRACT_JS = r"""
(dialog) => {
  const out = []; let n = 0;
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && (r.width > 0 || r.height > 0); };
  const labelOf = el => {
    if (el.id) { const l = dialog.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return clean(l.innerText); }
    if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
    const l = el.closest('label'); if (l) return clean(l.innerText);
    const fs = el.closest('fieldset'); if (fs && fs.querySelector('legend')) return clean(fs.querySelector('legend').innerText);
    return clean(el.name);
  };
  // 2026 layout: questions are plain text above the control, not linked by <label>.
  // Returns {label, raw}: walks up from the control and reads the block's text with the
  // control itself and its option labels removed (2026 layout has no <label> for questions).
  const contextLabel = (el, stripEls, optTexts) => {
    const optOnly = clean((optTexts || []).join('')).replace(/\s/g, '').toLowerCase();
    (stripEls || []).forEach(x => x && x.setAttribute('data-ja-strip', '1'));
    let n = el;
    for (let i = 0; i < 7 && n && n !== dialog; i++) {
      n = n.parentElement; if (!n) break;
      const c = n.cloneNode(true);
      c.querySelectorAll('[data-ja-strip], input, select, textarea, option, button').forEach(x => x.remove());
      const t = clean((c.textContent || '').replace(/this field is required|\*|\b\d+\/\d+\b|\d+ of \d+ characters/gi, ' '));
      const flat = t.replace(/\s/g, '').toLowerCase();
      if (t.length > 3 && flat !== optOnly && !/^(yes|no)+$/.test(flat))
        return { label: t.slice(0, 300), raw: n.innerText || '' };
    }
    return { label: '', raw: '' };
  };
  const isReq = (el, box) => el.required || el.getAttribute('aria-required') === 'true' ||
    /\brequired\b/i.test(box ? box.innerText : '');
  const seen = new Set();
  for (const el of dialog.querySelectorAll('input, select, textarea')) {
    const tag = el.tagName;
    const type = tag === 'SELECT' ? 'select' : tag === 'TEXTAREA' ? 'textarea' : (el.type || 'text');
    if (['hidden', 'submit', 'button', 'file', 'search'].includes(type)) continue;
    if (type === 'radio') {
      const fs = el.closest('fieldset');
      const key = fs || el.name;
      if (seen.has(key)) continue; seen.add(key);
      const radios = [...(fs ? fs.querySelectorAll('input[type=radio]')
                              : dialog.querySelectorAll(`input[type=radio][name="${CSS.escape(el.name)}"]`))];
      // resume picker cards are radios too — skip them, handled separately
      if (radios.some(r => /document|resume/i.test(r.id + ' ' + r.name))) continue;
      const id = 'f' + (n++);
      const optEl = r => (r.id && dialog.querySelector(`label[for="${CSS.escape(r.id)}"]`)) || r.closest('label')
        || (r.parentElement && r.parentElement.querySelectorAll('input[type=radio]').length === 1
            && clean(r.parentElement.innerText).length > 0 && clean(r.parentElement.innerText).length < 40 ? r.parentElement : null);
      const opts = radios.map((r, i) => { r.setAttribute('data-ja', id + '_' + i);
        const l = optEl(r);
        return clean(l ? l.innerText : (r.getAttribute('aria-label') || r.value)); });
      const ci = radios.findIndex(r => r.checked);
      out.push({ id, type: 'radio', options: opts, value: ci >= 0 ? opts[ci] : '',
        ...(() => {
          if (fs && fs.querySelector('legend')) {
            const lg = fs.querySelector('legend').innerText;
            return { label: clean(lg), required: radios.some(r => r.required) || /\*|required/i.test(fs.innerText) };
          }
          let c = radios[0].parentElement;
          while (c && c !== dialog && !radios.every(r => c.contains(r))) c = c.parentElement;
          const optLabels = radios.map(optEl).filter(x => x && !radios.every(r => x.contains(r)));
          const cl = contextLabel(c || el, [...radios, ...optLabels], opts);
          return { label: cl.label || labelOf(el),
                   required: radios.some(r => r.required || r.getAttribute('aria-required') === 'true')
                             || /\*|required/i.test(cl.raw) };
        })() });
      continue;
    }
    if (type !== 'checkbox' && !vis(el)) continue;
    const id = 'f' + (n++); el.setAttribute('data-ja', id);
    const box = el.closest('[data-test-form-element], .fb-dash-form-element, .jobs-easy-apply-form-element');
    let lab = labelOf(el);
    let ctxRaw = '';
    if (!lab || lab === el.name) {
      const cl = contextLabel(el, [el]);
      lab = cl.label; ctxRaw = cl.raw;
    }
    const f = { id, type, label: lab.slice(0, 300), required: isReq(el, null) || /\*/.test(lab) || /\*|required/i.test(ctxRaw) };
    if (type === 'checkbox') f.value = el.checked ? 'yes' : '';
    else if (type === 'select') {
      // placeholders: "Select an option", "Select...", "Choose", "--", empty value, disabled first option
      const isPh = o => !clean(o.text) || o.value === '' || (o.disabled && o.index === 0)
        || /^(-+\s*)?(select|choose|please (select|choose)|pick)\b.*$|^-+$/i.test(clean(o.text));
      f.options = [...el.options].filter(o => !isPh(o)).map(o => clean(o.text));
      const cur = el.options[el.selectedIndex];
      f.value = cur && !isPh(cur) ? clean(cur.text) : '';
    } else f.value = el.value || '';
    if (el.getAttribute('role') === 'combobox' || el.getAttribute('aria-autocomplete')) f.typeahead = true;
    const holder = box || el.closest('div');
    const err = holder && (holder.querySelector("[role='alert']") || holder.querySelector('.artdeco-inline-feedback--error'));
    if (err) f.error = clean(err.innerText);
    else if (el.getAttribute('aria-invalid') === 'true') f.error = 'marked invalid by the form';
    out.push(f);
  }
  return out;
}
"""

# LinkedIn's 2026 modal: obfuscated classes, buttons identified only by their text.
PRIMARY_TEXT = [("submit application", "submit"), ("submit", "submit"),
                ("review", "review"), ("next", "next"), ("continue", "next")]


def _visible(locator):
    for i in range(locator.count()):
        el = locator.nth(i)
        if el.is_visible():
            return el
    return None


def _dialog(page, wait: float = 12):
    """The Easy Apply modal: a <dialog> inside LinkedIn's #interop-outlet shadow root
    (Playwright pierces open shadow roots). Older layouts used div[role=dialog]."""
    end = time.time() + wait
    while True:
        d = _visible(page.locator("dialog")) or _visible(page.locator(
            "div.jobs-easy-apply-modal, div[role='dialog']"))
        if d or time.time() > end:
            return d
        time.sleep(0.5)


def _primary(dialog):
    btns = dialog.locator("button")
    best = None
    for i in range(btns.count()):
        b = btns.nth(i)
        if not b.is_visible():
            continue
        txt = " ".join((b.inner_text() or b.get_attribute("aria-label") or "").lower().split())
        for rank, (key, kind) in enumerate(PRIMARY_TEXT):
            if txt == key or txt.startswith(key):
                if best is None or rank < best[0]:
                    best = (rank, b, kind)
                break
    return (best[1], best[2]) if best else (None, None)


def _errors(dialog) -> str:
    texts = dialog.locator("[role='alert'], [aria-live='assertive'], .artdeco-inline-feedback--error").all_inner_texts()
    bad = re.compile(r"required|invalid|valid |enter a|please|must|error|select an|too (long|short)|between", re.I)
    return "; ".join(t.strip() for t in texts if t.strip() and bad.search(t) and "success" not in t.lower())


def _snapshot(page, job_id, tag):
    """Screenshot + dialog text while the modal is still open (for debugging)."""
    try:
        from .config import DATA
        shots = DATA / "shots"
        shots.mkdir(parents=True, exist_ok=True)
        stem = shots / f"{time.strftime('%Y%m%d-%H%M%S')}_{job_id}_{tag}"
        page.screenshot(path=f"{stem}.png")
        d = _dialog(page, wait=0)
        if d:
            (shots / f"{stem.name}.txt").write_text(d.inner_text()[:5000])
    except Exception as exc:
        log.warning("snapshot failed: %s", exc)


def _discard(page, human: Human):
    try:
        x = _visible(page.locator("button[aria-label='Dismiss']"))
        if x:
            human.click(x)
            pause(1, 2)
        btn = _visible(page.locator("button[data-control-name='discard_application_confirm_btn'], "
                                    "dialog button:has-text('Discard'), button:has-text('Discard')"))
        if btn:
            human.click(btn)
            pause(1, 2)
    except Exception as exc:
        log.warning("discard failed: %s", exc)


def _handle_resume(page, dialog, human: Human, cfg) -> None:
    """Resume step: if no resume is already chosen, click "Upload resume" like a person
    and give the file picker the applicant's PDF. (LinkedIn's 2026 modal creates the
    file input only when the button is clicked.)"""
    text = dialog.inner_text().lower()
    if "resume" not in text or "upload" not in text:
        return
    if dialog.locator("input[type=radio]:checked, [role=radio][aria-checked=true]").count() > 0:
        return  # a previously uploaded resume is already selected
    btn = None
    for sel in ("label:has-text('Upload resume')", "button:has-text('Upload resume')",
                "[role=button]:has-text('Upload resume')", "label:has-text('Upload')",
                "button:has-text('Upload')"):
        btn = _visible(dialog.locator(sel))
        if btn:
            break
    try:
        if btn:
            with page.expect_file_chooser(timeout=8000) as fc:
                human.click(btn)
            fc.value.set_files(cfg["resume_pdf"])
            log.info("  uploaded resume via file chooser")
        else:
            inp = dialog.locator("input[type=file]")
            if inp.count() == 0:
                log.info("  resume step: no upload control found")
                return
            inp.first.set_input_files(cfg["resume_pdf"])
            log.info("  uploaded resume via file input")
    except Exception as exc:
        inp = dialog.locator("input[type=file]")
        if inp.count():
            inp.first.set_input_files(cfg["resume_pdf"])
            log.info("  uploaded resume via file input (chooser failed: %s)", str(exc)[:80])
        else:
            log.warning("  resume upload failed: %s", exc)
            return
    pause(3, 5)


def _fill(page, dialog, human: Human, fields: list[dict], answers: dict):
    by_id = {f["id"]: f for f in fields}
    for fid, value in answers.items():
        f = by_id[fid]
        t = f["type"]
        if t == "radio":
            idx = f["options"].index(value)
            r = dialog.locator(f'[data-ja="{fid}_{idx}"]').first
            rid = r.get_attribute("id")
            target = dialog.locator(f'label[for="{rid}"]').first if rid else r
            human.click(target)
        elif t == "checkbox":
            el = dialog.locator(f'[data-ja="{fid}"]').first
            want = value.strip().lower() in ("yes", "true", "checked", "1")
            if want != el.is_checked():
                eid = el.get_attribute("id")
                lab = dialog.locator(f'label[for="{eid}"]').first if eid else None
                human.click(lab if lab and lab.count() else el)
        elif t == "select":
            el = dialog.locator(f'[data-ja="{fid}"]').first
            human.hover(el)
            el.select_option(label=value)
        else:
            el = dialog.locator(f'[data-ja="{fid}"]').first
            human.type(el, value)
            if f.get("typeahead"):
                pause(1.2, 2.2)
                opt = _visible(page.locator("[role='listbox'] [role='option']"))
                if opt:
                    human.click(opt)
        pause(0.5, 1.8)


def _needs_answer(f: dict) -> bool:
    if f.get("error"):
        return True
    if f["type"] == "checkbox":
        return f.get("required") and not f.get("value")
    return not f.get("value")


def apply_to_job(page, cfg, conn, job: dict) -> tuple[str, str, int]:
    applicant = cfg["name"]
    human = None
    page.goto(job["url"], wait_until="domcontentloaded")
    pause(3, 6)
    if (hit := safety.check(page)):
        return "paused", f"safety:{hit}", 0
    human = Human(page)
    body = page.inner_text("body").lower()
    if "no longer accepting applications" in body or "not currently accepting applications" in body:
        return "skipped", "closed", 0
    if re.search(r"\bapplied\b \d+ \w+ ago", body) or "application submitted" in body:
        return "skipped", "already_applied", 0

    human.read_page()
    if cfg.get("driver", "agent") == "agent":
        # Haiku looks at the page and decides every click (spec 2026-11-05).
        from .agent import run as agent_run
        return agent_run(page, cfg, conn, job, human)

    btn = None
    for sel in ("button.jobs-apply-button:has-text('Easy Apply')",          # top card
                "button[aria-label*='Easy Apply']",
                ".jobs-s-apply a:has-text('Easy Apply'), .jobs-apply-button--top-card a"):
        btn = _visible(page.locator(sel))
        if btn:
            break
    if not btn:
        if cfg.get("offsite"):
            from .offsite import apply_offsite  # Phase 2: company-site applications
            return apply_offsite(page, cfg, conn, job, human)
        return "skipped", "not_easy_apply", 0
    human.click(btn)
    pause(2, 4)

    steps, last_err, stuck = 0, "", 0
    while steps < MAX_STEPS:
        if (hit := safety.check(page)):
            return "paused", f"safety:{hit}", steps
        dialog = _dialog(page)
        if dialog is None:
            return "failed", "modal_missing", steps
        steps += 1
        _handle_resume(page, dialog, human, cfg)

        fields = dialog.evaluate(EXTRACT_JS)
        todo = [f for f in fields if _needs_answer(f)]
        before = " ".join(dialog.inner_text().split())[:400]
        log.info("  step %d: %d fields, to fill: %s", steps, len(fields),
                 [f"{f['label'][:40]}{' (ERR: ' + f['error'][:40] + ')' if f.get('error') else ''}" for f in todo])
        if todo:
            try:
                res = answer_fields(cfg, todo, store.answered(conn, applicant), job, last_err)
            except BrainQuota as exc:
                _discard(page, human)
                return "skipped", f"quota:{exc}"[:300], steps
            except BrainError as exc:
                _snapshot(page, job["id"], "brain")
                _discard(page, human)
                return "failed", f"brain:{exc}"[:300], steps
            if res["unknown"]:
                for fid in res["unknown"]:
                    f = next(x for x in todo if x["id"] == fid)
                    store.add_question(conn, applicant, f["label"], f["type"], f.get("options"), job["id"])
                _discard(page, human)
                labels = "; ".join(next(x["label"] for x in todo if x["id"] == u) for u in res["unknown"])
                return "skipped", f"question:{labels}"[:500], steps
            log.info("  answers: %s", {next(x["label"][:30] for x in todo if x["id"] == k): v[:30]
                                       for k, v in res["answers"].items()})
            _fill(page, dialog, human, todo, res["answers"])

        primary, kind = _primary(dialog)
        if not primary:
            _snapshot(page, job["id"], "nobutton")
            _discard(page, human)
            return "failed", "no_primary_button", steps
        log.info("  clicking %s", kind)
        human.click(primary)
        pause(2.5, 4.5)

        if kind == "submit":
            for _ in range(15):
                d = _dialog(page, wait=0)
                txt = (page.inner_text("body") + " " + (d.inner_text() if d else "")).lower()
                if "application was sent" in txt or "application sent" in txt or "applied" in txt and "your application" in txt:
                    done = _visible(page.locator("button:has-text('Done'), button[aria-label='Dismiss']"))
                    if done:
                        pause(1, 3)
                        human.click(done)
                    return "applied", "submitted", steps
                time.sleep(1)
            _snapshot(page, job["id"], "noconfirm")
            return "failed", "no_confirmation_after_submit", steps

        dialog = _dialog(page, wait=3)
        after = " ".join(dialog.inner_text().split())[:400] if dialog else ""
        err = _errors(dialog) if dialog else ""
        if after == before or err:
            stuck += 1
            last_err = err or "the form did not move to the next page; some answer is missing or invalid"
            log.info("  form did not advance (%d): %s", stuck, last_err[:200])
            if stuck >= 2:
                _snapshot(page, job["id"], "stuck")
                _discard(page, human)
                return "failed", f"stuck:{last_err}"[:300], steps
        else:
            stuck, last_err = 0, ""
    _snapshot(page, job["id"], "steps")
    _discard(page, human)
    return "failed", "too_many_steps", steps

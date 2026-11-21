"""Page -> text snapshot for Haiku: what's on screen + a numbered list of everything it can
click or type into (like the Chrome extension's read_page). No AI here.

Every listed element gets data-ja-n="<n>" so the agent can find it again. Open shadow
roots (LinkedIn's Easy Apply dialog) and child frames (embedded ATS forms) are included.
Spec: .claude/specs/apply-agent/approach.md -> "Haiku drives the browser".
"""
import hashlib
import json
import logging

log = logging.getLogger(__name__)

MAX_ELEMENTS = 160
MAX_TEXT = 4000

SNAP_JS = r"""
([start, maxEls]) => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const vh = innerHeight;
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity || '1') > 0.05
      && r.width > 1 && r.height > 1; };
  // walk the DOM including open shadow roots
  const all = [];
  const walk = root => { for (const el of root.querySelectorAll('*')) { all.push(el); if (el.shadowRoot) walk(el.shadowRoot); } };
  walk(document);
  all.forEach(e => e.removeAttribute && e.removeAttribute('data-ja-n'));

  const rootOf = el => el.getRootNode();
  const byId = (el, id) => { try { return rootOf(el).querySelector(`[id="${CSS.escape(id)}"]`); } catch (e) { return null; } };
  const labelOf = el => {
    const al = el.getAttribute('aria-label'); if (al) return clean(al);
    const lb = el.getAttribute('aria-labelledby');
    if (lb) { const t = lb.split(/\s+/).map(i => byId(el, i)).filter(Boolean).map(x => x.innerText).join(' '); if (clean(t)) return clean(t); }
    if (el.id) { try { const l = rootOf(el).querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l && clean(l.innerText)) return clean(l.innerText); } catch (e) {} }
    const l = el.closest('label'); if (l && clean(l.innerText)) return clean(l.innerText);
    return '';
  };
  // question text written above a control without a <label> (LinkedIn 2026 / many ATS)
  const ctxText = el => {
    let n = el;
    for (let i = 0; i < 5 && n; i++) {
      n = n.parentElement; if (!n) break;
      const c = n.cloneNode(true);
      c.querySelectorAll('input,select,textarea,button,option,script,style').forEach(x => x.remove());
      const t = clean(c.textContent);
      if (t.length > 2) return t.slice(0, 200);
    }
    return '';
  };
  // a real job-search bar is small: <= 3 fill-in fields and nothing an application form has
  const smallSearchBox = c => {
    const fields = [...c.querySelectorAll('input,select,textarea')].filter(i =>
      !['hidden', 'submit', 'button', 'reset', 'image'].includes((i.type || '').toLowerCase()));
    if (fields.length > 3) return false;
    return !fields.some(i => i.tagName === 'TEXTAREA' || ['file', 'email', 'tel'].includes((i.type || '').toLowerCase()));
  };
  const regionOf = el => {
    if (el.closest('[id*=cookie i],[class*=cookie i],[id*=onetrust i],[class*=onetrust i]')) return 'cookie-banner';
    if (el.closest('dialog,[role=dialog],[aria-modal=true]')) return 'dialog';
    const sb = el.closest('[role=search],form[action*=search i],[class*=search i][class*=bar i]');
    if (sb && smallSearchBox(sb)) return 'search';
    const f = el.closest('form');
    if (f && smallSearchBox(f) && [...f.querySelectorAll('input,button')].some(i => /^search/i.test(clean(i.innerText || i.value || i.getAttribute('aria-label'))) || i.type === 'search')) return 'search';
    if (el.closest('nav,[role=navigation]')) return 'nav';
    if (el.closest('header,[role=banner]')) return 'header';
    if (el.closest('footer,[role=contentinfo]')) return 'footer';
    if (el.closest('[id*=cookie i],[class*=cookie i],[id*=consent i],[class*=consent i],[id*=onetrust i],[class*=onetrust i]')) return 'cookie-banner';
    if (f) return 'form';
    return 'page';
  };
  const bigDialog = e => e.matches && e.matches('dialog[open],[role=dialog],[aria-modal=true]') && vis(e)
    && e.getBoundingClientRect().width > 200 && e.getBoundingClientRect().height > 120;
  const dialogOpen = all.some(bigDialog);
  const SEL = 'a[href],button,input,select,textarea,[role=button],[role=link],[role=checkbox],[role=radio],[role=combobox],[role=option],[role=tab],[role=menuitem],[role=switch],[contenteditable=true],summary';
  const out = []; let n = start; const seen = new Set();
  for (const el of all) {
    if (!el.matches || !el.matches(SEL)) continue;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (tag === 'input' && type === 'hidden') continue;
    const isFile = tag === 'input' && type === 'file';
    const isChoice = tag === 'input' && (type === 'radio' || type === 'checkbox');
    // file inputs and styled radios/checkboxes are often invisible: list them anyway
    if (!vis(el) && !isFile && !isChoice) continue;
    if (dialogOpen && !el.closest('dialog,[role=dialog],[aria-modal=true]')) continue;   // a modal is open: only it matters
    if (el.disabled) continue;
    let role = el.getAttribute('role') || (tag === 'a' ? 'link' : tag === 'select' ? 'select' : tag === 'textarea' ? 'textbox'
              : tag === 'input' ? ({checkbox: 'checkbox', radio: 'radio', file: 'file', submit: 'button', button: 'button',
                                    search: 'searchbox', email: 'textbox', tel: 'textbox', number: 'number', date: 'date',
                                    url: 'textbox', password: 'password'}[type] || 'textbox')
              : tag === 'summary' ? 'button' : tag);
    let label = labelOf(el);
    if (!label && ['button', 'link', 'option', 'tab', 'menuitem'].includes(role)) label = clean(el.innerText || el.value);
    if (!label) label = clean(el.getAttribute('placeholder') || el.getAttribute('title') || el.value || '');
    let question = '';
    if (['textbox', 'select', 'radio', 'checkbox', 'number', 'date', 'combobox', 'searchbox', 'file'].includes(role)) {
      const q = ctxText(el); if (q && q !== label) question = q;
      if (!label) label = clean(el.getAttribute('name') || '');
    }
    if (!label && !question) continue;
    const key = role + '|' + label + '|' + question + '|' + (el.getAttribute('href') || '');
    if (role === 'link' && seen.has(key)) continue;   // the same link repeated in menus
    seen.add(key);
    const r = el.getBoundingClientRect();
    const item = { n, role, label: label.slice(0, 120), region: regionOf(el),
                   onscreen: r.bottom > 0 && r.top < vh };
    if (question) item.question = question;
    if (tag === 'a') { const h = el.getAttribute('href') || ''; if (h && !h.startsWith('javascript')) item.href = h.slice(0, 120);
                       if (el.target === '_blank') item.new_tab = true; }
    if (tag === 'select') {
      item.options = [...el.options].map(o => clean(o.text)).filter(Boolean).slice(0, 40);
      const cur = el.options[el.selectedIndex]; item.value = cur ? clean(cur.text) : '';
    } else if (isChoice) item.checked = el.checked;
    else if (el.getAttribute('aria-checked')) item.checked = el.getAttribute('aria-checked') === 'true';
    else if (['textbox', 'number', 'date', 'searchbox', 'combobox', 'password'].includes(role) && 'value' in el) item.value = (el.value || '').slice(0, 80);
    if (el.required || el.getAttribute('aria-required') === 'true') item.required = true;
    if (el.getAttribute('aria-invalid') === 'true') item.invalid = true;
    if (el.getAttribute('aria-expanded')) item.expanded = el.getAttribute('aria-expanded') === 'true';
    el.setAttribute('data-ja-n', String(n));
    out.push(item); n++;
    if (out.length >= maxEls) break;
  }
  const textRoot = dialogOpen ? all.find(bigDialog) : document.body;
  const errs = all.filter(e => e.matches && e.matches("[role=alert],[aria-live=assertive],.error,.errors,[class*=error-message i],[class*=field-error i],.artdeco-inline-feedback--error") && vis(e))
                  .map(e => clean(e.innerText)).filter(t => t && t.length < 300);
  return { elements: out, next: n, dialog: dialogOpen,
           text: clean(textRoot ? textRoot.innerText : '').slice(0, 6000),
           errors: [...new Set(errs)].slice(0, 10),
           password: all.some(e => e.matches && e.matches('input[type=password]') && vis(e)),
           card: all.some(e => e.matches && e.matches('input[autocomplete^=cc-],input[name*=cardnumber i]') && vis(e)) };
}
"""


def take(page) -> dict:
    """Snapshot the page and its visible child frames. Returns
    {url, title, dialog, text, errors, password, card, elements:[...], frames:{n: frame}}"""
    elements, frames, texts, errors = [], {}, [], []
    dialog = password = card = False
    n = 1
    for fr in page.frames:
        if fr != page.main_frame:
            try:
                fe = fr.frame_element()
                box = fe.bounding_box()
                if not box or box["width"] < 50 or box["height"] < 50:
                    continue
            except Exception:
                continue
        try:
            res = fr.evaluate(SNAP_JS, [n, MAX_ELEMENTS - len(elements)])
        except Exception as exc:
            log.debug("snapshot frame failed: %s", exc)
            continue
        for e in res["elements"]:
            frames[e["n"]] = fr
            if fr != page.main_frame:
                e["frame"] = fr.url[:60]
        elements += res["elements"]
        n = res["next"]
        if res["text"]:
            texts.append(res["text"])
        errors += res["errors"]
        dialog |= res["dialog"]
        password |= res["password"]
        card |= res["card"]
        if len(elements) >= MAX_ELEMENTS:
            break
    try:
        title = page.title()
    except Exception:
        title = ""
    return {"url": page.url, "title": title, "dialog": dialog, "text": "\n---\n".join(texts)[:MAX_TEXT],
            "errors": errors, "password": password, "card": card, "elements": elements, "frames": frames}


def signature(snap: dict) -> str:
    """Fingerprint for stuck detection: same url + same controls/values + same errors."""
    core = [snap["url"].split("#")[0], snap["errors"],
            [(e["role"], e["label"], e.get("value"), e.get("checked")) for e in snap["elements"]]]
    return hashlib.sha1(json.dumps(core, sort_keys=True, default=str).encode()).hexdigest()


def render(snap: dict) -> str:
    """Compact text for the prompt."""
    lines = []
    for e in snap["elements"]:
        bits = [f'[{e["n"]}] {e["role"]} "{e["label"]}"']
        if e.get("question"):
            bits.append(f'question="{e["question"][:160]}"')
        for k in ("value", "checked", "required", "invalid", "expanded", "new_tab"):
            if k in e and e[k] not in (None, "", False):
                bits.append(f"{k}={e[k]}" if not isinstance(e[k], bool) else k)
        if e.get("options"):
            bits.append("options=" + json.dumps(e["options"], ensure_ascii=False))
        if e.get("href"):
            bits.append(f'href={e["href"]}')
        bits.append(f'({e["region"]}{"" if e["onscreen"] else ", below/above the screen"}'
                    f'{", in frame " + e["frame"] if e.get("frame") else ""})')
        lines.append(" ".join(bits))
    return "\n".join(lines) or "(nothing clickable found)"


def locate(page, snap: dict, n: int):
    fr = snap["frames"].get(n)
    if fr is None:
        return None
    loc = fr.locator(f'[data-ja-n="{n}"]').first
    return loc if loc.count() else None

// job-doot home-screen widget for the free iPhone app "Scriptable".
// Shows today's numbers from the Pi over Tailscale (Tailscale app must be ON).
// Spec: .claude/specs/dashboard/phone-widget.md
//
// Setup (2 min): Scriptable > + > paste this file > name it "job-doot" > long-press the
// home screen > + > Scriptable > Small or Medium > Edit widget > Script: job-doot.
// Keep this file ASCII-only (use \u escapes): copying via Safari can mangle UTF-8.

const URL = "http://100.66.138.76:8080/api/summary?key=PASTE_KEY_HERE"   // Pi's Tailscale address + widget key
const COLORS = { green: "#2e7d32", yellow: "#f9a825", red: "#c62828", offline: "#616161" }

async function load() {
  try {
    const r = new Request(URL)
    r.timeoutInterval = 10
    return await r.loadJSON()
  } catch (e) {
    return null
  }
}

function addRow(w, label, value, size) {
  const s = w.addStack()
  const l = s.addText(label)
  l.font = Font.systemFont(size)
  l.textColor = new Color("#ffffff", 0.85)
  s.addSpacer()
  const v = s.addText(String(value))
  v.font = Font.boldSystemFont(size)
  v.textColor = Color.white()
}

const d = await load()
const w = new ListWidget()
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000)   // ask iOS to refresh in ~15 min
const big = config.widgetFamily !== "small"
const size = big ? 14 : 12

if (!d) {
  w.backgroundColor = new Color(COLORS.offline)
  const t = w.addText("job-doot\noffline")
  t.font = Font.boldSystemFont(15)
  t.textColor = Color.white()
  w.addSpacer(4)
  const n = w.addText("Tailscale off or Pi down")
  n.font = Font.systemFont(11)
  n.textColor = new Color("#ffffff", 0.8)
} else {
  w.backgroundColor = new Color(COLORS[d.status] || COLORS.offline)
  const head = w.addText(d.status === "green" ? "job-doot \u2713" : d.status === "red" ? "job-doot \u26A0 CHECK" : "job-doot \u26A0")
  head.font = Font.boldSystemFont(size + 1)
  head.textColor = Color.white()
  w.addSpacer(4)
  addRow(w, "Fetched", d.fetched, size)
  addRow(w, "Applied", big ? `${d.applied} (easy ${d.applied_easy} \u00B7 site ${d.applied_company_site})` : d.applied, size)
  addRow(w, "Need you", d.needs_you, size)
  if (big) addRow(w, "Interviews 7d", d.interviews_7d, size)
  if (d.status !== "green") {
    w.addSpacer(3)
    const why = w.addText(d.scraper !== "healthy" ? `Scraper: ${d.scraper}` : `Applier: ${d.applier}`)
    why.font = Font.systemFont(10)
    why.textColor = Color.white()
    why.lineLimit = 2
  }
  w.addSpacer()
  const u = w.addText(`updated ${d.updated}`)
  u.font = Font.systemFont(9)
  u.textColor = new Color("#ffffff", 0.7)
}

if (config.runsInWidget) Script.setWidget(w)
else await w.presentMedium()
Script.complete()

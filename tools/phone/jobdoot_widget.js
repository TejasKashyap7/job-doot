// job-doot home-screen widget for the free iPhone app "Scriptable" (Apple-style rings).
// Shows today's numbers from the Pi over Tailscale (Tailscale app must be ON).
// Spec: .claude/specs/dashboard/phone-widget.md
//
// Setup (2 min): Scriptable > + > paste this file > name it "job-doot" > long-press the
// home screen > + > Scriptable > Small or Medium > Edit widget > Script: job-doot.
// Keep this file ASCII-only (use \u escapes): copying via Safari can mangle UTF-8.

const URL = "http://100.66.138.76:8080/api/summary?key=PASTE_KEY_HERE"   // Pi's Tailscale address + widget key
const GOALS = { applied: 12, fetched: 30, needs_you: 5 }   // ring is full at these numbers

const RING = {
  applied: new Color("#30d158"),   // green
  fetched: new Color("#0a84ff"),   // blue
  needs_you: new Color("#ff9f0a"), // orange
}
const STATUS = { green: "#30d158", yellow: "#ffd60a", red: "#ff453a", offline: "#8e8e93" }
const BG = new Color("#1c1c1e")

async function load() {
  try {
    const r = new Request(URL)
    r.timeoutInterval = 10
    return await r.loadJSON()
  } catch (e) {
    return null
  }
}

function arc(ctx, cx, cy, r, w, frac, color) {
  if (frac <= 0) return
  frac = Math.min(frac, 0.9999)
  const steps = Math.max(4, Math.ceil(160 * frac))
  const p = new Path()
  let first = null, last = null
  for (let i = 0; i <= steps; i++) {
    const a = -Math.PI / 2 + 2 * Math.PI * frac * (i / steps)
    const pt = new Point(cx + r * Math.cos(a), cy + r * Math.sin(a))
    if (i === 0) { p.move(pt); first = pt } else { p.addLine(pt) }
    last = pt
  }
  ctx.addPath(p)
  ctx.setStrokeColor(color)
  ctx.setLineWidth(w)
  ctx.strokePath()
  ctx.setFillColor(color)   // round caps
  ctx.fillEllipse(new Rect(first.x - w / 2, first.y - w / 2, w, w))
  ctx.fillEllipse(new Rect(last.x - w / 2, last.y - w / 2, w, w))
}

function ring(ctx, cx, cy, r, w, frac, color) {
  const track = new Path()
  track.addEllipse(new Rect(cx - r, cy - r, 2 * r, 2 * r))
  ctx.addPath(track)
  ctx.setStrokeColor(new Color(color.hex, 0.22))
  ctx.setLineWidth(w)
  ctx.strokePath()
  arc(ctx, cx, cy, r, w, frac, color)
}

function drawRings(d, size) {
  const ctx = new DrawContext()
  ctx.size = new Size(size, size)
  ctx.opaque = false
  ctx.respectScreenScale = true
  const c = size / 2, w = size * 0.11, gap = w * 1.15
  ring(ctx, c, c, c - w / 2 - 1, w, d.applied / GOALS.applied, RING.applied)
  ring(ctx, c, c, c - w / 2 - 1 - gap, w, d.fetched / GOALS.fetched, RING.fetched)
  ring(ctx, c, c, c - w / 2 - 1 - 2 * gap, w, d.needs_you / GOALS.needs_you, RING.needs_you)
  return ctx.getImage()
}

function legend(stack, label, value, color, size) {
  const row = stack.addStack()
  row.centerAlignContent()
  const dot = row.addText("\u25CF ")
  dot.font = Font.systemFont(size - 2)
  dot.textColor = color
  const l = row.addText(label)
  l.font = Font.systemFont(size)
  l.textColor = new Color("#ebebf5", 0.75)
  row.addSpacer()
  const v = row.addText(String(value))
  v.font = Font.boldRoundedSystemFont(size + 1)
  v.textColor = color
}

const d = await load()
const w = new ListWidget()
w.backgroundColor = BG
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000)
const small = config.widgetFamily === "small"

if (!d) {
  const t = w.addText("job-doot")
  t.font = Font.boldSystemFont(15)
  t.textColor = Color.white()
  w.addSpacer(6)
  const n = w.addText("offline - Tailscale off or Pi down")
  n.font = Font.systemFont(11)
  n.textColor = new Color(STATUS.offline)
} else {
  const statusColor = new Color(STATUS[d.status] || STATUS.offline)
  const head = w.addStack()
  head.centerAlignContent()
  const title = head.addText("job-doot")
  title.font = Font.boldSystemFont(small ? 13 : 14)
  title.textColor = Color.white()
  head.addSpacer()
  const st = head.addText(d.status === "green" ? "\u25CF ok" : d.status === "red" ? "\u25CF CHECK" : "\u25CF look")
  st.font = Font.boldSystemFont(small ? 11 : 12)
  st.textColor = statusColor
  w.addSpacer(6)

  if (small) {
    const img = w.addImage(drawRings(d, 200))
    img.imageSize = new Size(84, 84)
    img.centerAlignImage()
    w.addSpacer(4)
    const t = w.addText(`${d.applied} applied \u00B7 ${d.needs_you} need you`)
    t.font = Font.systemFont(10)
    t.textColor = new Color("#ebebf5", 0.8)
    t.centerAlignText()
  } else {
    const body = w.addStack()
    body.centerAlignContent()
    const img = body.addImage(drawRings(d, 240))
    img.imageSize = new Size(104, 104)
    body.addSpacer(14)
    const col = body.addStack()
    col.layoutVertically()
    legend(col, "Applied", `${d.applied}/${GOALS.applied}`, RING.applied, 13)
    col.addSpacer(5)
    legend(col, "Fetched", d.fetched, RING.fetched, 13)
    col.addSpacer(5)
    legend(col, "Need you", d.needs_you, RING.needs_you, 13)
    col.addSpacer(6)
    const sub = col.addText(d.status === "green"
      ? `easy ${d.applied_easy} \u00B7 site ${d.applied_company_site} \u00B7 interviews ${d.interviews_7d}`
      : (d.scraper !== "healthy" ? `Scraper: ${d.scraper}` : `Applier: ${d.applier}`))
    sub.font = Font.systemFont(10)
    sub.textColor = d.status === "green" ? new Color("#ebebf5", 0.6) : statusColor
    sub.lineLimit = 2
  }
  w.addSpacer()
  const u = w.addText(`updated ${d.updated}`)
  u.font = Font.systemFont(9)
  u.textColor = new Color("#ebebf5", 0.45)
}

if (config.runsInWidget) Script.setWidget(w)
else await w.presentMedium()
Script.complete()

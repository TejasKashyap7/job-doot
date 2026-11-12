// job-doot home-screen widget for the free iPhone app "Scriptable" (Apple Fitness-style rings).
// Shows today's numbers from the Pi over Tailscale (Tailscale app must be ON).
// Spec: .claude/specs/dashboard/phone-widget.md
//
// Setup: Scriptable > + > paste this file > name it "job-doot" > tap play to preview.
// Then: long-press home screen > + > Scriptable > Medium > Edit Widget > Script: job-doot.
// Keep this file ASCII-only (use \u escapes): copying via Safari can mangle UTF-8.

const URL = "http://100.66.138.76:8080/api/summary?key=PASTE_KEY_HERE"   // Pi's Tailscale address + widget key
const DASHBOARD = "http://100.66.138.76:8080/"   // opened when you tap the widget
const GOALS = { applied: 12, fetched: 30, needs_you: 5 }   // ring is full at these numbers

// Colours taken from the wallpaper: can red, can silver, city-light amber.
const RING = {
  applied: "#ff4a4a",
  fetched: "#f2e4df",
  needs_you: "#ffb547",
}
const STATUS = { green: "#30d158", yellow: "#ffd60a", red: "#ff453a", offline: "#8e8e93" }
const LABEL = new Color("#fff0ec", 0.80)
const FOOT = new Color("#fff0ec", 0.62)
const PLAIN = new Color("#000000")   // card colour

async function load() {
  try {
    const r = new Request(URL)
    r.timeoutInterval = 10
    return await r.loadJSON()
  } catch (e) {
    return null
  }
}

function rotate(cx, cy, a, x, y) {
  return new Point(cx + x * Math.cos(a) - y * Math.sin(a), cy + x * Math.sin(a) + y * Math.cos(a))
}

function ring(ctx, cx, cy, r, w, frac, hex) {
  const track = new Path()
  track.addEllipse(new Rect(cx - r, cy - r, 2 * r, 2 * r))
  ctx.addPath(track)
  ctx.setStrokeColor(new Color(hex, 0.30))
  ctx.setLineWidth(w)
  ctx.strokePath()

  frac = Math.min(Math.max(Number(frac) || 0, 0), 0.9999)
  if (frac <= 0) return
  const color = new Color(hex)
  const a0 = -Math.PI / 2, a1 = a0 + 2 * Math.PI * frac
  const steps = Math.max(4, Math.ceil(180 * frac))
  const p = new Path()
  for (let i = 0; i <= steps; i++) {
    const a = a0 + (a1 - a0) * (i / steps)
    const pt = new Point(cx + r * Math.cos(a), cy + r * Math.sin(a))
    if (i === 0) p.move(pt); else p.addLine(pt)
  }
  ctx.addPath(p)
  ctx.setStrokeColor(color)
  ctx.setLineWidth(w)
  ctx.strokePath()
  // round caps
  const sx = cx + r * Math.cos(a0), sy = cy + r * Math.sin(a0)
  const ex = cx + r * Math.cos(a1), ey = cy + r * Math.sin(a1)
  ctx.setFillColor(color)
  ctx.fillEllipse(new Rect(sx - w / 2, sy - w / 2, w, w))
  ctx.fillEllipse(new Rect(ex - w / 2, ey - w / 2, w, w))
  // small arrow on the leading end, Apple-style
  const arrow = new Path()
  arrow.move(rotate(ex, ey, a1 + Math.PI / 2, -w * 0.22, -w * 0.18))
  arrow.addLine(rotate(ex, ey, a1 + Math.PI / 2, 0, w * 0.12))
  arrow.addLine(rotate(ex, ey, a1 + Math.PI / 2, w * 0.22, -w * 0.18))
  arrow.closeSubpath()
  ctx.addPath(arrow)
  ctx.setFillColor(new Color("#000000", 0.4))
  ctx.fillPath()
}

function drawRings(d, size) {
  const ctx = new DrawContext()
  ctx.size = new Size(size, size)
  ctx.opaque = false
  ctx.respectScreenScale = true
  const c = size / 2, w = size * 0.125, step = w * 1.1
  const r0 = c - w / 2 - 1
  ring(ctx, c, c, r0, w, d.applied / GOALS.applied, RING.applied)
  ring(ctx, c, c, r0 - step, w, d.fetched / GOALS.fetched, RING.fetched)
  ring(ctx, c, c, r0 - 2 * step, w, d.needs_you / GOALS.needs_you, RING.needs_you)
  return ctx.getImage()
}

// "17:36" -> "5:36 PM"
function clock12(hhmm) {
  const [h, m] = String(hhmm).split(":").map(Number)
  if (isNaN(h)) return String(hhmm)
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`
}

function value(stack, v, unit, hex, size) {
  const s = stack.addStack()
  s.bottomAlignContent()
  const t = s.addText(String(v))
  t.font = Font.boldRoundedSystemFont(size)
  t.textColor = new Color(hex)
  if (unit) {
    const u = s.addText(unit)
    u.font = Font.boldRoundedSystemFont(Math.round(size * 0.46))
    u.textColor = new Color(hex)
  }
}

function footer(w, d) {
  const f = w.addStack()
  f.centerAlignContent()
  const sc = new Color(STATUS[d.status] || STATUS.offline)
  const dot = f.addText("\u25CF ")
  dot.font = Font.systemFont(8)
  dot.textColor = sc
  let msg = clock12(d.updated)
  if (d.status === "green") {
    if (d.interviews_7d) msg += ` \u00B7 ${d.interviews_7d} interview${d.interviews_7d > 1 ? "s" : ""}`
  } else {
    // Server picks the most serious problem (reason); old logic kept for an older backend.
    msg = d.reason || (d.scraper !== "healthy" ? `Scraper: ${d.scraper}` : `Applier: ${d.applier}`)
  }
  const t = f.addText(msg)
  t.font = Font.semiboldSystemFont(10)
  t.textColor = d.status === "green" ? FOOT : sc
  t.lineLimit = 1
}

async function build() {
  const family = config.widgetFamily || "medium"
  const w = new ListWidget()
  w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000)
  w.setPadding(13, 15, 13, 15)
  w.url = DASHBOARD   // tap opens the dashboard in Safari instead of Scriptable
  w.backgroundColor = PLAIN

  const d = await load()
  if (!d) {
    w.addSpacer()
    const n = w.addText("offline - Tailscale off or Pi down")
    n.font = Font.semiboldSystemFont(11)
    n.textColor = FOOT
    w.addSpacer()
    return w
  }

  if (family === "small") {
    const top = w.addStack()
    top.centerAlignContent()
    const img = top.addImage(drawRings(d, 200))
    img.imageSize = new Size(80, 80)
    top.addSpacer(10)
    const nums = top.addStack()
    nums.layoutVertically()
    value(nums, d.applied, "", RING.applied, 19)
    value(nums, d.fetched, "", RING.fetched, 19)
    value(nums, d.needs_you, "", RING.needs_you, 19)
    w.addSpacer()
  } else {
    const body = w.addStack()
    body.centerAlignContent()
    const img = body.addImage(drawRings(d, 280))
    img.imageSize = new Size(118, 118)
    body.addSpacer(16)
    const col = body.addStack()
    col.layoutVertically()
    const rows = [
      ["Applied", d.applied, "/" + GOALS.applied, RING.applied],
      ["Fetched", d.fetched, "/" + GOALS.fetched, RING.fetched],
      ["Need you", d.needs_you, "", RING.needs_you],
    ]
    rows.forEach(([label, v, unit, hex], i) => {
      if (i) col.addSpacer(6)
      const r = col.addStack()
      r.centerAlignContent()
      const l = r.addText(label)
      l.font = Font.semiboldSystemFont(13)
      l.textColor = LABEL
      r.addSpacer()
      value(r, v, unit, hex, 24)
    })
    w.addSpacer(4)
  }
  footer(w, d)
  return w
}

const widget = await build()
if (config.runsInWidget) Script.setWidget(widget)
else await widget.presentMedium()   // tapping play in Scriptable shows the widget
Script.complete()

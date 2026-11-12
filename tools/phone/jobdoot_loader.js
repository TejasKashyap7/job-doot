// job-doot widget LOADER for the free iPhone app "Scriptable". Paste THIS file once.
// On every refresh it downloads the real widget code from the Pi over Tailscale and runs it,
// so widget changes arrive by themselves (git push -> Pi -> phone, ~15 min). It keeps the
// last good copy, so if the Pi or Tailscale is down the widget still shows "offline".
// Spec: .claude/specs/dashboard/phone-widget.md -> "Self-updating widget"
//
// Setup: Scriptable > + > paste this file > put your key in KEY > name it "job-doot" > tap play.
// Then: long-press home screen > + > Scriptable > Medium > Edit Widget > Script: job-doot.
// Keep this file ASCII-only: copying via Safari can mangle UTF-8.

const PI = "http://100.66.138.76:8080"   // Pi's Tailscale address
const KEY = "PASTE_KEY_HERE"              // WIDGET_KEY from the Pi's .env

const CODE_URL = PI + "/static/phone/jobdoot_widget.js"
const MARKER = "JOBDOOT_WIDGET_CODE"
const fm = FileManager.local()
const cache = fm.joinPath(fm.documentsDirectory(), "jobdoot_widget_code.js")

async function fetchCode() {
  try {
    const r = new Request(CODE_URL + "?t=" + Date.now())
    r.timeoutInterval = 10
    const code = await r.loadString()
    if (r.response && r.response.statusCode === 200 && code.includes(MARKER)) {
      fm.writeString(cache, code)
      return code
    }
  } catch (e) {}
  return fm.fileExists(cache) ? fm.readString(cache) : null
}

function message(text) {
  const w = new ListWidget()
  w.backgroundColor = new Color("#000000")
  w.addSpacer()
  const t = w.addText(text)
  t.font = Font.semiboldSystemFont(11)
  t.textColor = new Color("#fff0ec", 0.62)
  w.addSpacer()
  return w
}

let widget
const code = await fetchCode()
if (!code) {
  widget = message("job-doot: first load needs Tailscale ON")
} else {
  try {
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
    const run = new AsyncFunction("opts", code + "\nreturn await build(opts)")
    widget = await run({ summaryUrl: PI + "/api/summary?key=" + KEY, dashboard: PI + "/" })
  } catch (e) {
    widget = message("job-doot widget error: " + String(e).slice(0, 80))
  }
}
if (config.runsInWidget) Script.setWidget(widget)
else await widget.presentMedium()   // tapping play in Scriptable shows the widget
Script.complete()

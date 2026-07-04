# Scraper-Agent Audit Playbook — what Claude Code checks, and when

> A scheduled senior audit of the self-healing scraper agent, run by Tejas + Claude Code.
> The dev and auditor agents have context limited to the scraper folder only. Claude Code
> has WHOLE-PROJECT context — so this audit catches the things they structurally cannot see
> (downstream effects, cross-source regressions, slow drift, pipeline-wide health). This is
> the human-supervised backstop that retires the residual "what if it goes wrong" risk left
> by the flaws.

## Why this exists
The dev and auditor were produced by two LLMs across many loops and heavy planning — they
are well-trained, but their view is narrow (scraper folder, one break at a time). They can't
see: whether a fix flooded the database with duplicates, whether fixing source A broke source
B, whether the pipeline has quietly dropped to a single source, or whether their own
"lessons" are slowly drifting toward gaming each other. Claude, reading the whole project,
can. The audit is that whole-context review.

## Cadence
- **First 2 weeks of deployment:** once per day.
- **After 2 weeks:** once per week.
- The 2-week clock starts at on-Pi go-live, not at code-complete.
- **Telegram reminder:** on each audit day, the bot messages Tejas "Claude audit due today"
  (reuses the existing M2/M4 Telegram plumbing). The audit is human-initiated — Tejas opens
  Claude Code and runs it; the reminder ensures it isn't forgotten.
- Escalate back to daily for a week if any audit finds a real problem.

## What Claude must have to do this (context)
- The whole repo (code + all specs + this folder's flaws/approach/concepts).
- The repair ledger: every auto-merge since the last audit (diff, auditor verdict, sample
  data, token cost, timestamp — see SA-Flaw 22).
- The `dev_lessons` and `auditor_lessons` files.
- Recent database rows ingested since the last audit.
- `git log` of agent-authored commits.
- Live access to spot-check a few current pages against what was parsed.

## The checklist — every audit, go through all of these

### A. Data integrity (is the data actually correct?)
- [ ] Spot-check several recently auto-merged fixes: does the parsed data MATCH the live page
      right now? (catches silent poisoning — SA-Flaw 21, and gaming — SA-Flaw 3)
- [ ] Any rows with empty/garbled fields that slipped through? Were they from a broken window
      that should have been quarantined? (SA-Flaw 21)
- [ ] Any fabricated/invented field values where the site actually REMOVED a field? Empty is
      acceptable; invented is poison. (SA-Flaw 26)

### B. Collusion / drift (is the dev gaming the auditor over time?)
- [ ] Take a few auditor "PASS" verdicts and independently re-judge them with whole-project
      ground truth. Is the auditor passing things that are subtly wrong? (SA-Flaw 3, 27)
- [ ] Read new entries in `dev_lessons`: any lesson phrased as "do X so the auditor accepts"
      rather than "do X because the data is actually there"? Reject/curate those. (SA-Flaw 3, 9)
- [ ] Read `auditor_lessons`: did any change make the auditor MORE LENIENT? Auditor evolution
      should only ever ADD checks, never relax them. (SA-Flaw 3)
- [ ] Is either lessons file bloating or self-contradicting (stale lessons describing a layout
      that no longer exists)? Distill/retire. (SA-Flaw 9)

### C. Auditor calibration (is it too strict OR too lenient?)
- [ ] False negatives: is the auditor rejecting GOOD fixes and causing needless escalations?
      (SA-Flaw 24)
- [ ] False positives: is it approving bad ones? (SA-Flaw 27)
- [ ] Do the auditor's thresholds (e.g. description length) still match real data ranges?
      (SA-Flaw 4, 24)

### D. Whole-project / downstream effects (what the agents can't see)
- [ ] Duplicate flood: did any fix change the dedup hash and re-ingest old jobs as new?
      (SA-Flaw 20)
- [ ] Cross-source regression: did a fix for one source break another source's parsing?
      (SA-Flaw 19)
- [ ] Multi-source health: are ALL sources flowing, or has the pipeline quietly dropped to
      one? (SA-Flaw 10)
- [ ] Did any auto-merged fix actually go live (process restarted), or is a good fix committed
      but not running? (SA-Flaw 16)

### E. Operations & budget
- [ ] Any repairs thrashing near the attempt/token caps? Any source burning a disproportionate
      share of the budget? (SA-Flaw 2)
- [ ] Escalation backlog: anything waiting because the senior (Claude) was unavailable?
      Clear it. (SA-Flaw 23)
- [ ] Any source silently down — cookie expired or bot wall — that was NOT escalated?
      (SA-Flaw 5, 6, 13)

### F. Security
- [ ] Any sign of prompt-injection attempts in saved failing pages? (SA-Flaw 15)
- [ ] Any secret (cookie/key/header) leaked into a commit, log, or escalation report?
      (SA-Flaw 25)

## What Claude does when something is found
- **Bad auto-merge:** revert it with git (SA-Flaw 7), then root-cause it.
- **Drift / gaming / miscalibration:** evolve the dev or auditor — a distilled, curated
  lesson, or a tightened auditor check — never a one-off patch (the EVOLUTION principle from
  flaws.md). Re-measure the auditor against the labeled set afterwards (SA-Flaw 27).
- **Downstream damage (duplicates, cross-source break, poisoned rows):** fix the data and the
  cause; add a regression case to the battery (SA-Flaw 11).
- **Anything Tejas should decide:** summarize on Telegram and wait.

## Output of each audit
A short written audit report appended to a running log: date, what was checked, what was
found, what was done, what's still open. The report is the trust record — over the first two
weeks it either earns confidence (clean audits → move to weekly, eventually consider fuller
autonomy) or surfaces problems early while a human is still watching daily.

> Note: this playbook is the concrete resolution for the "repair ledger / drift re-audit /
> revert authority" flaw (SA-Flaw 22) and the human-supervision side of the auditor-trust
> ramp (SA-Flaw 27, SA-Flaw 23).

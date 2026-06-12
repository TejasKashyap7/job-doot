# Self-Healing Scraper Agent — Design Spec

> Status: DRAFT for review. Core idea & architecture: Tejas. This spec captures the
> generator+verifier (developer+auditor) design Tejas reasoned out, the asymmetric
> context flow, the escalation-as-evolution philosophy, plus guardrails agreed in
> discussion. Build target: ~1 focused week. Do NOT build until reviewed & approved.

## The problem
Scrapers break constantly and unpredictably (markup drift, header/API changes, bot
walls, cookie expiry). Manual repair is impractical for a solo dev with a day job — the
cost isn't the fix (~10 min with Claude Code), it's noticing + diagnosing, plus the
silent-poison risk: a subtly-wrong parser feeds garbage JDs into scoring/tailoring and
you apply with resumes tailored to noise. Goal: a system that detects breakage, repairs
the scraper itself in real time, PROVES the repair via an independent auditor,
auto-commits on pass, and escalates only genuinely-unfixable cases — and that EVOLVES so
it needs fewer interventions over time.

## Core principle — two agents, isolated context (Tejas's insight)
1. **Developer agent** — thinks like an experienced scraping dev. Reads the failing
   response + scraper file, reasons about what moved, rewrites the parser, RUNS it,
   extracts fields.
2. **Auditor agent** — a FRESH context with NO knowledge of the developer's reasoning.
   Sees only the extracted output + the source. Judges it cold. Isolation is essential:
   if the auditor saw the developer's justification it would be primed to agree.

## Asymmetric information flow (THE key rule — Tejas)
Information is allowed in exactly ONE direction:
- Auditor's rejection reasons → SHOWN TO the developer. On attempt 2 the dev sees why
  attempt 1 failed; on attempt 3 it sees reasons for 1 and 2. The dev improves from
  feedback, like a junior reading review comments.
- Developer's reasoning / "why my fix is right" → NEVER shown to the auditor. Strictly
  prohibited. Each audit starts from a clean auditor context. This is the one channel
  that could poison the oracle, so it is closed by construction.
- Rejection reasons are persisted to a store the developer can read but that is NEVER
  injected into the auditor's context.

## Guardrails (agreed — non-negotiable)
- **Per-field auditing, not vibe-check.** The auditor receives the STRUCTURED record +
  source URL and verifies each field, not just "is this a JD":
  - title: a role, not a company; < ~120 chars; no HTML.
  - company: plausible org; matches the company named in the description body.
  - location: a place, not boilerplate.
  - description: > ~200 words; reads like a JD (responsibilities/requirements), not nav
    or cookie-banner text.
  - cross-check: record internally consistent AND consistent with the source URL.
  This catches real-but-scrambled parses (company in the title slot, truncated desc,
  wrong job) that a "looks like a job?" check waves through.
- **Two separate exits — UNFIXABLE is immediate; the cap is for thrash.**
  - `UNFIXABLE_IN_CODE` (dev detects a wall: 406/recaptcha, Akamai challenge, login
    redirect) → EXIT THE LOOP IMMEDIATELY, do not wait out the counter. A wall is a wall;
    recoding against it is pure waste. Goes straight to escalation.
  - Attempt cap (default 3) → the SEPARATE exit for "fixable in principle but the dev
    keeps failing." Also goes to escalation.
- **The cap is configurable and is NOT the real cost lever — page payload is.** Tuning
  factors for the cap (to decide with real measurements, not a guessed constant):
  - Dominant token cost per attempt = ingesting the FAILING PAGE, not the loop count.
    LinkedIn's page was 1.3 MB (~300k+ tokens raw — exceeds context windows and a free
    Groq budget). So the high-value lever is PRE-TRIMMING the page (strip scripts/styles,
    extract the relevant DOM subtree, or chunk) before it ever reaches the model. Fix
    that and 3-vs-5 barely matters.
  - Diminishing returns are steep: generator-verifier loops that haven't converged by
    attempt 2-3 almost never converge by 5 — they oscillate. 3 is a sane DEFAULT, not a law.
  - Implement TWO caps, whichever trips first: `max_attempts` (default 3) AND a
    `per_breakage_token_budget`. On a free Groq tier the token budget is the actual safety
    valve. Measure one real repair's token cost, then set both against your tier's RPM/TPM
    and daily caps.
- **Anti-gaming (the GAN risk — real, and we built a channel for it).** Because the dev
  sees the auditor's reasons AND accumulates `dev_lessons`, over many escalations it
  could drift toward "phrase output so the auditor passes" instead of "parse correctly" —
  exactly generator-fools-discriminator / Goodhart's law. Three defenses:
  - Ground the auditor in REALITY, not a memorizable pattern: canary samples + live-source
    cross-check, so "pass" depends on the data actually matching the real page. No static
    rule for the dev to game.
  - Curate `dev_lessons` to be about CORRECTNESS only: any lesson that reads "do X so the
    auditor accepts" is rejected at the human curation gate; only "do X because the data
    is actually there" gets in.
  - During TRAINING (Phase 0 below), the orchestrator watches for output that passes the
    auditor but fails ground truth — that gap IS the collusion signal.

## Escalation = EVOLUTION, not a quick fix  **[CORE LOGIC — HIGHEST PRIORITY]**
When dev + auditor deadlock N times:
1. Both write their version of events. A structured ESCALATION REPORT is stored:
   - sensor's failure classification,
   - developer's attempts (diffs + what it tried + why it thinks it failed),
   - auditor's per-attempt rejection reasons,
   - the raw failing response sample.
2. Telegram alerts Tejas: "Beyond dev + auditor — intervene."
3. Tejas + Claude Code read the full report and do ROOT-CAUSE analysis — not "patch this
   one break" but "what is missing in the dev's or auditor's understanding that let this
   class defeat them." The output is an improvement that pushes the agents in a DIRECTION
   so the class is handled next time without help.
4. **The fix is a durable capability upgrade, never a one-off.** Real-life analogy: a
   junior dev gets stuck, a senior helps, the junior LEARNS it and never trips on that
   class again. Over time, interventions trend toward zero. A patch that fixes today and
   re-breaks later is explicitly a FAILURE of this principle.

### How the agents actually "evolve" (mechanism — honest)
The agents have no trainable weights. "Learning" = a curated, persistent LESSONS store
that feeds their context on every run:
- `dev_lessons.md` — distilled lessons the developer carries forward ("LinkedIn moves
  job IDs into JS blobs, not <a> tags — check raw text"; "prefer the guest API endpoint
  over HTML parsing where one exists").
- `auditor_lessons.md` — additional checks the auditor learned to run.
Rules that keep evolution healthy:
- **Distilled, not raw.** Escalation reports are the raw record; only a SHORT, distilled,
  human-approved lesson enters the lessons store. Dumping raw logs into context bloats it
  and degrades quality over time.
- **Evolve the developer freely; evolve the auditor only by ADDING checks, never
  relaxing them.** The auditor is the safety oracle — it must stay conservative. The
  dangerous drift is an auditor that slowly learns to be lenient so the dev passes.
  Auditor evolution should almost always be "now catches a failure mode it used to miss,"
  never "now tolerates X."
- Every lessons-store change is human-approved at escalation time (curation gate).

## Position on the human gate (honest update)
With a strong, independent, per-field auditor, human approval need NOT block every merge —
the auditor IS the safety oracle. Recommended ramp:
- Phase A: BLOCKING approval for the first ~5 real repairs (you watch it judge correctly).
- Phase B: once trusted, auto-commit on auditor PASS + Telegram proof (3 sample jobs).
  Wrong? `git revert` undoes it in one command. Notification, not a gate — fits a busy
  schedule.

## Non-negotiable prerequisites (build FIRST)
1. **git init the repo.** Auto-merge is only safe because revert is instant. The seatbelt.
2. **Scoped write access.** Developer agent writes ONLY `services/scraper.py` (+ its
   tests). It physically cannot touch `database/` or `data/`. "It deletes my data"
   becomes structurally impossible.
3. **Golden-record schema + canary queries exist before any auto-merge.** The per-field
   rules above, written down, plus a few known-good canary queries whose answers are
   roughly stable. No verifier = no auto-anything. (Highest-skill part; best resume line.)

## Architecture
```
                         ┌─────────────┐
   daily / on-failure →  │   SENSOR    │  probes each source + a CANARY query
                         │ (classifier)│  (LLM reads the response → failure class)
                         └──────┬──────┘
        healthy → normal scrape │ broken → route by class (table below)
                                ▼  (MARKUP_DRIFT / API_CONTRACT only)
                  ┌──────────────────────────┐   attempt ≤ N(=3)
                  │     DEVELOPER AGENT       │◄──────────────────────┐
                  │ + dev_lessons.md context  │   auditor REJECT       │
                  │ + prior rejection reasons │   reason (stored,      │
                  │ rewrites parser, RUNS it  │   shown to dev only)   │
                  │ → record  OR  UNFIXABLE   │                        │
                  └────────────┬──────────────┘                        │
                               │ STRUCTURED record only                │
                               ▼  (NO dev reasoning crosses this line) │
                  ┌──────────────────────────┐                         │
                  │      AUDITOR AGENT        │─────────────────────────┘
                  │ fresh ctx + auditor_      │
                  │ lessons.md + per-field +  │
                  │ canary → ACCEPT / REJECT  │
                  └────────────┬──────────────┘
                  ACCEPT │              │ N rejects OR UNFIXABLE
                         ▼              ▼
            git commit + Telegram   ESCALATION REPORT (both versions)
            proof (3 sample jobs)   → Telegram "intervene" → Tejas+Claude
                                    → root-cause → distilled lesson → evolve
```

## Failure-class routing
| Class | Signal | Action |
|-------|--------|--------|
| MARKUP_DRIFT | 200 OK but 0 jobs / empty fields | dev↔auditor repair loop |
| API_CONTRACT | 400 + "provide valid header" | dev↔auditor repair loop (header/param tweak) |
| BOT_WALL | 406 / "recaptcha required" / Akamai | escalate — no code fix (needs Selenium/browser) |
| COOKIE_EXPIRED | redirect to /login, 401 | escalate — "re-login + save li_at" |
| HEALTHY | jobs returned + fields pass canary | normal scrape |

## The Spies & the Duo — source independence (build alongside; matters MORE than the agent)
Mental model (Tejas):
- **Each source is an independent SPY** that delivers job data on its own. LinkedIn,
  Naukri (friend's Selenium), Indeed, an API source (Adzuna/Jooble) — each runs in its own
  lane. They do NOT share fate.
- **The dev + auditor are a scientist + engineer DUO** who UPGRADE a spy when it breaks.
  While they repair one spy, every other spy keeps working — nothing about the others
  changes. When no spy needs help, the duo is IDLE (not activated, not burning tokens).
Consequences that make this the highest-ROI reliability work:
- **One break = a degraded day, never a blackout.** Remove the single point of failure by
  having ≥3 sources. This is boring (no AI in it) and beats any self-healing agent,
  because the pipeline keeps flowing even while a repair is mid-flight.
- **Per-source isolation:** a repair (or a bot wall) on source A must never block sources
  B/C/D. Each source = its own module, its own health state, its own repair loop instance.
- **Prefer API/guest endpoints over HTML parsing** — spies that talk a stable protocol
  break far less often (the durable LinkedIn fix on 2026-06-12 was moving to the guest
  API, not a cleverer regex). Recruit stable spies first.

## Phase 0 — Bootstrap & Training (Claude Code as the teacher)
The dev and auditor are NOT weight-trained — "training" = Claude Code crafting and
iterating their PROMPTS + lessons files against a test battery until they perform at
"senior" level. Minutes, not gradient training.
- Claude Code spawns (training-time only) up to 3 subagents: a dev-trainer, an
  auditor-trainer, and an ORCHESTRATOR that runs a battery of historical/synthetic
  breakages, scores both agents, and — critically — watches for COLLUSION: output that
  passes the auditor but fails ground truth (the GAN/reward-hacking signal). It keeps the
  dev from learning the auditor's pattern by varying test cases and grounding pass/fail in
  real data, not a static rule.
- Staged rollout (maps to the human-gate ramp): (1) Claude trains + certifies the agents
  on the battery; (2) shadow/blocking mode on the first ~5 REAL breakages with Tejas
  watching; (3) full auto-commit once the auditor has earned trust.
- The orchestrator is a TRAINING-TIME construct. In production the loop + escalation
  already cover its role; it does not run live.

## Model notes
- Sensor + auditor on Groq Llama (Pi) is sufficient BECAUSE the auditor is independent
  and structured — that independence is what lets a modest model be a trustworthy oracle.
  A single self-auditing agent on Llama would NOT be safe.
- Developer (code-gen) wants the strongest model. Start with Claude-Code-triggered (gets
  Claude); graduate to on-Pi Llama code-gen only after the auditor has earned trust.

## Build order (the week)
1. git init + scoped permissions + reuse M2/M4 Telegram plumbing.
2. Golden-record schema + canary queries + auditor checklist (the oracle).
3. Lessons store (`dev_lessons.md`, `auditor_lessons.md`) + injection into agent context.
4. Sensor + failure classifier.
5. Developer agent (repair drafter) — UNFIXABLE verdict, N-cap, reads prior reasons + lessons.
6. Auditor agent (fresh-context, per-field, canary) + accept/reject loop with asymmetric logging.
7. Escalation report + Telegram + the curation gate for lessons.
8. Auto-commit-on-pass; dry-run against a deliberately-broken scraper (inject a bad
   selector, watch it self-heal; inject a bot wall, watch it escalate cleanly).

## Interview value
"Adversarial generator–verifier loop with asymmetric context isolation, a per-field
golden-record oracle, and an escalation-driven lessons store so the agents evolve toward
zero intervention — self-healing a multi-source scraping pipeline, git-reversible." A
genuine agentic-systems portfolio piece.

## Open questions for Tejas
- Developer agent runtime: Claude Code on a cron, or on-Pi Llama? (Recommend Claude-Code
  first.)
- Auto-merge from day 1, or blocking-approval until the auditor earns trust over ~5 real
  breakages? (Recommend blocking first, then flip.)
- Which 3rd source for the multi-source resilience layer? (Adzuna API is a strong, stable
  starting candidate.)

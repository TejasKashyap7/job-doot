# Spec: LinkedIn-only daily cap (VASU-HANDOFF §1)

**Status:** applied 2026-11-21 (Vasu instance). Spec-first per CLAUDE.md.

**Why:** the `daily_targets` cap (set to 15) exists to keep **LinkedIn** applies
under 20/day on the shared PG IP. It must count **only LinkedIn Easy Apply**
applications so unlimited company-site (offsite) applies are never blocked by it.

**How it's distinguished:** in `applier/store.py` `attempts`, a successful offsite
apply logs `detail` beginning `offsite:` (offsite.py), while LinkedIn Easy Apply
logs `detail = "submitted"` (easy_apply.py). No schema change needed.

**Change:**
- `store.applied_since(conn, applicant, since, linkedin_only=False)` — when
  `linkedin_only`, count `status='applied' AND COALESCE(detail,'') NOT LIKE 'offsite:%'`.
- `run.today_progress` passes `linkedin_only=True` when the target comes from
  `daily_targets` (the fixed LinkedIn cap); the test-mode "fetched" target is
  unaffected (test_mode doesn't submit anyway).

**Effect:** offsite/company-site applications don't consume the 15/day LinkedIn
budget — matching §1 ("Company sites / other platforms: no cap from this rule").

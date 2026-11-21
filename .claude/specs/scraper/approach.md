# Spec: scraper keywords/locations for Vasu

**Status:** applied 2026-11-21 (Vasu's instance). Spec-first per CLAUDE.md.

**Why:** defaults in  were Tejas's (research-heavy roles; Gurgaon/Delhi/Noida/Pune/Remote). Vasu's targeting differs.

**Change (fetch net only; per-user scoring still does fine filtering):**
- KEYWORDS -> GenAI/agentic/applied-LLM first (most preferred), then core ML/NLP engineering. Dropped Tejas's research-scientist terms since Vasu targets engineering, not R&D.
- LOCATIONS -> ["Gurgaon","Gurugram","Delhi","Noida","Remote"] (Delhi-NCR cluster + Remote). Dropped Pune.

**Note:** remote-global is hard to express as a location string; "Remote" catches remote listings and the per-user scorer handles global/sponsorship fit. Revisit after a few days of real volume.

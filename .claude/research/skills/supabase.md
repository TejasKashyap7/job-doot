---
title: Supabase
type: skill
verdict: moderate
---
## Evidence
- [[bluparrot]] — managed Postgres for the Agri platform: farm profiles, soil district master, commodity modal-price lookup (state/district/market/variety/grade), crop HI config; service-role access; seed scripts (`scripts/seed.py`, `seed_engine2_tables.py`) [verified-in-code]. Also in sparqnow's dependency stack.

## Resume verdict
Moderate per Tejas's own ruling (real use at BluParrot, Claude-guided). OK on the resume as part of the agri-platform stack ("Supabase farm/commodity data layer"); not a claim of deep Postgres expertise.

## Interview readiness
Can discuss schema design for the advisory engines and service-role vs anon access. Caveat: usage was Claude-guided — keep claims at integration level, not database administration.

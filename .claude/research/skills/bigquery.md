---
title: BigQuery / GCP
type: skill
verdict: weak
---
## Evidence
- [[bluparrot]] — BCL chatbot: LangGraph SQL agent over BigQuery `wealthmaker_prod_fz` with payroll-id multi-tenancy injected at SQL-generation time, local schema.json (no INFORMATION_SCHEMA calls), GCP Secret Manager. **Docs-only on this machine** — the directory holds ARCHITECTURE.md + PlantUML + SQL dump, not running code (Honesty Flag #2).

## Resume verdict
Weak per Tejas's ruling. Do not list BigQuery/GCP in the skills section. If the BCL project is mentioned at all, frame as "architected/documented a multi-tenant BigQuery SQL agent" and confirm code ownership with the company first.

## Interview readiness
Can discuss the architecture (dual-path design, tenancy-at-generation, schema caching) from the docs. Cannot honestly field hands-on BigQuery implementation questions — code is not on disk.

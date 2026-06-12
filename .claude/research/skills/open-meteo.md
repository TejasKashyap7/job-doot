---
title: Open-Meteo (Weather API)
type: skill
verdict: moderate
---
## Evidence
- [[bluparrot]] — weather fetcher (7-day past + 5-day forecast, keyless API) feeding irrigation scoring, crop-protection weather rules, and harvest-window risk classification across all Agri variants [verified-in-code: `data_fetchers/weather.py`].

## Resume verdict
Fine as a supporting mention inside the agri-platform bullet ("live weather via Open-Meteo"); not a standalone skill line. Already in the skills inventory — keep it as context, not a headline.

## Interview readiness
Can describe how forecast data modulates irrigation (0.7× forecast-rain deduction, >30mm cancel override) and spray-delay guardrails. It's a simple REST integration — the interesting part is the agronomic logic built on it.

---
title: Sentinel-2 (Satellite Data)
type: skill
verdict: strong
---
## Evidence
- [[bluparrot]] — Sentinel Hub process API ingestion: OAuth2, server-side band math (B04/B08/B11 → NDVI/NDWI), 5-day revisit walk with ±2-day windows, ≤20% cloud filtering, FLOAT32 GeoTIFF output [verified-in-code: `data_fetchers/satellite.py`]. NDVI timeseries drive crop-stage, yield, and harvest-window engines; documented the Gao-vs-McFeeters NDWI requirement in the client data contract.

## Resume verdict
Yes — LOCKED_SKILL_SET and resume (already in the skills inventory). Phrase as "Sentinel-2 NDVI/NDWI timeseries ingestion (Sentinel Hub API) feeding production agronomic advisory engines".

## Interview readiness
Can discuss band math, cloud filtering, revisit cadence, and the cost lesson (no caching → ~150 calls per 14-month farm, trial burn at ~200 advisories). Caveat: imagery is consumed via Sentinel Hub's API, not raw ESA scenes.

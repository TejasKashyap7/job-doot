---
title: Rasterio (GeoTIFF Processing)
type: skill
verdict: moderate
---
## Evidence
- [[bluparrot]] — in-memory GeoTIFF parsing of Sentinel Hub responses, nanmean aggregation over cloud-edge NaNs in the satellite fetcher [verified-in-code: `data_fetchers/satellite.py`].

## Resume verdict
Mention inside the satellite-ingestion bullet ("rasterio GeoTIFF parsing"), not as a standalone skill. Single-component usage.

## Interview readiness
Can explain reading multi-band FLOAT32 rasters in memory and handling NaN cloud edges. Don't claim broader geospatial-stack experience (reprojection, CRS work, large-mosaic processing) — not evidenced.

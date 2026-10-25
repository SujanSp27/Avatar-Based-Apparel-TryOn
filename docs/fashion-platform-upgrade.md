# Fashion discovery and sizing upgrade — 25 October 2026

## Audit and sequence

Preserve React 19, FastAPI, MongoDB/PostgreSQL, the private Colab FASHN worker,
its model revision/settings, and the existing measurements and comparison UI.
Baseline from the previous milestone: 650 Python and 21 browser checks passed.

1. Enforce account authentication before new inference; preserve private ownership.
2. Source distinct reusable photographs and metadata, then expand data-backed
   discovery, filters and pagination. No manufactured inventory or brand claims.
3. Add explicitly scoped, sourced chart records with region, units, body/garment
   basis and verification. Never use garment dimensions as body measurements.
4. Improve the editorial homepage, catalog, chart controls and image error states.
5. Run API, model, ownership, chart, browser, build and responsive regression checks.

New inventory remains a discovery/reference collection, not a store with verified
stock. Unknown sizes and brands stay unknown. Unsupported layered/draped garments
remain browseable but are not offered to the inference model as supported inputs.

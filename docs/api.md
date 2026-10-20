# Current API contract

Base: `http://127.0.0.1:8000`; generated OpenAPI and interactive schemas at `/docs`.
The application is 2D only. VTON inference uses the user's private Colab worker;
measurement estimation uses CPU MediaPipe. No local GPU or public GPU demo is used.

## Measurement and exact sizing APIs

| Endpoint | Contract |
|---|---|
| `POST /api/v1/measurements/extract` | Multipart `image` (JPEG/PNG), `height_cm`; six approximate dimensions, scale, annotated PNG URL, quality/provenance/warnings |
| `POST /api/v1/sizing/recommend` | JSON `brand_id`, `apparel_id`, `measurements`, optional `chart_version`; exact midpoint-relative error, rankings, `100/(1+E)` heuristic score |
| `GET /api/v1/sizing/brands` | Five India brands, men's/women's verified coverage or explicit source limitations |
| `GET /api/v1/sizing/charts` | Summaries; optional `gender`, `market`, `brand_id` filters |
| `GET /api/v1/sizing/charts/{brand_id}/{apparel_id}` | Full chart; optional `version` |
| `POST /api/v1/sizing/charts` | New immutable chart version; optional configured admin token |

These endpoints use MongoDB. See [measurements and sizing](measurements-and-sizing.md)
for exact schemas, mathematical rules, supported poses, source limitations and
test evidence. The existing browser manual-sizing form uses the legacy endpoint
below; its interval/ease algorithm has not been silently replaced.

## Try-on and legacy APIs

| Endpoint | Contract |
|---|---|
| `GET /api/health` | PostgreSQL connectivity and actual online worker readiness/connection state |
| `GET /api/brands` | Legacy numeric brand IDs, names, slugs, demo flag |
| `POST /api/brands` | `{name,slug,isDemo}`; creates a legacy brand |
| `GET /api/brands/{id}/charts` | `garmentCategory`, optional immutable `version` |
| `GET /api/brands/{id}/chart-versions` | Category chart version history |
| `POST` or `PUT /api/brands/{id}/charts` | Newer chart version; existing versions cannot be overwritten |
| `POST /api/sizing/recommend` | `{brandId,garmentCategory,fitPreference,measurements}`; legacy weighted interval-distance score with ease adjustments |
| `POST /api/tryon` | Person/garment uploads; real generated image or typed failure |
| `GET /api/tryon/jobs/{uuid}` | Persisted job state/progress/result/error |
| `GET /api/runs/{uuid}` | Persisted run status and metadata |
| `DELETE /api/runs/{uuid}` | Removes the run's assets and SQL record; rejects running jobs |
| `GET /api/samples/person` | Credited public full-body sample |
| `GET /api/samples/garment` | Synthetic striped garment fixture |

Try-on multipart fields: `personImage`, `garmentImage`, `garmentCategory`,
optional `garmentPhotoType` (`flat-lay` or `model`), optional numeric `brandId`,
`fitPreference` (`regular` default) and `tryonMode` (`2d` only).
All eleven garment categories are enumerated by OpenAPI. Inputs are decoded,
not trusted by filename/MIME: JPG/PNG/WebP, minimum 128 px per side, maximum
20 MP and 12 MB per upload. Content-Length is required.

The browser sends `Prefer: respond-async` and a UUID `Idempotency-Key`.
Admission returns 202 and `Location`/`statusUrl`; poll for `queued`, `processing`,
`success` or `failed`. Success contains the actual result; failure contains
`error:{code,message}`. Reusing a key with identical inputs returns the same job;
different inputs with that key return 409. Concurrent generation admission
returns 429. Without `Prefer`, synchronous generation is supported.

The single-process coordinator persists state in `.runtime/tryon-jobs`.
Interrupted jobs are marked failed on API restart and are never automatically
replayed. Browser refresh resumes polling without uploading or regenerating.
Run one Uvicorn worker. Actual model inference happens in the private Colab.

Image generation returns real PNG URLs, original/result comparison, provenance,
timings and limitations. It does not return a mesh or image-derived physical
size recommendation. Missing worker/model, invalid clothing/mask, network and
quality-gate failures return errors; no pasted-overlay fallback is used.
HTTP success and transport-category support do not prove visual quality.

Legacy chart intervals describe body measurements in cm: chest, waist, hip,
optional shoulder. Tight/loose ease adjustments and interval-distance scoring
remain unchanged. These scores and the new midpoint score are separate contracts;
neither is a statistically calibrated probability.

## Errors and local data

Pipeline errors use `{error:{code,message}}`. Invalid fields use FastAPI's
standard 422 `detail`. Database/model unavailable errors return 503, unsupported
inputs 422, missing charts 404, immutable-version conflicts 409, upload excess
413 and occupied processing capacity 429.

Set `ADMIN_TOKEN` and supply `X-Admin-Token` for chart/brand mutations and run
deletion. When unset, mutations are permitted for local development. The app
does not implement public multi-user authentication or asset isolation.
Uploads, intermediate outputs, annotations and diagnostic records persist
locally until deleted; do not expose private runtime credentials or data publicly.

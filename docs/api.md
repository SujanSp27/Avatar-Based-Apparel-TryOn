# Current API contract

Base: `http://127.0.0.1:8000`; generated OpenAPI and interactive schemas at `/docs`.
The application is 2D only. VTON inference uses the user's private Colab worker;
measurement estimation uses CPU MediaPipe. No local GPU or public GPU demo is used.

## Measurement and exact sizing APIs

| Endpoint | Contract |
|---|---|
| `POST /api/v1/measurements/extract` | Multipart `image` (JPEG/PNG), `height_cm`; saved `measurement_id`, six approximate dimensions, scale, annotated PNG URL, quality/provenance/warnings |
| `POST /api/v1/measurements/extract-and-recommend` | Same upload plus `brand_id`, `apparel_id`, optional `chart_version`; `{extraction,recommendation}` from one CPU inference |
| `GET /api/v1/measurements` | Admin-protected history; `limit` 1–100, `offset` >=0; `{items,total,limit,offset}` |
| `GET /api/v1/measurements/{measurement_id}` | Saved estimates, provenance, UTC creation time; no new inference |
| `GET /api/v1/measurements/{measurement_id}/annotation` | Actual annotated PNG; missing record/file returns 404 |
| `DELETE /api/v1/measurements/{measurement_id}` | Admin; removes MongoDB record, annotation, mask and diagnostic JSON; 204 |
| `POST /api/v1/sizing/recommend` | JSON `brand_id`, `apparel_id`, exactly one of `measurements` or saved `measurement_id`, optional `chart_version`; exact midpoint-relative error, rankings, `100/(1+E)` heuristic score |
| `GET /api/v1/sizing/categories` | Eleven sizing categories, default dimensions and normalized weights; independent of chart availability or visual VTON quality |
| `GET /api/v1/sizing/brands` | Requested India brands, actual available charts, source limitations; `include_demo=true` adds fictional fixtures |
| `POST /api/v1/sizing/brands` | Admin; `{brand_id,brand_name,market,official_url?,description?}`; new brand, 201 |
| `GET /api/v1/sizing/brands/{brand_id}` | One brand, sourced coverage and currently available charts |
| `PATCH /api/v1/sizing/brands/{brand_id}` | Admin; update name, official URL or description; historical chart provenance remains unchanged |
| `GET /api/v1/sizing/charts` | Summaries; `gender`, `market`, `brand_id`, `category`, `latest_only`; `limit` 1–500 and `offset` >=0 |
| `GET /api/v1/sizing/charts/{brand_id}/{apparel_id}` | Full chart; optional `version` |
| `GET /api/v1/sizing/charts/{brand_id}/{apparel_id}/versions` | Immutable version history, newest first |
| `POST /api/v1/sizing/charts` | New immutable chart version; optional configured admin token |

These endpoints use MongoDB. See [measurements and sizing](measurements-and-sizing.md)
for exact schemas, mathematical rules, supported poses, source limitations and
test evidence. The existing browser manual-sizing form uses the legacy endpoint
below; its interval/ease algorithm has not been silently replaced.

## Health and readiness

| Endpoint | Contract |
|---|---|
| `GET /api/v1/health/live` | 200 if the API process can serve requests; no database or inference |
| `GET /api/v1/health` | Aggregate component status, independent `sizing`, `measurements`, `tryon` capability flags; 200 even if degraded |
| `GET /api/v1/health/ready?capability=all` | 200 when requested capability is ready, otherwise 503; accepts `sizing`, `measurements`, `tryon`, `all` |

Readiness pings PostgreSQL/MongoDB, checks the pose checkpoint's presence and
reads the background Colab monitor. It never runs inference or proves image
quality. The `pose_model.inference_validated` flag is false for this lightweight
probe. A missing Colab does not disable measurement/sizing APIs; a SQL outage
does not prevent the independent MongoDB routes from starting.

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
| `GET /api/runs` | Admin-protected paginated run summaries; `limit` 1–100, `offset`, optional `status` (`processing`, `success`, `failed`); no raw diagnostic metadata |
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
Unreadable saved job files are retained and skipped at startup; querying or
resubmitting their ID returns 503 rather than replacing them or rerunning inference.
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

Responses include `X-Request-ID`; 429/503 include `Retry-After: 5`. CORS exposes
these headers and asynchronous `Location` to the browser. Unexpected failures
return a sanitized 500 and request ID; driver credentials and tracebacks are not
sent to clients. Field-validation errors retain FastAPI's standard 422 format.

Set `ADMIN_TOKEN` and supply `X-Admin-Token` for chart/brand mutations and run
deletion, measurement deletion, and measurement/run history listings. When unset,
these operations are permitted for local development. The app
does not implement public multi-user authentication or asset isolation.
Uploads, intermediate outputs, annotations and diagnostic records persist
locally until deleted; do not expose private runtime credentials or data publicly.

Measurement deletion removes files before the MongoDB document. If filesystem
cleanup fails, metadata remains for retry. There is no distributed transaction
between disk and MongoDB: retry a failed deletion if the database went offline
after files were removed. Immutable chart versions are retained rather than
deleted so saved recommendation provenance remains meaningful.

Verification: `scripts/verify_backend_api.py` exercises actual local HTTP,
CPU MediaPipe, MongoDB persistence, saved-record sizing and artifact deletion.
It deletes only the measurement it creates and submits no try-on generation.
Current evidence is in `experiments/backend-completion/`.

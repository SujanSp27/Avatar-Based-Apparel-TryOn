# API contract

Base: `http://127.0.0.1:8000`; interactive schema at `/docs`.
No external inference API is used. Local PNG/JPEG/WebP content is decoded and inspected;
client MIME types and filenames do not determine validity. Max 12 MB/image and 20 MP; minimum
256 px per side except 2D garment inputs (128 px). Multipart try-on requests require Content-Length. A single job is admitted;
parallel submissions receive 429. Heavy inference executes in a FastAPI worker thread.

| Endpoint | Contract |
|---|---|
| `GET /api/health` | DB connectivity, actual DB dialect, 3D backend identity, and `vton2d` availability/device/categories/quality-validation state |
| `GET /api/brands` | IDs, names, slugs and explicit demo flag |
| `POST /api/brands` | JSON `{name, slug, isDemo}`; returns 201; unique name and slug |
| `GET /api/brands/{id}/charts` | `garmentCategory`, optional `version`; latest immutable version by default |
| `GET /api/brands/{id}/chart-versions` | Category-specific version history |
| `POST` or `PUT /api/brands/{id}/charts` | JSON `{garmentCategory, version, source, sizes:[...]}`; newer versions only |
| `POST /api/sizing/recommend` | JSON `{brandId, garmentCategory, fitPreference, measurements}`; no images required |
| `POST /api/tryon` | Multipart fields below; full pipeline result with real relative asset URLs |
| `GET /api/tryon/jobs/{uuid}` | Persisted asynchronous job state, actual generation progress, final result or typed failure |
| `GET /api/runs/{uuid}` | Persisted run status and metadata |
| `DELETE /api/runs/{uuid}` | Removes that run's inputs/outputs and SQL record; refuses running jobs |
| `GET /api/samples/person` | Downloaded, credited public full-body example |
| `GET /api/samples/garment` | Locally drawn synthetic garment test fixture |

Try-on fields: `personImage`, `garmentImage`, `brandId`, `garmentCategory` (t-shirt/shirt/dress/trouser),
`fitPreference` (tight/regular/loose), optional `tryonMode` (`auto` default, `3d` or `2d`),
optional `heightCm` (120–220; default explicitly assumed
170), optional `garmentLengthCm` and `garmentWidthCm`. Dimension overrides are experimental;
templates use body/size priors when no physical garment dimensions are known. A photo's
pixel dimensions are never described as known physical dimensions.

The browser sends `Prefer: respond-async` and a UUID `Idempotency-Key` with the upload.
The API acknowledges admission with HTTP 202 and a `Location`/`statusUrl`; clients poll
that URL for `queued`, `processing`, `success` or `failed`. `success` contains the real
pipeline `result`; `failed` contains `error: {code, message}`. Progress is emitted by
the pipeline, including completed diffusion steps, rather than estimated percentages.
Without `Prefer`, the existing synchronous API remains available. The capacity limit
is shared by both paths. Reusing a key with identical bytes and parameters returns the
same job; different inputs with that key return 409. Busy admission returns 429.

Job metadata is saved in `.runtime/tryon-jobs`. The UI retains the last job UUID in
local storage and resumes polling after refresh without resubmitting the images.
Completed results can be reloaded; failed/missing jobs are cleared from browser storage.
The worker is single-process and does not survive a server restart: interrupted jobs
are marked failed with their artifacts retained, never automatically replayed. Run
one Uvicorn worker. This local queue is not a distributed or authenticated service.
Colab notebook evaluation is separate; these HTTP jobs still run on the local machine.

In `auto`, allowlisted full-body validation/reconstruction failures can invoke pretrained
2D generation when the input and model support it. Explicit `3d` preserves strict validation;
explicit `2d` skips mesh generation. The UI defaults to explicit `2d`; API requests omitting
the field still use `auto`. CatVTON supports `t-shirt` and `shirt` only in this integration;
`dress` and `trouser` return `vton_category` if routed to 2D. Invalid images, missing visible
clothing or insufficient landmarks return typed errors. Person images retain the 256 px
minimum; a 2D garment may be 128 px per side. Other upload bounds are unchanged.

Successful 2D responses have `mode: "2d"`, `renderingMethod: "pretrained-vton"`, real PNG
`previewUrl` and `originalUrl`, plus checkpoint provenance, semantic-mask artifacts, timings
and limitations in `warnings`. `measurements`, `recommendedSize`, `bodyUrl`, `garmentUrl`
and `avatarUrl` are null. CatVTON generates clothing from the uploaded person, segmented
garment and white-edit clothing mask. Original face/background and other protected pixels
are restored according to human parsing. It does not reconstruct an avatar or determine
physical dimensions; `/api/sizing/recommend` remains independently available. Clients must
branch on `mode` and require the neural `renderingMethod` before showing a 2D result.

`photoAlignment.qualityValidated` is false until a documented visual evaluation supports a
stronger claim. HTTP success means inference/export completed, not that sleeves, neckline,
stripes or old-shirt removal meet the acceptance criterion. Missing dependencies/checkpoints,
invalid checkpoint hashes, unavailable CUDA and memory/load failures return typed errors
(normally 503); invalid category/mask/clothing requests normally return 422. No failure
falls back to the debug image-overlay module. Health readiness does not prove checkpoint
loading or output quality; actual model loading verifies safetensors hashes and state keys.

Chart sizes: `sizeLabel`, `sortOrder`, `chestMin/Max`, `waistMin/Max`, `hipMin/Max`, optional
paired `shoulderMin/Max`. All intervals are body measurements in cm, not garment flat widths.
Duplicate sizes/orders, reversed ranges, missing paired ranges and reused versions fail.
Brand, chart-version and size-row tables are normalized with keys and SQL constraints.

Sizing response includes size, fit, weighted normalized interval-distance score, each
measurement's explanation, full candidate ranking, out-of-range flag and chart version/source.
Tie-breaks use distance from interval midpoints then declared size order. Tight and loose
shift target body circumferences by -2/+4 cm; shoulder target shifts by one quarter that amount.
Weights are category-specific. Scores are not probabilities. Explanations describe distance
relative to the preference-adjusted target, not empirically verified clothing comfort.

Successful 3D try-on returns `mode: "3d"`, `runId`, `brandName`, measurements/uncertainty, `bodyUrl`,
`garmentUrl`, `avatarUrl`, `previewUrl`, artifact URLs, model provenance, fitting diagnostics,
warnings, per-stage latency and final process RSS. GLB export is reloaded and inspected
before success. Previews use a simple orthographic rasterizer; the browser GLB contains the
actual photo texture. The preview's garment uses average fabric color, not photorealistic rendering.

Errors: `{error:{code,message}}` for pipeline errors; Pydantic validation uses standard FastAPI
422 `detail`. Internal exceptions return a safe stage/run identifier and are logged locally.
Failures after admission preserve input bytes, available intermediates, checkpoint SHA-256,
settings and error metadata in a UUID directory. Input data is local and unencrypted; anyone
with filesystem access can read it. No automatic retention policy is imposed.

Set `ADMIN_TOKEN` and supply `X-Admin-Token` for brand/chart mutation and run deletion. When
unset, those operations are permitted for local development. This is not a public multi-user
service; there is no user authentication, access isolation or object-storage implementation.

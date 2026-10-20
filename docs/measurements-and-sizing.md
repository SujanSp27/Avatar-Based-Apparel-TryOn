# Body estimates and brand sizing

Implemented on 20 October 2026. These are independent backend APIs; they do not
change the existing try-on model or infer dimensions from a generated outfit.
The existing browser's manual sizing form still uses the legacy PostgreSQL API.
The new APIs are usable at http://127.0.0.1:8000/docs.

## Runtime and storage

- `backend/app/anthropometry/pose_adapter.py`: MediaPipe Tasks Pose Landmarker
  Full, 33 normalized xyz/visibility and 33 world landmarks. CPU delegate only.
- `measurement_service.py`: deterministic geometry, silhouette sections,
  validation and annotated output.
- `sizing_engine.py`: independent, exact midpoint-relative scoring.
- `schemas.py`, `router.py`: Pydantic v2 validation and FastAPI contracts.
- `repository.py`: PyMongo, `brand_size_charts`, `measurement_brands` and
  `body_measurements` collections. A chart version embeds all sizes in a single
  atomic document. Unique `(brand_id, apparel_id, version)` index prevents overwrites.
- Existing VTON runs and the legacy size API remain in PostgreSQL. This is not
  a migration of the entire application's database.

`scripts/setup.ps1` installs the pinned local dependencies and verifies the
official pose checkpoint. `scripts/start.ps1` starts/verifies both databases.
The Windows launcher discovers installed MongoDB Community; alternatively use
the `measurements-db` service in `docker-compose.yml`. The current machine runs
MongoDB Community 8.2.2 at loopback port 27018. Its data is in `.runtime/mongodb/`.

Configuration is in `.env.example`: `MONGODB_URI`, `MONGODB_DATABASE`,
`MEASUREMENT_MODEL_PATH`, `MEASUREMENT_OUTPUT_ROOT`. URI credentials are not
included in API errors. No MongoDB Atlas account or cloud upload is needed.
Pose checkpoint download: `scripts/download_measurement_model.py`, SHA-256
`5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1`.

## Measurement extraction

`POST /api/v1/measurements/extract`

Multipart fields:

| Field | Requirement |
|---|---|
| `image` | Actual JPEG/PNG, at least 256 px per side, at most 20 MP and 12 MB |
| `height_cm` | Finite, self-reported height, 80–250 cm |

Content-Length is required. EXIF orientation, alpha and ICC colour profiles are
normalized; the image is resized to at most 1600 px. One inference at a time is
admitted; overlapping measurement requests receive 429, independently of VTON.

Use a front-facing, upright full-body photograph with straight uncrossed legs,
level shoulders, arms apart, close-fitting clothing and a contrasting background.
Nose, both shoulders, hips, knees, ankles and heels must have visibility **>0.65**.
Multiple detected people, missing landmarks, side views, crossed/bent legs,
ambiguous torso/arm boundaries and merged thigh outlines are rejected with 422.
Landmark visibility is not calibrated measurement confidence.

Calculation:

1. `H_px = max(ankle_y[27,28]) - min(visible_face_y[0..10])`.
2. `S = height_cm / H_px`; x/y coordinates are converted to pixels before distances.
3. Shoulder: Euclidean 11–12 distance × S.
4. Chest and waist: connected silhouette width × S × 2.45 / 2.30.
5. Hip: Euclidean 23–24 distance × S × 2.40, exactly as requested.
6. Thigh: mean of separately visible upper-thigh sections × S × 2.50.
7. Inseam: mean Euclidean distance from hip midpoint to ankles 27/28 × S.

Image-guided GrabCut refines the coarse pose mask on CPU with a fixed seed.
Torso sections intersecting arm centerlines are excluded. Chest uses the first
clear section between 25% and 45% down the shoulder-to-hip axis; waist uses 50%.
Thigh sections are at 40% down each hip-to-knee axis, perpendicular to the leg.
Five nearby sections are median-filtered. The selected positions are returned.
These choices are documented heuristics, not anatomical landmark ground truth.

The response contains `scale_factor`, all six `measurements` in cm,
`annotated_image_url`, geometry, quality, model/input hashes and warnings.
The annotation, refined mask and diagnostic JSON are stored under
`data/processed/measurements/annotated/`; metadata is saved in MongoDB. If the
database write fails, new artifacts are cleaned up and the endpoint returns 503.

**Accuracy limits:** MediaPipe has no crown or crotch point. Face-to-ankle height
scaling and hip-midpoint inseam are biased. Hip *joint spacing* is substantially
narrower than the outside of the hips: the specified multiplier yielded **52.44
cm** on the studio example and must not be treated as its true hip circumference.
The chest section can fall below the fullest bust; loose clothing affects widths.
The returned warnings explicitly state these limitations. Confirm dimensions
with a tape measure before relying on size advice. No ground-truth anthropometric
accuracy, MAE or calibrated uncertainty is claimed.

## Size recommendation

`POST /api/v1/sizing/recommend`

```json
{
  "brand_id": "nike",
  "apparel_id": "nike-in-hv4188-013",
  "measurements": {
    "chest_circumference": 93.98,
    "waist_circumference": 81.915,
    "hip_circumference": 93.98
  }
}
```

Optional `chart_version` pins an immutable version; otherwise the latest for
that exact brand/apparel is selected. Measurements required by the chart must
be positive finite centimetres. The example is the published M midpoint, not
an estimate extracted from the sample photo.

For each active dimension:

`midpoint = (lower + upper)/2`

`deviation = abs(measurement - midpoint)/midpoint`

`error = sum(normalized_weight * deviation)`

Weights: shoulder .20, chest .25, waist .20, hip .20, thigh .10, inseam .05.
Active subsets are normalized to sum to one. No ease offsets or interval-distance
substitutions are used. A value inside an interval still has nonzero error away
from its midpoint. Full precision determines ranking; exact ties use published
`sort_order`, then label.

`recommended_size = argmin(error)`

`fit_confidence = 100/(1 + minimum_error)`

The last value is a **heuristic similarity score, not a calibrated probability
of fit**. Response fields also include full `size_rankings`, per-size
`chart_comparison`, `active_weights`, chart provenance and warnings. A closest
size is still returned when no size contains all measurements, with an explicit
out-of-range warning.

Default category dimensions:

| Categories | Active metrics |
|---|---|
| T-shirt, shirt, blouse, sweater, jacket, dress | Shoulder, chest, waist, hip |
| Trouser, jeans, shorts | Waist, hip, thigh, inseam |
| Skirt | Waist, hip |
| Jumpsuit | All six |

Official charts may declare a nonempty `active_metrics` subset of their category
when they publish fewer dimensions. Every size must define those ranges; the
response states omitted category dimensions. The four India charts publish
chest/bust, waist and hip only, giving weights .25/.65, .20/.65, .20/.65.
Finished-garment charts are rejected for body-size recommendations.

## Brands, charts and administration

| Endpoint | Use |
|---|---|
| `GET /api/v1/sizing/brands` | Five requested brands, with separate India men's/women's verification status and source links |
| `GET /api/v1/sizing/charts?market=IN&gender=women&brand_id=nike` | Chart summaries; all filters optional |
| `GET /api/v1/sizing/charts/{brand_id}/{apparel_id}?version=1` | Full bounds and provenance |
| `POST /api/v1/sizing/charts` | Insert a newer immutable version; `X-Admin-Token` required when `ADMIN_TOKEN` is set |

Chart payloads contain brand/apparel/category/version, gender, market, source URL,
checked date, original unit, body/garment measurement basis, notes, active metrics,
and `sizes:[{size_label,sort_order,bounds:{metric:{lower,upper}}}]`.
Bounds are always stored in cm. A version cannot change apparel category, gender
or market. Seed insertion is idempotent and never overwrites an existing version.

Current verified coverage is in [India brand sources](india-brand-sources.md).
The fictional six-metric fixture remains in
`data/brandCharts/anthropometry-demo-v1.json`, with `is_demo: true`; it is not
relabelled as a real brand.

## Verification and privacy

- `tests/test_anthropometry.py`: analytical geometry, strict visibility, arm/thigh
  ambiguity, repeated mask refinement, known weighted errors/confidence, chart
  conversion and filtering, immutable versions, API validation and MongoDB failures.
- Real CPU integration: repeated studio photo produces identical numbers;
  a waist-up crop is rejected. No new model was trained and no local GPU was used.
- `scripts/verify_measurement_api.py`: real local HTTP upload, returned PNG decode,
  repeatability, Nike midpoint recommendation and cropped-photo rejection.
- Live evidence: `experiments/anthropometry/live-api/report.json` and annotations.
  Measured cold/warm extraction was 2.6757/0.6725 seconds on this machine; these
  times apply only to measurement extraction, not virtual try-on generation.
- 506 CPU regression tests passed, 3 integration tests deselected. The separate
  37-test measurement suite includes its real CPU integration and passed.

This is a local development service. Annotation URLs and diagnostic artifacts
are not authenticated; photos and records persist until explicitly deleted.
Do not expose this server as a public multi-user service without access isolation
and a retention policy. Measurement inference stays on local CPU; only VTON
generation uses the user's authorized private Colab.

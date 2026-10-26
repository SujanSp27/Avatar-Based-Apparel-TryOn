# Torso outline validation — 26 October 2026

## Root cause and reproduction

The exact message originated in `backend/app/anthropometry/measurement_service.py`,
inside `estimate()`. The old implementation selected connected foreground spans
through torso anchors. It rejected the entire scan if every candidate crossed an
arm centerline, or exceeded 1.65 times shoulder width. Waist had only one candidate
at 50% of the shoulder-to-hip axis. A binary person mask includes clothing and arms;
touching regions therefore became a single span. A good skeleton did not establish
a usable body outline. Width alone could not distinguish loose clothing from body
shape. Missing elbow/wrist confidence was silently skipped by the overlap check.

There was no reproduced normalized-coordinate scaling bug: x and y already used
the decoded image width and height independently. The decoder applies EXIF and
colour handling before resizing to at most 1600 px. The coarse GrabCut pass works
at at most 800 px, which can lose narrow gaps. Probability dimensions and ranges
are now checked explicitly and mapped to the same image frame.

The existing deterministic connected-arm regression reproduces the old error.
The credited studio photograph succeeds before and after the fix: upper chest
sections intersect sleeves/arms; its first separate section is at 45%, and waist
at 50%. A waist-only bridge now recovers the observed section at 48%, without
substituting a hip width. Complete torso overlap is retained as unavailable
chest/waist, rather than measured through the arms.

The user's exact failing upload was not attached to this request. Tests use the
repository's supplied photographs and explicit geometric/mask fixtures; they do
not claim to have validated an unidentified photograph.

## Implemented behavior

- Keep the MediaPipe CPU checkpoint, OpenCV refinement, projection multipliers,
  height scaling and brand engine. No model training or dependency change.
- Validate RGB shape, matching binary mask, normalized probability range,
  finite landmarks and visibility. Key landmark visibility stays strictly >0.65.
  Framing, side view, bent/crossed leg, merged thigh, file-size and image-content
  checks remain enforced.
- Measure connected spans around shoulder/hip anchors perpendicular to the torso
  axis, not a rectangular bounding box. Check shoulders/elbows/wrists, including a
  forearm collinear with the section. Do not carve guessed anatomical boundaries.
- Check five chest levels and a narrow waist band (50%, 48%, 52%). A possible
  coarse-resolution arm bridge can trigger one deterministic image-guided retry
  at up to 1600 px, using the original probabilities. Accept only an improvement
  in usable dimensions; preserve the prior partial result otherwise.
- Return unknown chest/waist as `null`, preserve other valid estimates and the
  33-landmark annotation. Low-confidence/out-of-frame arm landmarks are explicitly
  uncertain, not interpreted as proof of no arm contamination.
- Retain a wide or asymmetric observed silhouette as a **review-required estimate**.
  The 1.65 width ratio and 0.35 side-imbalance check are geometric review heuristics,
  not calibrated garment/body classifiers. Neither guarantees close-fitting clothing.
- Expose `quality.status`, per-metric reason/message and `requires_manual_review`.
  These are qualitative evidence flags, not probabilities or tape accuracy scores.
- Keep image and height on retry. Clear stale values/skeleton when extraction
  starts, clear obsolete errors when the input changes, display warnings inline,
  and allow explicit per-dimension tape corrections.
- Pass the stored scan ID to sizing. The server validates ownership and refuses
  flagged/missing dimensions required by the selected chart until explicit tape
  overrides are supplied. Correcting one dimension does not approve all others.
  Saving a recommendation uses the same gate; raw manual input remains independent.
- Do not briefly display all six fields while a three-metric chart is loading.

## API compatibility

Successful complete scans keep the same numeric values and response keys. New
partial scans allow `measurements.chest_circumference` and
`measurements.waist_circumference` to be null. Complete manual/saved-profile
`Measurements` still requires six positive numbers. No database migration is needed
for existing complete records.

`POST /api/v1/sizing/recommend` and `/api/v1/profile/sizes` accept an owned
`measurement_id` and optional `measurement_overrides` keyed by metric in centimetres.
Overrides are validated positive finite numbers, only valid with a stored scan.
The stored photo estimates are not overwritten. Unreviewed required dimensions
produce HTTP 422 with code `measurement_review_required`.

`POST /api/v1/measurements/extract-and-recommend` retains a successful partial scan
with HTTP 200, `recommendation: null` and an actionable `recommendation_error`.
It never fabricates a size or loses a usable annotation just because sizing cannot
proceed. Fully valid extraction still returns the computed recommendation.

## Logging and privacy

The `vastraview.measurements` logger emits JSON events for preprocessing sizes and
scale, pose detection/key visibility, mask size and uncertain-prior fraction,
candidate left/right pixel spans, arm intersection decisions, error codes and
elapsed processing time. No image bytes, source filenames, tokens, user identities,
input hashes or complete landmark arrays are logged. Diagnostic artifacts stay in
the existing private output storage. Refinement uses a lock around its fixed-seed
OpenCV initialization, including the optional retry.

## Files changed

Backend: `anthropometry/measurement_service.py`, `pose_adapter.py`, `schemas.py`,
`router.py`, new `measurement_quality.py` and `diagnostics.py`; `accounts/router.py`
uses the quality gate when saving scan-based sizes.

Frontend: `MeasurementProvider.tsx`, `MeasurementWorkspace.tsx`, `MeasurementGrid.tsx`,
`SizeEngineView.tsx`, `sizingService.ts`, `types/studio.ts`. Existing design and VTON
integration are preserved.

Tests: `test_anthropometry.py`, new `test_torso_measurements.py` and
`frontend/e2e/measurement-quality.spec.ts`. Documentation: this report, API contract,
measurement guide and implementation status.

## Verification

- `.venv/Scripts/python.exe -m pytest tests -q --disable-warnings --maxfail=5`:
  **678 passed**, including real local CPU checkpoint tests; 112.34 seconds.
- `python -m ruff check backend/app tests`: passed. `python -m pip check`: passed.
- `npm run build`: passed (TypeScript build and Vite, 183 modules).
  Prettier check of all changed frontend files and the new browser test: passed.
- `npx playwright test measurement-quality.spec.ts studio.spec.ts vastraview.spec.ts
  fashion-platform.spec.ts online-tryon.spec.ts job-recovery.spec.ts results-comparison.spec.ts
  --max-failures=3`: **31 passed**, no skipped or flaky cases; 114.49 seconds.
  Tests include the real CPU extraction-to-size flow, byte-identical canvas after
  retry, partial/uncertain UI, per-metric review, stale-value clearing, authentication,
  upload rejection, source charts, profile, responsive comparison, failure/recovery
  and retained VTON rendering. Controlled responses test uncertainty UI; they are
  not claims of real-image inference accuracy.
- `VASTRAVIEW_LIVE=1 VASTRAVIEW_LIVE_CASE=fashion-upgrade npx playwright test
  private-tryon-live.spec.ts --reporter=list`: passed. Resumed the already-completed
  real Colab job; checked owner-only access, anonymous denial, history, reload,
  both comparison modes, download bytes, mobile layout and retained display during
  a simulated availability outage. No new inference was submitted, and this is not
  evidence of a fresh GPU generation in this measurement-fix session. The separate
  `frontend/test-results-live/.last-run.json` records `passed`.
- The running frontend on port 5173 and API `/api/health` on port 8000 returned 200.
- The original studio image was processed through the actual checkpoint and its
  annotation inspected: selected torso sections stop at visible clothing edges and
  exclude the arms. The known projection limitations remain. Cached original/resized
  pose observations at widths 400, 600, 800 and 1000 retain the prior valid estimates.
- Actual fresh resized-image checks verify torso logic at 400 and 800 px. A particular
  resampling of the 400 px sample still has a merged-thigh failure in the independent
  full-body check; that threshold was not bypassed. Female repository examples with
  low heel visibility or merged thighs still fail their specific checks. The
  oversized standing photo still fails the 20 MP limit. Multiple-person/invalid
  examples remain rejected.

Local evidence: `.runtime/torso-diagnostics/`, `.runtime/torso-full-pytest.log`,
`experiments/torso-validation/partial-scan-mobile.png`, and
`experiments/browser-test-report.json`. Private test outputs are not published.

## Limits

A single clothed image cannot reveal concealed body contours. Some images now
return a useful partial scan, not six claimed accurate measurements. Shoulder-to-hip
section selection, face-to-ankle height scaling, hip-joint circumference proxy and
hip-midpoint inseam remain heuristic and uncalibrated. Close-fitting clothing, a
contrasting background and tape measurements are still recommended. No VTON model,
checkpoint, inference parameter, authentication policy or size-error formula changed.

Coordinate and probability handling follows the official
[MediaPipe Pose Landmarker documentation](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python).

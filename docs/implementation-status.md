# Current implementation status - 26 October 2026

## Torso validation and measurement uncertainty

| Requirement | Status | Evidence |
| --- | --- | --- |
| Separate detected pose from usable torso silhouette | IMPLEMENTED | Candidate spans and arm visibility/overlap checks; per-metric quality instead of blanket torso rejection |
| Preserve partial results without invented contours | IMPLEMENTED | Nullable chest/waist, original landmarks and other valid dimensions; wide/asymmetric silhouettes require tape review |
| Block uncertain estimates from sizing and saved recommendations | IMPLEMENTED | Owned scan references, explicit per-metric overrides, server quality gate and 422 regression tests |
| Retain image/height on retry; clear stale results | IMPLEMENTED | Three new browser regressions, mobile warning/accessibility checks; existing design preserved |
| Logging, validation and regression verification | IMPLEMENTED | 678 Python tests and 31 browser tests passed; structured numeric diagnostics without photos/tokens |
| Accurate anatomy beneath loose/overlapping clothing | PARTIALLY IMPLEMENTED | No hidden contour inferred; manual correction remains necessary; existing thigh/framing constraints unchanged |

See [torso-validation-fix.md](torso-validation-fix.md) for root cause, schema changes,
file list, exact checks and known limitations.

## Fashion discovery and sizing upgrade

This section supersedes older catalog counts and guest try-on behavior below.
See [fashion-platform-upgrade.md](fashion-platform-upgrade.md) for sources, exact
coverage, assets, audit findings and deployment limitations.

| Phase | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| Discovery | Editorial hero, supplied logo and responsive design | IMPLEMENTED | HomePage, local responsive Pexels photograph, desktop/mobile browser evidence |
| Catalog | Distinct real data, filters, pagination and saved favorites | IMPLEMENTED | 51 new references / 57 total locally; manifest, MongoDB APIs, asset checksum and filtering tests |
| Catalog scope | High-resolution commercial inventory in every category | PARTIALLY IMPLEMENTED | 46 community reference photos plus 5 editorial outfits; no stock claims, unsupported layered outfits browse-only |
| Sizing | Explicit source, market, basis, units and published-metric matching | IMPLEMENTED | 23 official scopes across Nike, Puma, Manyavar, Adidas, Levi's and H&M; source/mapping/point/weight tests |
| Sizing coverage | All target Indian brands/categories verified | PARTIALLY IMPLEMENTED | Missing charts remain explicit; UK/US/Kosovo charts are not relabeled India |
| Security | Account required before new inference and recovery POST | IMPLEMENTED | Protected route plus server dependency; invalid/expired/revoked tokens and ownership tests |
| Regression | Backend and real CPU measurement checks | IMPLEMENTED | 652 regression + 3 checkpoint tests passed on 26 October |
| Browser | Catalog, charts, authentication, responsive comparison and recovery | IMPLEMENTED | Final combined 28-case browser suite passed; 57 image URLs checked, desktop/mobile/accessibility verified |
| Live inference | Fresh authenticated private Colab result, authorization and download | IMPLEMENTED | Job 51c51dad-e812-4545-83ea-3c0d8986c6f1; one live browser test passed; retained result survives reload/outage, identical download bytes |
| Fidelity and speed | Exact reference construction and consistent sub-30-second output | PARTIALLY IMPLEMENTED | New sage-polo test 34.837 s total / 22.696 s generation; face/background unchanged in checked regions; placket/texture softened and relaxed sleeves/hem |
| Deployment | Catalog manifest and restorable local images | IMPLEMENTED | API Dockerfile COPY, source/checksum manifest and repeatable downloader; container runtime still pending |

## VastraView upgrade — current application

The existing React/FastAPI application now uses the supplied VastraView artwork,
with a MongoDB catalog and private account/result APIs. PostgreSQL chart/run data
and the existing FASHN VTON integration remain. This section supersedes older
public-result links below: unowned historical results are preserved on disk but
are no longer publicly accessible. New results require their original account or
guest browser session. No historical files were assigned to an arbitrary user.

| Stage | Requirement | Status | Evidence |
|---|---|---|---|
| 1 Audit | Inspect existing stack, preserve model and database data | IMPLEMENTED | `docs/vastraview-upgrade.md`; existing checkpoint/profile unchanged; versioned SQL index migration |
| 2 Branding | Supplied logo, favicon, responsive navigation, authentication, homepage, footer and empty/loading states | IMPLEMENTED | `BrandLogo.tsx`, `frontend/public/brand/`, `scripts/prepare_branding.py`; original logo copied unchanged |
| 2 Catalog | Stable database IDs, sourced products, search/filters/sort/pagination/details, upload handoff | IMPLEMENTED | `backend/app/catalog.py`, `features/catalog/`; real browser filtering and selected-image handoff; equal-height cards at 375/768/1440 px |
| 2 Inventory | All requested brands and apparel types available as real products | PARTIALLY IMPLEMENTED | 23-brand directory and 24-category taxonomy; six sourced research references. No fabricated stock/charts. Commercial rights are not established; research assets are excluded in production |
| 3 Accounts | Signup/login/logout, Argon2id, short JWT, HttpOnly cookies, rotation/reuse detection | IMPLEMENTED | `accounts/router.py`, `security.py`; unit/integration and real multi-tab browser session tests |
| 3 Email | Verification and password reset with single-use expiring tokens | PARTIALLY IMPLEMENTED | SMTP adapters and test delivery verified; actual SMTP host/sender credentials remain unconfigured. Production startup requires verification and SMTP |
| 3 Authorization | Protected routes/APIs, fail-closed admin writes, origin checks and throttling | IMPLEMENTED | Cross-owner/anonymous/CSRF/admin-denial tests; old public static trees replaced with authorized image endpoints |
| 4 Personalization | Units, consented scans, saved sizes, favorites, private history and session management | IMPLEMENTED | `AccountPrivacy.tsx`, `ProfilePage.tsx`; real browser save/read/unit/favorite/session tests; genuine Colab result appears in owner history |
| 4 Erasure | Password-confirmed account deletion and owned local data cleanup | IMPLEMENTED | `accounts/lifecycle.py`, `private_data.py`, serialized mutations; deletion browser regression. Colab files/backups require separate retention |
| 5 Uploads | File-content, byte/dimension limits, safe paths, bounded processing | IMPLEMENTED | Existing decoder retained; private measurement/try-on ownership, job capacity, JSON/body limits and request throttles tested |
| 5 Result privacy | Owner checks for status, annotations, original/generated images and downloads | IMPLEMENTED | `private_data.py`; cross-user fixture tests and fresh real GPU result rejected for an unauthenticated client; no-store responses |
| 5 Recovery | Preserve existing notebook, verify replacement GPU and restore actual model | IMPLEMENTED | Existing notebook recovered to T4 `0720e93c273d` after user-approved Google prompt; real readiness and one fresh inference verified |
| 5 Inference | Genuine garment-conditioned result, comparisons, refresh, outage survival and download | IMPLEMENTED | Real job `2198597c-ce71-460e-9995-1a2a2b385488`; `experiments/vastraview/private-tryon/`; byte-equal download and no duplicate inference POST |
| 5 Quality | Exact fabric construction and universal sub-30-second results | PARTIALLY IMPLEMENTED | Sage-polo run 32.102 s, GPU 23.162 s. Full-resolution review: correct color/collar/sleeves, no obvious old-shirt/blue artifacts; softened buttons/texture and minor collar softness remain |
| 6 Tests | Backend suite, real CPU pose, browser accessibility, build, lint and dependency checks | IMPLEMENTED | 647 backend tests plus 3 checkpoint integration tests passed; final combined browser run: 21 passed, including the genuine private GPU result; strict TypeScript/Vite, Ruff, Prettier and pip check passed |
| 6 Deployment | HTTPS proxy, Dockerfiles, production validation, migration, retention/backup documentation | PARTIALLY IMPLEMENTED | `compose.production.yml`, `deploy/`, `.env.production.example`, deployment guide; Compose configuration validated. Docker daemon unavailable; container/HTTPS/real-domain verification pending |
| 6 Security review | Dependencies and release assessment | PARTIALLY IMPLEMENTED | npm audit: zero findings. API dependencies patched; protobuf 4.25.9 advisory CVE-2026-0994 remains constrained by MediaPipe 0.10.21. See deployment release gates; not certified production-ready |

The fresh 800×1200 result was manually compared with its actual input and sage
polo reference. Pixel checks found zero changed pixels in the checked face/hair,
lower legs/shoes and outer-background regions. The detailed review is
`experiments/vastraview/private-tryon/visual-review.json`; this is a controlled
single-case check, not proof of universal fit or garment accuracy.

App: `http://127.0.0.1:5173`; API docs: `http://127.0.0.1:8000/docs`.
See [deployment and remaining release gates](vastraview-deployment.md).

## Compact results layout — 25 October

The existing comparison now uses an 1100 px maximum width and 540 px desktop
image-height limit, reduced to 500 px at tablet widths. The card shrinks with
the source aspect ratio and selected panel count rather than creating empty
side gutters. Full-body photographs remain uncropped and identically scaled.
The title and mode controls sit above the bordered image/action card; Inspect
details stays left, with Share and Download right. The FormFit theme, navigation,
result URLs and inference pipeline are retained.

Evidence: `experiments/compact-comparison/`. Browser checks cover 3840, 1920,
1440, 768 and 375 px widths, equal painted image bounds, centering, no center gap,
compact slider dimensions, pointer/keyboard input, footer alignment, retries,
result switching, download, sharing and the saved real Colab result. This layout
verification does not submit another inference request.
Final verification passed: 12 browser tests, strict TypeScript/Vite production
build and formatting checks. Final desktop/slider/mobile screenshots inspected.

## Blouse fidelity continuation

The actual person/blouse pair was recovered and tested on the existing private
Colab T4. Mapping `blouse` to `tops` and uploaded-image hashes were correct. White
sleeves/waist fabric originated in model output, before compositing. Doubling the
steps and enabling official person masking did not remove it; neutralizing the
confidently segmented dark flat-lay reference's pale background did.

| Requirement | Status | Evidence |
|---|---|---|
| Exact input/category audit and reproducible comparisons | IMPLEMENTED | `experiments/blouse-fidelity/README.md`, actual conditioning tensors/images and hashes |
| Remove invented white layer for the reported blouse | IMPLEMENTED | Fresh real API job `4bb32769-3289-428e-bb76-f413dc308df7`; `app-correction10/tryon-2d.png`, `fidelity-metrics.json`; dark reference fabric retained exactly during background preparation |
| Preserve head, bag and hands; handle cropped hem and shorter sleeves | PARTIALLY IMPLEMENTED | Exact parsed protected pixels; bounded reference-aware midriff exception and background transition. Small hair/arm seams remain. Newly exposed midriff is generated, not measured anatomy |
| Exact sleeve construction, smocking and eyelet texture | PARTIALLY IMPLEMENTED | Native-resolution comparison completed in 33.987 s and improved flutter sleeves/eyelet detail; smocking and hem proportions remain approximate. `native-correction10/visual-review.json` records the full-resolution review |
| Existing API and comparison UI remain functional | IMPLEMENTED | 637 CPU backend tests passed, 3 integration tests excluded; genuine blouse job passed live browser refresh/comparison/download/outage checks; UI unchanged |
| Universal sub-30-second output | PARTIALLY IMPLEMENTED | Final native-profile app pipeline 31.319 s including 22.466 s GPU; Colab queues and network vary |

Real saved result:
`http://127.0.0.1:5173/tryon?job=4bb32769-3289-428e-bb76-f413dc308df7`.
This records completed inference, not a certification of exact garment detail.

The final worker now retains native resolution and parses preservation labels
at the output canvas size, classifying after logit interpolation instead of
nearest-neighbor upscaling of class IDs. A parser-only test on the saved native
output visibly smoothed hair/arm edges without another try-on generation.
The existing Colab recovered automatically after its old tunnel expired. The
replacement T4 was verified and the real worker reached Ready; no duplicate
recovery cell was replayed. Final combined app job
`f5b254bc-0660-44e0-a0c1-e2689c67cd28` completed in 31.319 seconds. Its actual
800x1200 result, masks, conditioning, reports and browser screenshots are safely
local in `experiments/blouse-fidelity/app-native-fullparse10/`. Full-resolution
review confirms dark short flutter sleeves, no invented white layer and smoother
preservation boundaries. Smocking and hem proportions remain approximate.

Latest checks after the final source/profile edits: 137 focused CPU tests,
Ruff, and the strict TypeScript/Vite production build passed. The earlier full
637-test run covers the backend. The latest live browser check now covers the
final combined native/full-canvas app job, including a simulated health-network
interruption without losing the completed result.

## Comparison alignment correction — 24 October

| Requirement | Status | Evidence |
|---|---|---|
| Equal image dimensions with no unintended center strip | IMPLEMENTED | Removed one-sided sizing border; shared source aspect ratio and absolute contained photos; painted image bounds measured within 0.05 CSS px |
| Preserve both full images and support resized outputs | IMPLEMENTED | No crop/stretch; matching aspect ratios at different resolutions supported; incompatible framing gets a clear error |
| Side-by-side and draggable comparison remain functional | IMPLEMENTED | Consolidated comparison CSS; absolute 1 px slider divider; pointer/keyboard and divider-position checks |
| Male/female turquoise-shorts, desktop and mobile verification | IMPLEMENTED | Actual retained images tested at 1920/1440/768/375 px; screenshots inspected in `experiments/comparison-alignment/` |
| Latest real image, retry, download/share and outage handling | IMPLEMENTED | 12 browser tests passed, including fresh Colab job, image switching, failed/stalled downloads, saved-result retention and no duplicate generation; strict TypeScript/Vite build passed |

This targeted layout change retains the FormFit theme, routes, API behavior and
model pipeline. The retained shorts fixtures verify rendering rather than
certifying the photographic quality of those older generations.

## Results redesign and fresh navy T-shirt

The current comparison is the existing React try-on page, with equal image
panels, photo-derived aspect ratio, compact mode controls, responsive footer,
image-loading/error states and an expanded real garment catalog. The older
“unchanged comparison” notes below describe the previous recovery milestone.

The fresh FASHN VTON 1.5 job `5a257fc7-c093-45ce-81c7-f3919c003a6f` used the
original studio person and an actual navy tee garment reference on the private
Colab T4. It completed in **20.754 seconds** end-to-end, **16.401 seconds** GPU.
Open the actual saved job at
`http://127.0.0.1:5173/tryon?job=5a257fc7-c093-45ce-81c7-f3919c003a6f`.
There is no hardcoded AFTER image or replacement-person photograph in the UI.

| Requirement | Status | Evidence |
|---|---|---|
| Balanced responsive comparison and compact Slider/Side-by-side controls | IMPLEMENTED | `SplitCompareViewer.tsx`, `comparison.css`; completed results fill the content width, Change outfit reveals controls without discarding the image; browser checks equal widths/heights at 1920, 1440, 768 and 375 px; pointer and keyboard slider; screenshots in `experiments/results-redesign/` |
| Latest successful render, stale selection invalidation, bounded image loading and retry | IMPLEMENTED | `useTryOnJob.ts`, `TryOnStudio.tsx`, `results-comparison.spec.ts`; open tabs follow the latest selected job with GET only; input changes clear persisted job; failed/processing results cannot be downloaded; image failure/timeout/mismatched dimensions tested |
| Actual navy T-shirt AFTER with original person retained | IMPLEMENTED | `experiments/results-redesign/navy-tee/live-result.json`, `after.png`, `visual-review.json`; full-resolution visual inspection, unchanged face/hair check region, lower body and outer background |
| Details, zoom, sharing and correct image download | IMPLEMENTED | Browser tests exercise modal/focus, size-page link, share fallback and downloaded-byte SHA256 equality |
| Additional real garments and safe category/photo-type selection | IMPLEMENTED | `/api/garments`, `GarmentPicker.tsx`, `download_samples.py`; navy tee, sage polo, blouse, two dresses, skirt; API lists available allowlisted files only; dress selection tested |
| Photographic fine-texture fidelity and universal sub-30-second latency | PARTIALLY IMPLEMENTED | The accepted navy render has softened fabric/stitching and a slightly longer hem. Catalog selection is not a quality certification for every garment. Cold Colab recovery and queues remain variable |

Current targeted backend verification: **45 tests passed**, including catalog,
job handling and availability; Ruff and strict TypeScript/Vite production build
passed. The final full browser run had **22 passed, one skipped** (fresh GPU
upload intentionally disabled), including the live Colab connection, genuine
navy result, simulated outage, responsive comparison, download, share, real
account lifecycle, body extraction and brand sizing. The first broad run found
stopped local databases; starting their existing data directories restored the
APIs and all tests passed. Browser evidence is in `experiments/browser-test-report.json`; the normal
suite never starts fresh GPU inference. The navy inference above was submitted
once with a persisted idempotency key and inspected independently.

## Availability recovery and sage-polo input

The permanent runtime-pin pause is removed. Replacement GPUs require two spaced
identity checks, followed by an in-cell pin check before restoring the worker.
Readiness now requires the authenticated loaded model, expires when stale, and
invalidates on URL/token rotation. The frontend offers an honest outage state
and a coalesced Retry action; it keeps uploads and completed comparison results.
New submissions validate the images and model. Interrupted result streams retry
the same event with bounded backoff and never repeat generation POST.

The real sage-polo job `f773078b-48fc-4283-863b-b26ccf7bd0d4` completed on the
private Colab T4 in **24.591 seconds** end-to-end (16.045 seconds GPU generation).
Its original and AFTER images were recovered and inspected at 800 x 1200.
Open the retained result at
`http://127.0.0.1:5173/tryon?job=f773078b-48fc-4283-863b-b26ccf7bd0d4`.
This uses the real saved API job; no generation or replacement photograph is
silently substituted. The link becomes the browser's retained job on opening.

| Requirement | Status | Evidence |
|---|---|---|
| Automatic replacement-runtime verification and safe setup recovery | IMPLEMENTED | `scripts/auto_connect_colab.py`, `scripts/colab_worker_recovery.py`; runtime `9045f828fb7e` recovered and generated the polo; after app restart the replacement `73dd851fe103` was verified, restored and became Ready automatically; `experiments/recovery-polo/recovery-verification.json` |
| Real model readiness, stale-cache expiry, Retry and request timeouts | IMPLEMENTED | `tests/test_tryon_availability.py`, `frontend/e2e/online-tryon.spec.ts`; hanging health calls, credential rotation, failed health and retry tested |
| Retain jobs/results and reconnect without duplicate inference | IMPLEMENTED | `tests/test_jobs.py`, `tests/test_online_vton.py`, `frontend/e2e/job-recovery.spec.ts`; same-event GET retry and completed result reload verified |
| Sage polo conditioning input and unchanged comparison slider | IMPLEMENTED | `data/raw/sage-polo.jpg`, reproducible `scripts/download_samples.py`, `/api/samples/polo`; sample rail uses the real product photograph; `SplitCompareViewer.tsx` and slider CSS unchanged |
| Genuine sage-polo AFTER image, identity preservation and unchanged comparison viewer | IMPLEMENTED | `experiments/recovery-polo/after.png`, `live-result.json`, `visual-review.json`; collar/sleeves/hem visually inspected, no obvious beige/black fragments or blue artifacts; original face region, lower body and outer background are pixel-identical; actual-job viewer refresh/slider/zoom/download checked |
| Premium fabric/button fidelity and universal availability or latency | PARTIALLY IMPLEMENTED | Fine pique texture and button details are softened; relaxed fit and slight edge softness remain. This one run met 30 seconds; shared GPU cold setup, quotas, network delays and arbitrary garments cannot be guaranteed |

Verification: **597 Python tests passed** (three integration tests deselected),
and **14 browser tests passed**, with one fresh-upload opt-in skipped to avoid
duplicating inference. The 22 October browser run included the actual retained
polo, live replacement-GPU connection, simulated health interruption, refresh,
slider, zoom, download, mobile layout, accounts, measurements and sizing.
The complete browser report is in `experiments/browser-test-report.json`. Strict TypeScript,
Vite production build, Ruff and `pip check` passed. Evidence:
`experiments/recovery-polo-python.xml`, `experiments/browser-test-report.json`.
Setup now retains Colab's torch/torchvision/NumPy versions and disables parallel
Xet buffering; this mitigation is not proof of the crash's cause. Runtime
replacement attempts have a bounded cooldown. See [tryon-recovery.md](tryon-recovery.md).

The final blocker was the worker's Gradio JSON component returning Python
`root={...}` text under the installed Colab stack. Explicit JSON-text outputs and
strict client decoding fixed both readiness and result transport. An exception
after notebook progress now reports `recovery_failed`, not stale `loading`.

On 23 October the app was started again after the saved tunnel expired. It
automatically verified replacement runtime `0e95c38a5032`, restored the worker
and returned to Ready. The retained original and AFTER bytes were unchanged;
no new inference was submitted. Current-startup evidence is in
`experiments/recovery-polo/restart-smoke-20261023.json`.

The following frontend report is earlier evidence; its old `runtime_changed`
pause and “no connection button” wording are superseded by the recovery above.

## FormFit Studio frontend completion

The React 19 studio is running at `http://127.0.0.1:5173`, backed by real account,
measurement and sizing APIs. The API now exposes **48 OpenAPI operations**. New
implementation details and deployment limitations are in
[frontend-studio.md](frontend-studio.md). The earlier backend and VTON records
below are retained as dated evidence.

| Requirement | Status | Evidence |
|---|---|---|
| React 19, strict TypeScript, lazy routes, shared responsive design system | IMPLEMENTED | `frontend/src/App.tsx`, `components/`, `features/`, `services/`, `styles/`; production build passed, 172 modules |
| Signup/login, password strength, confirmation, terms, guest mode, remember-me, protected profile | IMPLEMENTED | Real MongoDB account flow in `e2e/studio.spec.ts`; Argon2id passwords, JWT session API |
| In-memory access tokens, HttpOnly refresh rotation, expiry/replay detection, logout, CSRF/rate limits | IMPLEMENTED | `tests/test_accounts.py`; browser reload, simultaneous tabs and forced-401 retry passed; no browser token storage |
| Forgot/reset-password screens and single-use reset implementation | PARTIALLY IMPLEMENTED | Reset expiry/replay and SMTP adapter tested; actual email delivery is BLOCKED because SMTP host/sender credentials are not configured |
| Editable profile height, authenticated scan history/thumbnails, saved brand sizes and deletion | IMPLEMENTED | Real HTTP profile/save/read/reuse/delete flow and account-isolation tests; desktop/mobile screenshots |
| Upload validation/resizing, camera capture with alignment guide, cm/feet/inches conversion | IMPLEMENTED | Client module and browser validation/camera-denial checks; live physical-camera capture not manually verified |
| Actual 33-point canvas, six metric cards, manual corrections and measurement-to-size flow | IMPLEMENTED | Real CPU MediaPipe request returned 33 points; canvas toggle, corrected values, saved profile and Nike M fixture verified |
| Brand/category/collection selectors, ranges, exact deviation engine and fit gauge | IMPLEMENTED | Live MongoDB charts and API; midpoint/error/confidence verified; unavailable guides disable recommendation |
| Try-on inputs, filtered sample rail, automatic readiness, status polling and retained-job recovery | IMPLEMENTED | Six connection/recovery/viewer browser checks; no connection button or local GPU inference |
| Split slider, side-by-side, zoom, download and platform sharing adapter | IMPLEMENTED | Retained genuine CatVTON result loads both images; slider/zoom/PNG download passed. Sharing depends on browser support |
| Responsive layout and keyboard/accessibility behavior | IMPLEMENTED | Widths 375, 768, 1440 and 3840 checked; no overflow; Axe WCAG 2 A/AA and 2.1 AA checks passed on tested screens; native-dialog Escape/focus and tab arrows tested |
| Universal browser/device compatibility and enterprise deployment certification | PARTIALLY IMPLEMENTED | Chromium verified; broader device/manual assistive-technology audits, SSO/MFA/email verification and deployment security remain outside completed verification |
| Fresh Colab inference during this frontend verification | BLOCKED | Health reports `runtime_changed`; existing worker tunnel is expired. No runtime reset, new notebook, public upload or new inference was submitted |

Final verification: **542 Python tests passed**, three integration tests deselected;
**10 browser tests passed**, three live-Colab opt-in tests skipped; strict TypeScript,
Vite production build, Ruff and `pip check` passed. npm audit reports **zero known
vulnerabilities** after compatible router/Vite/Playwright security updates. The
main JavaScript bundle is 263.26 kB (83.90 kB gzip); routes and validation code are
separate chunks. Evidence is in `experiments/frontend-studio/`, including the
browser report, Python XML, npm audit and visually inspected screenshots.

The old guest annotation and try-on asset URLs remain public on the local server.
Private profile thumbnails enforce account ownership. Public deployment still
requires protecting legacy assets and configuring HTTPS/cookies/secrets/SMTP;
the interface is not evidence that those deployment tasks are complete.

## Earlier pipeline and backend evidence

The latest user direction is **2D only, existing Colab only, no local GPU**, with
automatic connection at app startup and no manual connection control in the UI.
The user reconfirmed that photos must remain in their Colab only; public GPU demo
uploads are not authorized. The latest speed target is at most 30 seconds for a fresh,
visually acceptable result. No local GPU is used for inference.
Previous scope and verification records are preserved in
[the archive](archive/implementation-status-before-online-only.md); the original
root specification file is no longer present. The phase labels below are historical
references, and the active requirements are in [requirements.md](requirements.md).

The subsequent body-measurement request adds **CPU MediaPipe and MongoDB**.
This is separate from the removed 3D workflow and Colab image generation.
The new backend is documented in [measurements and sizing](measurements-and-sizing.md).

Backend completion on 21 October adds a single-upload extraction/recommendation
endpoint, saved-measurement retrieval/history/deletion, sizing by saved record ID,
brand create/read/update, chart filtering/pagination/version history, category
metadata, SQL run history and capability-specific health/readiness. There are
33 documented operations in OpenAPI. Request IDs, retry headers, sanitized
database errors and unreadable-job recovery are covered by regression tests.
The full CPU regression suite passed **530 tests**, with no failures or errors
(`experiments/backend-completion/unit-tests.xml`). The live acceptance script
passed **29 HTTP checks** against real MediaPipe, MongoDB and PostgreSQL. Its
combined extraction/recommendation took **4.021 seconds** on the first run;
this measures CPU estimation and sizing, not VTON. The test record and its files
were deleted through the API after verifying retrieval and reference-based sizing.
See [the complete API contract](api.md) and `experiments/backend-completion/`.
After local services stopped during the session, PostgreSQL, MongoDB and the API
were restored without changing Colab. All 29 live checks passed again; combined
CPU extraction/sizing took 6.4253s (`restarted-api/report.json`). The final four
browser regressions passed in 12.7s, and TypeScript/Vite built successfully in
1.69s. Ruff and `pip check` passed. These browser checks do not submit GPU inference.

21 October continuation: the local app and both databases were restarted after
their processes stopped. Fresh real HTTP extraction passed at 6.4897s cold and
2.0882s warm, with identical measurements, retrievable PNG annotations, MongoDB
persistence, and cropped-image rejection. Nike's known M midpoint returned zero
error. Evidence: `experiments/anthropometry/live-api-20261021/report.json`.
These are measurement latencies, not try-on generation timings. The previous
Colab worker URL returned 404; no new VTON inference was submitted in this check.
The frontend's annotation proxy now returns the actual PNG through port 5173.
The pinned Rollup tree-shaking pass stalled for several minutes on this machine;
disabling that pass restored a successful 1.05s Vite production bundle (TypeScript
also passed). Minification remains enabled. JavaScript is 215.53 kB / 67.78 kB
gzip, compared with the previous 212.18 / 67.07 kB. This is a build-time workaround,
not an image-generation optimization; reconsider it after a verified bundler fix.
All four `online-tryon.spec.ts` browser checks passed on 21 October, including the
real legacy size API, with results in `experiments/anthropometry/browser-20261021.json`.
Final health check reports the local API healthy and Colab `runtime_changed`;
measurement/sizing work independently. No runtime reset or new inference was used.

| New requirement | Status | Evidence |
|---|---|---|
| MediaPipe 33 landmarks, strict visibility, reported-height scale and six estimates | IMPLEMENTED | `backend/app/anthropometry/`; real CPU image extraction and deterministic repeat test |
| Anatomically accurate single-image measurements | PARTIALLY IMPLEMENTED | Requested projection formulas run, but hip joint spacing and head/crotch proxies are biased; no tape-measure ground truth or calibrated uncertainty |
| Exact weighted midpoint error, rankings and 100/(1+E) score | IMPLEMENTED | Hand-calculated .1/.29 fixtures and live Nike midpoint → M, error 0 |
| MongoDB chart versions and measurement records | IMPLEMENTED | Running MongoDB 8.2.2, unique version index, 10 seeded charts, HTTP extraction persistence |
| Saved-record APIs and single-upload extraction/recommendation | IMPLEMENTED | Real HTTP create/read/list/annotation/recommend/delete; measurement warnings retained; `scripts/verify_backend_api.py` |
| Brand administration, chart discovery/version history and run history | IMPLEMENTED | Auth, immutable provenance, category filters, latest-version aggregation and pagination tests |
| Independent health, readiness and failure handling | IMPLEMENTED | `backend/app/health.py`; SQL/Mongo/model/Colab failure tests; sanitized errors; corrupted jobs retained without replay |
| Both men's and women's Nike/Puma India guides | IMPLEMENTED | Four product-specific body guides, official URLs and source values in `data/brandCharts/india-*.json` |
| U.S. Polo Assn., Adidas, Allen Solly India body charts | BLOCKED | USPA tables describe garment dimensions; Adidas India access denied; Allen Solly interactive guide access denied. Catalog states these limitations |
| New routes, validation, annotation downloads and errors | IMPLEMENTED | `experiments/anthropometry/live-api/report.json`; real HTTP cold 2.6757s/warm 0.6725s, cropped image rejected |
| Regression checks | IMPLEMENTED | 530 CPU tests; 29 real HTTP checks repeated after service restoration; four browser checks; TypeScript/Vite build, Ruff and pip check passed |

| Phase | Requirement | Status | Evidence |
|------|------|------|------|
| 0 | Explicit image/category/privacy scope | IMPLEMENTED | `docs/requirements.md`; image validation and category enums |
| 1 | FastAPI, React, PostgreSQL, MongoDB, local assets | IMPLEMENTED | Running app and API/database tests; local base dependencies include CPU MediaPipe and exclude CUDA/3D runtimes |
| 1 / 12 | Automatic Colab connection and status-only UI | IMPLEMENTED | `backend/app/colab_connection.py`, `scripts/auto_connect_colab.py`; startup monitor; automatic browser recovery tests |
| 1 / 12 | Restore missing worker on existing GPU | IMPLEMENTED | `scripts/colab_worker_recovery.py`; runtime identity checked before writes, owned-process checks, pinned setup, bounded retries, no inference replay. Validated `config/online-worker.json` seeds missing runtime configuration only; recovery unit tests |
| 2 | Person/garment decoding, pose/parsing in online model | IMPLEMENTED | `online_vton.py`, FASHN official preprocessing; actual T4 inference report |
| 3 / 4 | 3D human reconstruction and mesh measurements | BLOCKED | Removed from active scope at user's request; new 2D pose estimates are separate and do not reconstruct a body mesh |
| 5 / 6 | Versioned charts and explainable size engine | IMPLEMENTED | Existing database/API/engine retained; independent measured-input size API/browser test |
| 7 / 8 / 9 / 10 | 3D garments, fitting, cloth simulation and GLB scene | BLOCKED | Removed from active scope at user's request; replaced by photo generation |
| 7 / 8 / 9 | Real pretrained image-based garment generation | PARTIALLY IMPLEMENTED | FASHN VTON 1.5 FP16/504 x 756 result has a natural collar, aligned sleeves and continuous hem without old-shirt fragments in the controlled graphic-shirt example. Small graphic details, striped collar corners and other-person contours remain imperfect |
| 11 | Uploads, eleven categories, photo type, original comparison and PNG output | IMPLEMENTED | `frontend/src/App.tsx`, `PhotoViewer.tsx`; seven browser tests passed |
| 12 | Colab-only transport, jobs, failures, reconnect without local fallback | IMPLEMENTED | Transport/DB/job/reconnection tests; same worker URL retained throughout an in-flight event. JPEG95 conditioning plus lossless changed-pixel output preserves original pixels outside the edit; response type/format/dimension checks and stage diagnostics |
| 13 / 14 | Evaluation records and broader quality/generalization | PARTIALLY IMPLEMENTED | Saved striped-shirt, second-person graphic-shirt and dress benchmarks, images and visual reviews in `docs/online-performance.md`. Fast results retain unacceptable artifacts; broad category quality remains unvalidated |
| 15 | Acceptable fresh generation within 30 seconds | PARTIALLY IMPLEMENTED | Current FP16/504 x 756/10-step graphic-shirt benchmark 23.080s; fresh browser upload-to-visible-image 25.449s (pipeline 22.668s). This controlled example passed prototype visual review. Striped, other-person and skirt/dress limitations remain; no universal guarantee |
| 16 | Complete production-quality application | PARTIALLY IMPLEMENTED | Web/API/size engine and online generation exist; garment quality, cloud environment isolation and latency need further work |

Saved benchmark evidence is detailed in [online-performance.md](online-performance.md).
The current default is FP16, 504 x 756, 10 steps, guidance 1.5, no crop and JPEG95
conditioning. The existing Colab T4 produced a fresh result through the real app:
**25.449 seconds from Generate to a loaded image**, including 22.668 seconds in
the pipeline and 16.943 seconds in GPU generation. The opt-in browser test passed
with exactly one inference POST; original/result comparison also worked.
Evidence and visual limitations are saved under
`experiments/live-balanced-upload-20261020/`. The graphic-shirt example meets
controlled prototype acceptance; small printed details are lost, and all-category
production acceptance remains open.

The 20 October work corrected ProPhoto-to-sRGB conversion before metadata removal,
then added a bounded semantic blend where a new neckline or hem reveals material
under the original outfit. Protected face/hair/hands and pixels outside the edit
mask remain unchanged. A new coverage gate rejects results inventing exposed skin
across more than 20% of the replaced garment area. These fixes are implemented;
their existence does not establish photographic accuracy for every category.

Fresh tests on the existing Colab T4: striped shirt 23.230s, graphic shirt 22.252s,
tiered skirt 23.318s, dress 24.340s. Each has actual output, raw model image, parsing
maps, timings and a separate visual review. The skirt fixture had been mislabeled
as trousers; it validates neither trouser fitting nor category accuracy. The dress
result predates the new coverage rejection. A larger shoulder projection was
tested at 26.443s, rejected for a rough contour, and reverted. Native crop tests
also remain unaccepted, including a white shirt band in the striped result.

The final full regression run passed **470 CPU-only tests**, with 2 integration
tests deselected, recorded in `experiments/online-balanced-full-tests.xml`.
Ruff passed for the changed Python files. The live browser upload test passed and
its raw output and masks were recovered from Colab to the evidence directory.

456 CPU-only tests passed before the coverage gate. The earlier focused run passed
104 tests covering compositing, colour handling, recovery, API/database and jobs
after reverting the rejected contour experiment. Another 115 focused tests passed
for the promoted preset, including parsing integer inference steps from environment
variables without breaking API startup. Four browser checks, a fresh live upload
test and the production frontend build passed on 20 October. These local checks are separate
from visual model acceptance; no model trained and no local GPU was used.

Earlier records:
The 54.583-second native FP16 image was reviewed on 18 October: face recognizable,
hands retained, sleeves aligned, no visible old-shirt fragments and a continuous
hem. This is one controlled example, not production-quality acceptance across
categories. Reduced-resolution 10/15-step images and their cropped variants retain
unnatural sleeve transitions and hem artifacts; none qualifies as an accepted fast
preset. Native guidance-1.0 / 10 steps reached 21.274s; adding the official clothing
mask reached 19.627s. Both failed visual review. The revised second-person
hem/shoulder compositor completed in 31.078s (13.181s generation), with a continuous
hem but remaining shoulder-edge artifacts. Raw outputs and masks are saved;
those earlier faster settings were not promoted. The later 504 x 756 preset above
is now the research default after its controlled real-shirt review.

Recorded connection and local verification (historical checks, not a claim that
an ephemeral Colab session is currently live):

- 447 CPU-only Python tests passed, with zero failures or errors in
  `experiments/online-profile-transport-tests.xml`. Coverage includes strict worker
  profile validation, seeding absent configuration while preserving existing files,
  lossless transport, malformed response rejection and sampler safeguards. These
  local tests do not imply that the latest worker changes are live in Colab.
- `experiments/lossless-transport.json` records CPU serialization checks: the person
  payload was 25.23% smaller and the reviewed result payload was 23.81% smaller,
  with identical decoded pixels. These are byte savings, not measured reductions in
  end-to-end inference time. Worker and transport stage timings are now recorded to
  measure the remaining costs on a subsequent live run.
- 351 CPU-only Python tests passed, 2 integration tests deselected, after runtime
  pinning and hem changes. `experiments/online-recovery-hem-tests.xml` records the
  run. Hem tests cover waistband overlap, disconnected label patches, excessive
  extension, sloped hems, and exact protection of unrelated pixels. These tests
  validate mask behavior, not realistic photographic fitting.
- 51 focused Python tests passed, including expired-worker recovery, bounded
  retries, existing-task preservation, connection rotation, real size API and jobs.
- Seven Playwright tests passed: automatic preparation/readiness without clicking,
  API loss/recovery without reload, no avatar controls, independent sizing, and
  retained-job recovery. Network-state tests use controlled responses and do not
  establish model image quality.
- On 16 October, one additional live Playwright test passed against the restored Colab T4:
  the app reached Ready without connection controls; sample inputs enabled Generate.
  `experiments/automatic-colab-ready.png` was visually inspected and
  `experiments/automatic-colab-connection.json` records live readiness and no local GPU.
- Ruff and TypeScript checks pass. The production frontend build passed (59
  modules, 212.18 kB JavaScript / 67.07 kB gzip).
- Live startup reopened the saved notebook automatically. It had a T4 but its
  temporary worker files had expired; pinned setup completed, the worker loaded,
  and the new tunnel was adopted automatically. No extra generation was submitted
  for this connection verification. A saved URL never substitutes for a live probe.

The 17 October connection reached several different runtime hostnames. Recovery
now refuses to mutate a runtime different from the verified pin. The original
292.3-second result and the subsequent native/reduced-resolution FP16 images and
timings are safely local under `experiments/online-runs/`.
The current 504 x 756 FP16/guidance-1.5 settings are persisted in
`config/online-worker.json` for restoring missing runtime configuration. Existing
settings and running jobs are preserved. Native guidance-1.0 experiments have
completed: the second-person graphic-shirt result took 18.644 seconds but failed
hem/shoulder review. The dress result passed the corrected lower-body validation
and took 35.592 seconds, but generated exposed limbs and background were unnatural.
Neither result establishes an accepted fast preset. Lossless changed-pixel
transport is now verified on live output without changing decoded image pixels.
`scripts/online_worker.py` also saves source and generated semantic label maps
alongside raw output, allowing subsequent visual review to separate model,
parsing and compositing errors.

Quality-95 input encoding is implemented and covered by focused
tests. It reduces uploaded bytes while preserving original pixels outside the
generated edit patch. It was used in the fresh 20 October results above and is now
the default research setting. Lossless input remains configurable. This change
does not establish exact garment-detail fidelity.

The 19 October continuation recovered the raw output and masks for the hem
failure, completed a fresh 31.078-second boundary test, and passed 447 CPU tests
plus 51 focused tests after adding failed-run artifact records. Four browser
checks passed for automatic readiness/recovery, the photo-only interface and the
real size API. At that point the smaller-upload benchmark had not run because the
connected notebook switched runtimes during worker restoration. It subsequently
completed on 20 October as recorded above. The runtime pin
blocked changes to the other machine. The user confirmed only one tab was open;
two read-only checks then verified the same empty replacement T4 before its pin
was updated. Restoration resumed on that existing notebook in one bounded cell.
No new notebook or inference was submitted as a workaround. A changed hostname
alone does not prove that duplicate tabs caused the problem.

Colab can require Google authentication/consent or GPU selection. Those browser
actions cannot be automated by the notebook helper. Automatic restoration requires
the already-authorized notebook, network access and an allocated GPU. The current
Colab profile inherits system packages; unrelated inherited-package conflicts
are recorded by pip and a fully isolated, clean profile remains unfinished.

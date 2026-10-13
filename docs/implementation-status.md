# Implementation status

Specification read in full before implementation and reread on 13 October 2026 while
replacing the 2D pipeline. The original specification is unchanged. Status refers to exercised code,
not intended future work. The functioning end-to-end path is a **controlled approximate
template prototype**, with pretrained pose/segmentation; it does not complete learned
SMPL/SMPL-X reconstruction or validate single-photo anthropometry.

The user subsequently authorized **2D when 3D is unavailable**, then rejected the visible
artifacts of the geometric overlay and requested a proper pretrained model. The application
now routes 2D through CatVTON plus FASHN parsing; the old overlay is debug-only. Real CUDA
inference now completes, but all three reviewed CatVTON configurations lost or changed the uploaded stripes and
were rejected. Visual acceptance remains unmet. This work does not
complete learned 3D reconstruction or measurement validation. The original 3D and 9 October
overlay verification records below are historical evidence, followed by a separate current
neural-pipeline table. Historical counts are not rerun results for the new model.

| Phase | Requirement | Status | Evidence |
|------|------|------|------|
| 0 | Freeze image scope, supported categories/brands, measurements, views and metrics | IMPLEMENTED | `docs/requirements.md`; API enums and validation; visible UI scope notices |
| 1 | Repository structure and modular backend/frontend/ML/data/assets/tests/docs | IMPLEMENTED | `backend/app`, `frontend/src`, `ml/*`, `data/*`, `assets/*`, `scripts`, `tests`, `docs`, `notebooks` |
| 1 | FastAPI, React, Three.js, React Three Fiber, OpenCV, MediaPipe, Trimesh, PyTorch environment | IMPLEMENTED | Installed local `.venv` and npm dependencies; production build, type check, pip check, live API/browser tests; CPU torch tensor test |
| 1 | Reproducibility, environment configuration, locks and startup | IMPLEMENTED | `requirements.lock.txt`, torch CPU/CUDA profiles, `frontend/package-lock.json`, `.env.example`, setup/start/stop scripts, Alembic |
| 1 | PostgreSQL and local generated-asset storage | IMPLEMENTED | Local PostgreSQL 17.11 at loopback:5433; live API reports `postgresql`; UUID asset directories and verified downloads |
| 1 | Open3D/Blender/SMPL-X research tooling | PARTIALLY IMPLEMENTED | Open3D 0.19 and SMPL-X 0.1.28 installed/imported; independent Open3D manifold, watertight and self-intersection checks passed (`experiments/open3d-report.json`). Licensed SMPL model absent; Blender not used by deterministic baseline |
| 2 | Person decode, validation, background removal, pretrained segmentation/pose, crop/normalize | IMPLEMENTED | `ml/preprocessing/images.py`, actual MediaPipe checkpoint; person mask/crop/normalized/keypoint artifacts |
| 2 | Garment validation, controlled segmentation, mask/crop/normalize | IMPLEMENTED | Plain-background/alpha segmentation; striped garment regression test and saved garment artifacts |
| 2 | Reject/flag partial body, multiple people, occlusion, low resolution, extreme poses, unclear garment | IMPLEMENTED | Negative real-image tests and actionable 422 codes; heuristics are restricted to documented scope, not a universal detector |
| 2 | Repeatability and saved intermediates | IMPLEMENTED | Repeated actual inference produces identical masks/keypoints in tests; per-run artifacts retained |
| 3 | Select and investigate one pretrained body-reconstruction target | IMPLEMENTED | HMR2 official setup/demo APIs inspected; `docs/model-adapter.md` explains selection and compatibility limits |
| 3 | Learned HMR2/SMPL(-X) body reconstruction | BLOCKED | Required licensed neutral SMPL model absent; upstream inference environment and anatomical mapping not validated. `HMR2Reconstructor` is an availability gate, not implemented inference; strict learned 3D returns 503. Auto may invoke neural 2D for supported failures, which does not enable HMR2 |
| 3 | Best working pretrained component + honest usable body-mesh fallback | PARTIALLY IMPLEMENTED | MediaPipe 3D pose/person segmentation plus image-conditioned elliptical/capsule mannequin; `smplCompatible=false`; no hidden-depth/identity recovery |
| 3 | Body/shape/pose/camera parameters, validity gate, OBJ/PLY/GLB and visualization | IMPLEMENTED | `ml/human/template.py`, `bodyParameters.json`, `validate_mesh`, `validate_reconstruction.py`, actual front/side/back previews and browser body view |
| 3 | 5–10+ sample inference and reconstruction-quality inspection | PARTIALLY IMPLEMENTED | Eleven downloaded photographs exercised; supported studio photo generates valid mesh, ten unsuitable images rejected. Geometry inspected. This is not diverse-body accuracy validation |
| 3 | Compare recovered shape with calibrated reference silhouette/scan | PARTIALLY IMPLEMENTED | Segmentation and shape export available; silhouette-IoU utility exists; no validated learned reconstruction or calibrated reference scans |
| 4 | Independent mesh-to-measurements service: all eight dimensions | IMPLEMENTED | `ml/measurement/service.py`; closed cross-section perimeters, landmark lengths, shoulder section; analytical ellipse and height-scaling tests |
| 4 | Estimates, uncertainty and structured JSON | IMPLEMENTED | Centimetres, explicit heuristic uncertainty, `confidence=null`, body-depth caveats; UI/API measurements |
| 4 | Calibration against actual tape measurements | BLOCKED | No consented tape-measurement ground truth provided. Numerical correctness is tested; human measurement accuracy is not established |
| 5 | Normalized brands/charts, range validation, immutable versions | IMPLEMENTED | Three related SQL tables plus run records; schema migration; unique/range constraints; chart CRUD/version tests |
| 5 | Brand/chart read/create/version APIs and initial data | IMPLEMENTED | `/api/brands`, `/charts`, `/chart-versions`; two explicitly fictional demo brands × four categories × six sizes |
| 6 | Independent deterministic weighted sizing, tight/regular/loose ease | IMPLEMENTED | `ml/sizing/engine.py`, `/api/sizing/recommend`; category weights, deterministic tie breaks and preference/brand tests |
| 6 | Ranked scores, fit explanations, out-of-range flags; no probability claims | IMPLEMENTED | Per-measurement explanations, candidate ranking, version/source provenance; scores can exceed 1 |
| 7 | T-shirt, shirt, dress and trouser templates using silhouette/body/size/dimensions | IMPLEMENTED | `ml/garment/templates.py`; joined loft surfaces, optional cm overrides; all four branches generated and inspected |
| 7 | Photo texture mapping and usable garment mesh export | IMPLEMENTED | Crop-derived nearest-fabric atlas and UVs, embedded GLB textures, reload tests, striped texture visible in browser |
| 7 | Arbitrary garment reconstruction / hidden back details | PARTIALLY IMPLEMENTED | Deliberately deferred research scope; front fabric repeats on back, no learned shape or true seams/material inference |
| 8 | Anatomical alignment, scale, body collision detection, offset and surface projection | IMPLEMENTED | Canonical body landmarks, chart/body dimensions, signed-distance queries and projection; final four-category fixture has zero penetrating sampled vertices/face centres |
| 8 | General collision-free fitting for arbitrary inputs, cloth self-collision | PARTIALLY IMPLEMENTED | Sampling is not continuous collision detection; self-collision/material stretch not modelled; failures above tolerance are rejected |
| 9 | Deterministic baseline deformation | IMPLEMENTED | Pinned-boundary Laplacian relaxation, small vertical settling, repeated body-surface projection; diagnostics record iterations/method |
| 9 | Physically calibrated cloth or Blender simulation | PARTIALLY IMPLEMENTED | Not required for the selected template baseline; not implemented or claimed. No material physics, seams or arbitrary-pose drape |
| 10 | Combine body, fitted garment and texture into loadable dressed GLB | IMPLEMENTED | Two named scene geometries; export/reload gate; live asset downloads and actual Three.js loading |
| 11 | Upload/select/generate React workflow and result display | IMPLEMENTED | Person/garment uploads, brand/category/fit/height controls, sample inputs, errors, measurements, size and explanations |
| 11 | Orbit, zoom, front/side/back, 360, GLB loading and responsive viewer | IMPLEMENTED | Two passing Playwright tests; body/garment/dressed tabs; real desktop/mobile screenshots in `experiments` |
| 12 | POST /api/tryon orchestration and real result/asset URLs | IMPLEMENTED | Live PostgreSQL-backed multipart uploads through all stages; all four categories returned 200 and reloadable GLBs |
| 12 | Error handling, validity gates, capacity control, local failure storage | IMPLEMENTED | Typed errors, 422/404/409/413/429/503, bounded pipeline slot, run/failure metadata and local traceback logging |
| 13 | MAE/MAPE/RMSE, IoU, MPJPE/P-MPJPE, exact/adjacent/top-2 size metrics | IMPLEMENTED | `ml/evaluation/metrics.py`, analytical metric tests, optional ground-truth evaluation input |
| 13 | Operational success/failure/latency/memory/GPU reporting | IMPLEMENTED | Actual run timings/RSS and hardware report; `scripts/evaluate.py`; CPU inference disclosed |
| 13 | Ground-truth reconstruction/measurement/size accuracy and scored visual quality | BLOCKED | No labelled scans, tape measurements, preferred sizes or human-review ratings; reports leave these null rather than fabricate scores |
| 14 | Split leakage checks and failure/regression dataset structure | IMPLEMENTED | Person/garment identity overlap rejection, manifest/review templates, negative-photo fixtures and saved failures |
| 14 | Diverse disjoint train/validation/test datasets and generalization study | PARTIALLY IMPLEMENTED | Templates/checks exist; no actual diverse labelled split. No training or unsupported generalization claim |
| 15 | Optimize only after working baseline | IMPLEMENTED | Cached pretrained model, normalized image sizes, bounded proximity batches and serialized memory-intensive jobs; viewer renders on demand with static contact shadows and continuous rendering only during 360 rotation; focused imports reduce transformed modules from 2,205 to 381 |
| 15 | CUDA inference on this installation | IMPLEMENTED | torch 2.5.1+cu121 and torchvision 0.20.1+cu121 installed; real CUDA tensor check, checkpoint loading and two complete 50-step CatVTON runs on GTX 1650. GPU inference works, but visual quality is rejected; `experiments/vton-hardware-report.json`, `experiments/catvton-initial-report.json`, `experiments/catvton-guidance5-report.json`. MediaPipe remains CPU |
| 16 | Complete local research application, tested through browser | PARTIALLY IMPLEMENTED | Functional end-to-end approximate avatar, measurements, sizing, templates, fitting and interactive GLB. Research-grade body reconstruction and empirical accuracy remain incomplete |

## Historical 3D verification record (9 October 2026)

- Python regression suite: **24 passed**; upstream deprecation warnings only.
- Ruff and TypeScript checks: passed. Python dependency consistency: passed.
- Frontend production build: passed; final rerun is recorded in `experiments/final-verification.json`.
  `experiments/build-report.json` records the successful command, 381 transformed modules,
  artifact checksums and the remaining large-bundle warning.
- Real browser tests: **2 passed**, covering uploads, generated size/results, GLB loads, view
  changes, zoom/rotation, layer selection, demo inputs and mobile overflow.
- Reconstruction: `experiments/reconstruction-report.json` and exported inspectable meshes.
- Independent Open3D inspection: 18,306 vertices / 36,608 triangles; watertight, orientable,
  edge/vertex manifold and no self-intersections. SMPL-X package import does not establish
  SMPL-X inference or model-asset availability.
- Garment/fitting: `experiments/garment-report.json`; all categories passed sampled collision
  checks after correcting overlapping sleeve and torso surfaces.
- Live API: `experiments/api-smoke-report.json`; main API, PostgreSQL, binary GLB download
  and trimesh scene reload verified. Synthetic garment across category branches is a software
  test, not garment-classification or cloth-realism evidence.

The initial browser test encountered 429 while a separate category suite occupied the single
pipeline slot. A later rerun timed out during concurrent dependency installation and mesh
validation, although the API request completed. A subsequent isolated run exposed excessive
continuous rendering in the software WebGL renderer; idle rendering and shadow recomputation
were removed, and the stale test process was stopped before revalidation. Generation suites
must run sequentially on this machine. The CUDA installation exhausted available disk at the
time; those historical checks used the explicitly documented CPU dependency profile.
The CUDA runtime was successfully installed during the later 2D correction below.
The final browser rerun passed both tests in 92 seconds, after the viewer fix and focused
dependency imports. The final desktop screenshot was inspected and shows the real striped
garment texture, generated measurements and size recommendation.

## Cropped-photo feedback correction

An uploaded upper-body portrait was correctly rejected but initially received the generic
`occluded_body` explanation. Framing checks now run before joint-visibility checks, so
extrapolated legs outside the image produce `partial_body` with explicit head-to-toe guidance.
The person upload control keeps this requirement visible after a file is selected. Validation
thresholds remain unchanged. Seven preprocessing tests passed, including a regression for this
case; replaying the original upload through the live API returned the corrected 422 response
(`experiments/cropped-photo-regression.json`). The frontend production build, TypeScript/Ruff
checks and existing mobile/sample-photo browser test also passed after this correction.

## Historical geometric 2D fallback (superseded)

The following records describe the earlier overlay implementation, which has been removed
from the application call path. They prove its historical software behavior, not acceptable
garment fitting or verification of the current CatVTON implementation.

| Phase | Requirement | Status | Evidence |
|------|------|------|------|
| 0 / 2 | Explicit 2D scope for cropped photos with sufficient visible anatomy | IMPLEMENTED | `docs/requirements.md`, `ml/tryon2d/service.py`; actual cropped portrait accepted, invisible lower body rejected; `experiments/2d-api-report.json` |
| 11 / 12 | Auto fallback, explicit 3D/2D mode and real original/preview PNG results | IMPLEMENTED | Real uploads through PostgreSQL-backed API passed in Auto and 2D; PNGs downloaded and verified; original/try-on comparison passed in Playwright; physical outputs remain null |
| 13 / 14 | Regression for the user's reported cropped-photo failure | IMPLEMENTED | `frontend/e2e/2d-fallback.spec.ts` passed with the actual retained uploads, PNG downloads, Original/Try-on controls and mobile layout. Private photos stay in ignored storage |

That 2D output was a landmark-guided garment warp on the source photo, not a trained VTON
model. It did not solve real-world sizing or photorealistic cloth. Its broader category
support and the validation cases below do not define the new model's scope.

Validation completed on 9 October 2026:

- **48 Python tests passed**, with three upstream deprecation warnings:
  `experiments/2d-pytest-report.xml`. Tests cover strict/auto/2D routing, preservation of
  the visible head/background, deterministic output, garment-colour regressions, invalid
  anatomy, failure persistence, and evaluation of mixed 2D/3D runs.
- **Four live API cases passed** using the user's actual retained portrait and garment:
  Auto and explicit 2D returned real PNG assets; strict 3D rejected the cropped portrait;
  trousers rejected invisible lower-body anatomy. `experiments/2d-api-report.json`.
- **Three Playwright browser tests passed**, including the reported portrait, existing
  3D upload/measurement/size/GLB flow, interactive view controls and mobile layouts.
  `experiments/browser-test-report.json`; private preview screenshots are in ignored
  `experiments/runs/browser-2d.png` and `browser-2d-mobile.png` and were visually inspected.
- Ruff and TypeScript passed. Production build passed: 382 modules, 539 seconds on this
  machine, with the existing large-JavaScript-chunk warning. Asset checksums and command
  evidence: `experiments/2d-build-report.json`.
- Actual mixed-run evaluation completed without interpreting 2D previews as mesh or
  measurement results: `experiments/2d-evaluation-report.json`. This development-run
  report includes intentional invalid-input tests and is not an accuracy benchmark.

Main changes: `ml/tryon2d/service.py`, `ml/preprocessing/images.py`,
`backend/app/photo_tryon.py`, pipeline/API/schema routing, `frontend/src/PhotoViewer.tsx`,
frontend mode/result handling, evaluation and regression scripts/tests. No new model was
trained and no external inference service was introduced.

## Current pretrained 2D correction (12 October 2026)

| Phase | Requirement | Status | Evidence |
|------|------|------|------|
| 0 / 2 | Audit actual cause of bad shirt output and remove geometric overlay from application | IMPLEMENTED | Old `ml/tryon2d/service.py` used `warpPerspective`; current `backend/app/photo_tryon.py` imports `ml/vton/service.py`. No neural failure calls the overlay |
| 1 | Preserve compatible versions and configure real pretrained assets | IMPLEMENTED | Installed torch 2.5.1+cu121/torchvision 0.20.1+cu121, pinned neural dependencies, `requirements-vton-cuda.lock.txt`, source revisions, verified SHA-256 manifests and successful local CatVTON loading; original CPU lock retained |
| 2 | Real human parsing and inspectable original-clothing/preservation masks | IMPLEMENTED | FASHN checkpoint loaded on CPU; repeated studio-person/garment labels identical and visually inspected, `experiments/runs/parser-validation/verification.json`; `ml/vton/parsing.py` saves semantic masks |
| 2 | Preserve light garment details and give diffusion mask boundary context | IMPLEMENTED | Background-noise-aware threshold retains cream stripes; regression verifies all 33,007 cream pixels. `ml/vton/masking.py` adds constrained eight-pixel semantic dilation before latent downsampling; model receives and saves the exact segmented garment condition |
| 2 | Separate neck and left/right limbs; universally accurate occlusion boundaries | PARTIALLY IMPLEMENTED | Parser has 18 classes with arms/hands but no separate neck/left/right labels; neck transition uses torso adjacency. Occlusion and boundary quality remain conditional on parsing |
| 7 / 8 / 9 | Neural garment conditioning and synthesis replacing flat paste | PARTIALLY IMPLEMENTED | Real uploaded inputs passed through pretrained CatVTON in 493.331 seconds, then 315.413 seconds with guidance 5/new masks/float32 convolution arithmetic. Both generated plain shirts and lost all uploaded stripes; generation is real but fidelity fails |
| 8 / 9 | Proper neckline, both sleeves and hem with no beige-shirt remnants | PARTIALLY IMPLEMENTED | Alpha 1 replaces all predicted original clothing. Bounded semantic context removed the reviewed white shoulder/collar seams on saved output (`experiments/runs/composite-refinement/refined-seams-review.png`). Missing garment details remain unresolved; no reviewed output meets the full criterion |
| 8 / 11 | Preserve original identity, limbs, lower clothing and background | PARTIALLY IMPLEMENTED | Actual initial CatVTON diagnostics report 1,403,378 preserved pixels, zero changes outside the edit mask and exact predicted identity preservation. Semantic errors and boundary seams remain limitations |
| 6 | Keep brand size recommendation independent and avoid fabricated 2D sizing | IMPLEMENTED | Existing engine/API retained; real supplied dimensions produce S and XXL with chart provenance in `experiments/vton-independent-size-report.json`; 2D physical measurements and recommended size remain null |
| 11 / 12 | Neural result contract, supported categories and honest failures | PARTIALLY IMPLEMENTED | `renderingMethod=pretrained-vton`, checkpoint provenance/masks, 2D T-shirt/shirt scope, typed model/category errors and health readiness are implemented; live CatVTON API/browser verification pending |
| 13 / 14 | Actual input replay, output inspection, multiple people/garments | PARTIALLY IMPLEMENTED | Exact reported inputs replayed through parser, DM-VTON and three CatVTON configurations; reviewed outputs rejected. Reports retain hashes/provenance/timing/review. Multiple-person/garment CatVTON validation remains pending |
| 12 / 13 | Reject catastrophic stripe loss without publishing a fake success | IMPLEMENTED | `ml/vton/quality.py`, `tests/test_vton_fidelity_failure.py`, `experiments/vton-fidelity-guard-report.json`: narrow horizontal-stripe check rejects both plain-shirt regressions; retains native diagnostics and returns 422 without final PNG. It is not a general visual-quality certificate |
| 15 | Memory-aware pretrained inference on available GPU | IMPLEMENTED | Two complete actual runs on GTX 1650 4 GB/8 GB RAM with sequential CFG, VAE slicing and CPU safety checker. Verified GTX 16 FP16 cuDNN NaNs are handled by model-scoped float32 Conv2d arithmetic retaining FP16 weights; 50-step denoising reduced from approximately 397 to 227 seconds in these runs |
| 16 | User's natural-looking uploaded-shirt acceptance criterion | PARTIALLY IMPLEMENTED | Actual generated outputs were inspected and rejected for missing or invented patterns. No production-quality or accepted-fitting claim |
| Experimental | Official mixed attention checkpoint | PARTIALLY IMPLEMENTED | Verified `mix-48k-1024` weights; reduced-resolution run completed in 326.298 seconds and was rejected (`experiments/catvton-mix512-report.json`). Native-resolution local run was interrupted; no final image. Efficient attention supports its larger tensor without changing checkpoint weights |
| Follow-up | Train or fine-tune if feasible | BLOCKED | No paired person/garment/target corpus or labelled disjoint validation set. Local 4 GB GPU/8 GB RAM has no established feasible training configuration. Pretrained inference is the active path; no new weights were trained |

Current model details, exact source revisions, license terms, setup and limitations are in
[`docs/vton-model.md`](vton-model.md). Verification recorded through 12 October:

- 11 October full suite: **200 Python tests passed in 40.54 seconds**, with three upstream
  warnings; `experiments/vton-pytest-report.xml`. On 12 October, **83 focused attention,
  conditioning and service-failure tests passed in 31.29 seconds**; counts are not combined.
  The experimental conditioning module is not enabled or inference-validated.
- Ruff and `pip check` passed. Pinned diffusers 0.29.2 and accelerate 0.31.0 are installed.
- Actual CUDA inference: `experiments/catvton-initial-report.json` records 493.331 seconds,
  while `experiments/catvton-guidance5-report.json` records 315.413 seconds. Both generated
  images but were visually rejected because the uploaded stripes were absent; the second
  review also identified shoulder outlines and a collar seam.
- Numeric diagnostics: `experiments/vton-numerics.json` identifies the first failing FP16
  convolution; `experiments/vton-convolution-report.json` records non-finite cuDNN FP16
  output and finite native-FP16/float32-cuDNN alternatives. `ml/vton/precision.py` applies
  the float32 arithmetic workaround without changing resident weights or checkpoint aliases.
- Frontend production build and TypeScript passed on 10 October: 382 modules, 302-second
  Vite build, remaining large-chunk warning. `experiments/vton-ui-build-report.json` records
  artifact/source hashes. Frontend source has not changed since. Two non-inference browser
  checks passed for category scope and unavailable-model errors; neither executed generation.
- Rejected real DM-VTON output is recorded in `experiments/dmvton-rejected-report.json`,
  including the pink neckline, unnatural sleeves and blurred stripes.
- Live CatVTON API/browser generation and accepted visual fitting remain pending.
  `scripts/validate_vton_api.py` covers the original regression, semantic preservation,
  independent sizing and unsupported categories. Updated `scripts/validate_2d_api.py`
  targets the neural contract and uses the new `experiments/pretrained-2d-api-report.json`
  report path, keeping historical overlay evidence separate.

The 48 Python tests and three browser tests in the earlier section belong to the superseded
9 October implementation. Historical passes and current unit/API results are separate from
the required visual acceptance. No training or fine-tuning has been performed.

## Colab continuation (13 October 2026)

| Phase | Requirement | Status | Evidence |
|------|------|------|------|
| 1 / 15 | Move native-resolution inference off the local 4 GB GPU | PARTIALLY IMPLEMENTED | `scripts/colab_runtime.py`, `requirements-colab.txt`, isolated Python setup, verified model downloads; Colab Tesla T4 with 15,360 MiB verified on 12 October in `experiments/colab-hardware-report.json`. The isolated setup cell completed, but no cloud model-load/inference result was obtained. A later reconnection opened a different empty scratch notebook whose probe had no GPU; the earlier report is not current-runtime evidence |
| 1 / 14 | Reproducible notebook with explicit source/data scope | IMPLEMENTED | `notebooks/Virtual_TryOn_GPU.ipynb`, `scripts/build_colab_notebook.py`, `experiments/colab-notebook-report.json`; 38 files, five explicit fixtures, checksums, no credential/database/upload-directory bundle; actual source extraction ran in Colab |
| 1 / 12 | Browser connection and notebook automation | IMPLEMENTED | Isolated pinned official Google Colab MCP server; `scripts/colab_bridge.py`, `scripts/colab_control.py`, `scripts/colab_notebook_control.py`; actual cells inserted/executed. Google account consent and GPU-runtime selection remain browser actions |
| 1 / 12 | Continue setup and evaluation without another chat turn between stages | IMPLEMENTED | `scripts/colab_notebook_control.py run-all` executed setup, four sequential case attempts and ZIP export. The first attempts failed before model inference; their actual reports were downloaded and collected. Image inspection is now separate to respect the bridge message limit. Optional Drive authorization is excluded; `--new-session` preserves prior cell mappings |
| 13 | Local regression verification after cloud integration | IMPLEMENTED | 273 Python tests passed in 50.94 seconds, three upstream warnings (`experiments/colab-pytest-report.xml`); Ruff passed. Both existing real-browser 3D tests passed in 176 seconds (`experiments/browser-test-report.json`), including size, measurements and GLB controls |
| 16 | Cloud result satisfies the uploaded-shirt acceptance criterion | PARTIALLY IMPLEMENTED | Earlier runtime provisioning is verified; the current runtime must be probed again. No cloud image inference or visual review has completed. All three reviewed local CatVTON configurations remain rejected for missing or invented stripes, and the native-resolution local run produced no final image before interruption. No accepted-output or training claim |

The 12 October setup completion covered isolated environment installation and model
downloads; it is not evidence of loading those weights or running inference on the T4.
Reconnecting on 13 October must establish the active notebook and GPU before work can
continue. Once connected, the agent handles source transfer, installation, inference and
artifact retrieval. No normal development setup is delegated to the user. Google account
consent and the Colab runtime selector remain browser actions when required.

Fine-tuning has not started. The bundled examples are unpaired regression inputs, and
there is no licensed paired training corpus or disjoint labelled validation set. The next
technical milestone remains an actual native-resolution pretrained result and visual
inspection of garment fidelity, neckline, sleeves, hem and identity preservation.

The first complete Colab runner attempt on 13 October used Python 3.12.14,
torch 2.5.1+cu121 and a Tesla T4 (14.56 GiB reported by PyTorch). All four cases
stopped at MediaPipe import because Colab's inherited `MPLBACKEND` pointed to
`matplotlib_inline`, which is absent from the isolated environment. The runner
now explicitly uses the headless `Agg` backend. The downloaded failure archive is
`experiments/colab-tryon-results-20261013.zip`; extracted reports are under
`experiments/runs/colab-initial-environment-failure`. These failures are not model
quality results. The corrected rerun is pending completion.

The updated cloud setup, combined-cell guard and result-archive tests passed:
**39 tests in 2.91 seconds**, with two upstream warnings
(`experiments/colab-correction-pytest-report.xml`); Ruff passed. The collector
verifies paths and available artifact checksums before extracting results and
does not mark generated candidates visually accepted.

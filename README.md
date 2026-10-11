# Form / Fit — 3D avatar virtual try-on

A working local research prototype built from
`3D_Avatar_Virtual_TryOn_Phase_Wise_Implementation_Plan.md`.

Upload a full-body person photo and flat-lay garment; select a brand, category and fit;
generate a textured dressed GLB and an explainable size recommendation. The React/Three.js
viewer supports front, side, back, orbit, zoom, 360 rotation and separate body/garment views.

**The 2D path now uses pretrained CatVTON with FASHN human parsing.** The previous
landmark-guided garment paste produced the reported sleeve, collar and old-shirt artifacts;
it is no longer called by the application. The UI defaults to 2D for T-shirts and shirts.
The API's `auto` mode first tries 3D, then calls the same neural 2D service for supported
3D failures. A missing checkpoint or failed inference returns an error, never a pasted
garment. The viewer compares the original and generated PNG and supports download.
**CatVTON now completes real CUDA inference, but both reviewed outputs failed visual acceptance:**
they generated plain shirts and lost the uploaded cream stripes. The requested
garment fidelity is not yet achieved. Further model/preprocessing experiments remain under
review; an HTTP success is not proof of natural fitting. See the
[model audit and verification state](docs/vton-model.md).

2D image generation is independent of the existing size engine. It does not infer physical
measurements or invent a size; the separate sizing API accepts actual measurements, and
the 3D path continues to use its explicitly approximate mesh measurements.

**The working body is an approximate parametric mannequin inferred from pretrained MediaPipe
pose/segmentation and silhouette widths. It is not a learned SMPL/SMPL-X reconstruction.**
Measurements are unvalidated estimates. Demo brands are fictional, and the sample garment is
a synthetic test image. HMR2/SMPL remains blocked by the missing licensed body asset and an
unvalidated upstream environment. Nothing in the API pretends that adapter has run.

## Run locally

This workspace has an installed `.venv`, frontend dependencies, downloaded pose model, sample
images and a local PostgreSQL 17.11 instance. The app uses loopback only.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

- Studio: http://127.0.0.1:5173
- API / OpenAPI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health
- Stop app and project database: `powershell -ExecutionPolicy Bypass -File scripts/stop.ps1`

For a clean Windows checkout (Python 3.12 and Node 22), `scripts/setup.ps1` provisions pinned
dependencies, model/sample downloads, portable PostgreSQL and schema migrations. It writes only
project data and normal package caches. It uses CPU PyTorch by default. The optional
`-Torch cuda` profile installs torch 2.5.1/cu121; allow ample free disk space for its 2.45 GB wheel
and extracted runtime. The original 3D validation used torch 2.5.1+cpu. The pretrained 2D
integration now runs torch **2.5.1+cu121** and torchvision **0.20.1+cu121** on the detected
GTX 1650 (4 GB VRAM). CUDA tensor checks and a complete 50-step CatVTON run passed; the run
took 493.331 seconds including loading and parsing. A second run with improved masks,
guidance 5 and the precision workaround completed in 315.413 seconds; both failed the
garment-pattern review, and the second also showed shoulder outlines and a collar seam.
MediaPipe and human parsing run on CPU. The current GTX 16 workaround uses float32 Conv2d
arithmetic with resident FP16 weights because this runtime's cuDNN FP16 convolution produced
NaNs; its focused tests and an actual complete inference run pass. Visual fitting still fails.

For Linux or an existing PostgreSQL server: install `requirements.txt` and a matching torch
profile, set `DATABASE_URL`, run `python -m alembic upgrade head`, download assets, then start
uvicorn and Vite. `docker-compose.yml` supplies an optional PostgreSQL service; Docker was not
installed here, so that route was not executed. `requirements.lock.txt` captures the actual
original CPU Windows/Python environment; `requirements-vton-cuda.lock.txt` records the installed
CUDA/neural profile. `frontend/package-lock.json` locks npm dependencies. Additional pinned
neural dependencies are in `requirements-vton.txt`.

The 2D model assets are provisioned locally with `scripts/download_parser.py` and
`scripts/download_vton.py`; the optional Windows CUDA-wheel downloader is
`scripts/download_cuda_runtime.py`. Each pins official sources and checksums. Inference never
downloads a model or uploads a photo. Model setup, exact revisions and license restrictions
are documented in [docs/vton-model.md](docs/vton-model.md).
The optional `scripts/download_vton_mix.py` provisions the official mixed attention checkpoint
with a separate manifest. It is downloaded and verified for experiments; it is not the selected
or visually accepted application checkpoint.

## Validate

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check backend ml scripts tests
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe scripts/validate_reconstruction.py
.venv/Scripts/python.exe scripts/inspect_open3d.py
.venv/Scripts/python.exe scripts/validate_garments.py
.venv/Scripts/python.exe scripts/smoke_api.py --all-categories
.venv/Scripts/python.exe scripts/evaluate.py
```

For actual pretrained-model inference, run
`.venv/Scripts/python.exe scripts/validate_pretrained_vton.py --all`. It uses the retained
reported person/striped-shirt inputs plus an alternate person and garment. Private uploads
are not bundled in a clean checkout. The report records generation, failures and timings;
each generated image still needs visual review. With the app running,
`scripts/validate_vton_api.py` checks the reported case, real checkpoint provenance,
semantic pixel preservation, independent sizing and unsupported categories.
`scripts/validate_2d_api.py` has also been updated for the pretrained contract and writes
`experiments/pretrained-2d-api-report.json`. These live inference checks remain pending.
Earlier `experiments/2d-*` reports concern the superseded geometric preview and do not
validate CatVTON or photorealistic fitting.

Verification as of 11 October: the prior full suite passed **89 tests in 38.33 seconds**
(`experiments/vton-pytest-report.xml`), with three upstream warnings. After the latest changes,
**33 focused adapter/precision tests passed**; the expanded full suite is pending. Ruff and
`pip check` passed. Real inference and its rejected visual review are recorded separately in
`experiments/catvton-initial-report.json` and `experiments/catvton-guidance5-report.json`.
The current frontend production build and TypeScript
checks passed on 10 October (`experiments/vton-ui-build-report.json`); two non-inference
category/error browser tests passed. Live neural API/browser generation remains pending.

From `frontend/`: `npm run build`; with the app running, `npm run test:e2e`. Playwright Chromium
is required (`npx playwright install chromium` during setup for browser tests). Run API and
browser generation tests sequentially: one pipeline job is admitted at a time; another
receives an actionable HTTP 429. This prevents unbounded local memory use.

`frontend/e2e/2d-fallback.spec.ts` checks unavailable-model handling and, when the actual
model is available, neural 2D PNG loading, original/try-on switching, null physical outputs
and browser errors. A skipped inference test is not evidence of working generation or
visual quality. The original 3D browser test explicitly selects 3D mode.

## Repository

| Directory | Responsibility |
|---|---|
| `backend/app` | FastAPI contracts, settings, normalized SQL models, asset store, orchestration |
| `backend/migrations` | Alembic schema versioning |
| `frontend/src` | React forms, result profile, React Three Fiber GLB viewer |
| `ml/preprocessing`, `ml/human` | Validation, pretrained pose/segmentation, body adapter and geometry |
| `ml/measurement`, `ml/sizing` | Mesh cross sections and weighted interval sizing |
| `ml/garment`, `ml/fitting` | Joined garment templates, photo UV texture, collision projection/relaxation |
| `ml/vton` | Pretrained CatVTON adapter, FASHN parsing, semantic replacement/preservation masks |
| `ml/tryon2d` | Superseded geometric preview, retained for debugging; not an API fallback |
| `ml/evaluation` | Measurement/pose/size metrics and leakage checks |
| `data/brandCharts` | Versioned synthetic charts; real sourced charts can be added through API |
| `data/processed/<runId>` | Inputs, masks/crops, keypoints, parameters, meshes, previews, result/failure |
| `experiments` | Actual verification reports and browser screenshots |
| `scripts`, `tests`, `docs` | Automated setup, milestone checks, regression tests and limitations |

Read [requirements](docs/requirements.md), [API](docs/api.md),
[model details](docs/model-adapter.md), and the full
[phase-by-phase status](docs/implementation-status.md).

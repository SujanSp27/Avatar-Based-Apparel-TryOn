# VastraView

Photo virtual try-on on the user's existing Google Colab GPU, with independent
brand size recommendations from photo estimates or tape measurements. The React
studio includes an editorial homepage, 57 garment references, account sessions,
a landmark measurement workspace, sourced brand charts, private scan history,
favorites, My Closet, and an original/generated photo comparison viewer.
Browsing is public; new try-on jobs require sign-in. See
[the frontend guide](docs/frontend-studio.md).
Independent
MediaPipe body-estimation and exact six-metric sizing APIs use MongoDB; see
[measurements and sizing](docs/measurements-and-sizing.md). There are 23 official
chart scopes across Nike, Puma, Manyavar, Adidas, Levi's and H&M, with explicit
India, UK, US or Kosovo applicability. Unsupported markets are not inferred.
The [fashion upgrade report](docs/fashion-platform-upgrade.md) lists sources,
image licenses, missing charts, tests and release gates. The active app
is now 2D only. Local GPU inference and the old avatar workflow are removed.

Start on this Windows installation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

The app is at http://127.0.0.1:5173 and the API at http://127.0.0.1:8000/docs.
The [API contract](docs/api.md) covers extraction, saved measurements, combined
extraction/sizing, brand administration, versioned charts, try-on jobs and health.
`/api/v1/health/ready?capability=measurements` checks measurement dependencies
independently of the Colab GPU; use `capability=tryon` for image generation.
The backend automatically checks the saved private worker, reopens the existing
notebook when needed, restores missing worker files on its GPU, and adopts the
new tunnel address. Recovery is automatic and offers Retry after a failure. Uploads can
be selected while the worker starts; generation is enabled only after a live check.

Google sign-in/consent and allocating a GPU remain controlled by Colab. The app
reports these conditions and resumes checking automatically. It never creates a
new notebook, resets a runtime, retries a submitted generation, or uses local CUDA.

For a fresh Windows install, `scripts/setup.ps1` installs the local web/API/database
dependencies. `scripts/setup_colab_bridge.py` installs the isolated, pinned Google
notebook helper. The existing notebook is recorded in ignored
`.runtime/colab-bridge/connection.json`; credentials are never committed.

The model is official FASHN VTON 1.5, with source/checkpoint revisions pinned in
`scripts/setup_online_worker.py`. Eleven UI categories map to tops, bottoms and
one-pieces. This does not establish visual quality for every garment; layered
ethnic outfit references remain browse-only. No training has been performed.
The fresh authenticated sage-polo test on 26 October took **34.837 seconds** in
the API pipeline (**22.696 seconds** GPU generation), on the existing private
Colab T4. It preserved the face and background; buttons and fine texture were
softened. Owner-only status/images, refresh, health interruption, comparison
controls and byte-identical downloads were verified. Evidence is saved locally
in `experiments/vastraview/private-tryon-fashion-upgrade/`.

The tested worker used FP16, 576 x 864 model resolution, guidance 1.5, full-frame
conditioning and 10 steps. Configuration is persisted in `config/online-worker.json`.
Accurate output within 30 seconds across people and categories is **not verified**.
VTON runs only in the user's Colab, never a public GPU demo or local GPU.
The independent measurement API uses local CPU. Only
unused unconditional predictions are skipped; the guided steps remain intact.
Lossless output patches retain the original pixels outside the clothing edit.
Recovery seeds this configuration only when the Colab file is absent; existing
runtime settings and running work are preserved. Warm model/pose caches help,
but every output is a fresh generation. Cold starts, shared GPU load and network
delays can exceed 30 seconds.

Colour-profile conversion and neckline/hem blending are corrected. Excessive
newly exposed skin is rejected rather than shown as a successful result. Skirt,
dress and second-person shoulder cases have failed visual review and remain
limitations, not production-quality support claims.

See [current requirements](docs/requirements.md),
[implementation status](docs/implementation-status.md), and
[automatic connection behavior](docs/automatic-colab.md). Actual timing and visual
evidence are in [online performance](docs/online-performance.md).
Previous 3D/CatVTON records are preserved under `docs/archive/` as historical
evidence, not as documentation of the current application.

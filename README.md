# Form / Fit Studio

Photo virtual try-on on the user's existing Google Colab GPU, with independent
brand size recommendations from measurements entered by the user. New independent
MediaPipe body-estimation and exact six-metric sizing APIs use MongoDB; see
[measurements and sizing](docs/measurements-and-sizing.md). Four verified Nike/Puma
India product guides cover men and women. The active app
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
new tunnel address. There is no connection button in the interface. Uploads can
be selected while the worker starts; generation is enabled only after a live check.

Google sign-in/consent and allocating a GPU remain controlled by Colab. The app
reports these conditions and resumes checking automatically. It never creates a
new notebook, resets a runtime, retries a submitted generation, or uses local CUDA.

For a fresh Windows install, `scripts/setup.ps1` installs the local web/API/database
dependencies. `scripts/setup_colab_bridge.py` installs the isolated, pinned Google
notebook helper. The existing notebook is recorded in ignored
`.runtime/colab-bridge/connection.json`; credentials are never committed.

The current model is official FASHN VTON 1.5, with source/checkpoint revisions
pinned in `scripts/setup_online_worker.py`. The eleven UI categories map to tops,
bottoms and one-pieces. Category support does not establish visual quality for
every garment. No training has been performed. The current research preset produced
a real graphic T-shirt in **23.080 seconds** and the striped sample in **25.151
seconds**, including transport. In the reviewed graphic-shirt example, the face
is preserved, collar/sleeves/hem align, and no old-shirt fragments are visible.
Small printed details are lost; striped collar corners and difficult shoulder
boundaries still need improvement. Accurate output within 30 seconds across
people and categories is **not verified**. VTON generation runs only in the
user's Colab, never in a public GPU demo. The separate measurement API uses local CPU.

A fresh upload through the browser completed in **25.449 seconds** to a visible
image (22.668 seconds in the API pipeline). The actual screenshot, timing and
visual review are saved in `experiments/live-balanced-upload-20261020/`.

`config/online-worker.json` persists FP16, 504 x 756 model resolution, guidance 1.5
and no crop. The API defaults to 10 steps and quality-95 input encoding. Only
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

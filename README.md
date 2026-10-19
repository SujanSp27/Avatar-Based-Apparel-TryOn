# Form / Fit Studio

Photo virtual try-on on the user's existing Google Colab GPU, with independent
brand size recommendations from measurements entered by the user. The active app
is now 2D only. Local GPU inference and the old avatar workflow are removed.

Start on this Windows installation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

The app is at http://127.0.0.1:5173 and the API at http://127.0.0.1:8000/docs.
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
every garment. No training has been performed. The best reviewed native-resolution
T4 example took **54.583 seconds**, improved from 292.278 seconds. A reduced-resolution
experiment took **14.914 seconds** but failed visual review because of sleeve and
hem artifacts. Acceptable fresh try-on within the requested 10-20 seconds remains
unverified. Photos are processed only in the user's Colab, never in a public GPU demo.
Native-resolution 10-step experiments reached 21.274s and 19.627s, but were also
rejected for neckline, exposed-skin and hem artifacts; they are not default presets.

`config/online-worker.json` persists the reviewed FP16/native-resolution profile
with guidance 1.5. Recovery seeds this configuration only when the Colab file is
absent; it preserves existing runtime settings and running work. Lossless image
transport reduces payload size without changing sanitized pixels, while stage
timings separate generation, preprocessing and transport costs. These local changes
have 438 passing CPU tests. A second-person graphic-shirt run reached 18.644
seconds but had a clipped hem. A dress run passed the corrected full-body check
but failed visual review. These native experiments include live transport and
stage timings; none establishes production-quality fast fitting.

See [current requirements](docs/requirements.md),
[implementation status](docs/implementation-status.md), and
[automatic connection behavior](docs/automatic-colab.md). Actual timing and visual
evidence are in [online performance](docs/online-performance.md).
Previous 3D/CatVTON records are preserved under `docs/archive/` as historical
evidence, not as documentation of the current application.

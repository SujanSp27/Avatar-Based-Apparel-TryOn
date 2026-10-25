# Automatic Colab connection

The API lifespan starts a background connection monitor. `/api/health` reads its
cached state, so a slow Colab connection does not block the web UI or database
health check. The frontend checks every three seconds during preparation and every
fifteen seconds when ready, with no overlapping requests or manual connect button.

The monitor first probes the saved private worker. If it responds, nothing is
launched. Otherwise the isolated Google notebook helper opens **only** the saved
Drive notebook. A persisted state machine recovers pending calls instead of
replaying them after an API restart. A busy notebook is left alone.

Before recovery changes any Colab files, a read-only probe identifies the runtime
hostname. That identity is saved in `.runtime/colab-autoconnect.json` and survives
API restarts. Every subsequent recovery cell compares its current hostname with
the saved identity before writing files or starting a process. If the browser
connection switches to another runtime, recovery reports `runtime_changed` and
does not adopt that runtime's credentials. It continues checking for the saved
runtime; it does not automatically replace the pin. This also prevents duplicate
tabs from redirecting setup to a different machine.

In the notebook, recovery checks actual process command lines. Existing setup and
inference processes are never stopped or duplicated. Missing worker files are
restored from an explicit source allowlist; the pinned setup runs in Colab, then
the worker loads its models and creates a private tunnel. Failed launches are
limited to three per hour for each of setup and worker. No recovery operation
submits person/garment images or starts an inference job.

The tracked `config/online-worker.json` supplies the reviewed starting profile:
FP16, native 576 x 864 resolution, guidance 1.5, no person crop, segmentation-free
conditioning and no conditional-branch shortcut. The recovery payload validates
these settings and creates `/content/formfit-online/worker-config.json` only if
that file is absent. It never overwrites an existing runtime profile or changes a
running worker. Thus missing temporary files can be restored without silently
reverting a new runtime to the much slower BF16 baseline. An existing experimental
runtime profile still requires an explicit operator change after its work finishes.

The returned HTTPS tunnel/token are written atomically to ignored
`.runtime/online-connection.json`. The running API adopts them without restarting.
Each submitted inference retains its original URL and event ID, even if the
connection file changes. Failed generation requests are never retried implicitly.
The default remote timeout is 600 seconds because the original BF16 T4 baseline
exceeded 180 seconds and cold starts or shared-runtime delays remain possible.
The reviewed native FP16 example completed in 54.583 seconds. The timeout prevents
premature failures; it does not improve model latency or guarantee a completion time.

Inputs use lossless WebP when it is smaller than the normalized PNG. The worker
returns lossless WebP, and the API validates the response object, declared and actual
image formats, payload size and original image dimensions before saving an actual
PNG. Older PNG worker responses remain supported. Transport diagnostics record byte
counts and preparation/encoding/request/saving times; worker diagnostics record
preprocessing, generation and postprocessing/saving times. These changes have local
CPU tests but do not establish a new live latency result or current Colab availability.

The optional `ONLINE_VTON_INPUT_ENCODING=jpeg95` setting changes only model
conditioning uploads and requires changed-pixel worker responses. It remains
experimental; the default is lossless. Even with compressed conditioning, the API
retains its original PNG and uses those exact pixels outside the generated patch.
Rejected generations save a `remote-failure.json` record containing the remote run
path and timing where supplied. This allows raw-output/mask recovery without
resubmitting an inference job. It does not turn a rejected result into a success.

The interface reports preparation, model loading, restoration, readiness and
external constraints. Google authentication/consent and GPU allocation remain
browser actions when Colab requires them. There is no local GPU or public VTON
service fallback. Do not share `.runtime` or notebook outputs: recovery responses
contain the private worker token, which is omitted from health responses and logs.

`ONLINE_AUTO_CONNECT=true` is the default. Setting it to false disables notebook
automation for service operators while retaining live checks of configured workers.
The existing notebook identity remains in
`.runtime/colab-bridge/connection.json`; no scratch/new notebook is ever selected.
If Colab permanently replaces a runtime, a service operator must first verify the
replacement with a read-only identity check and explicitly update the runtime pin
while recovery is paused. Pin changes are refused while a notebook call is
pending. This is a recovery safeguard, not an additional step in the try-on UI.

# Colab recovery and the sage polo

The frontend remains served locally during inference outages. Photos are sent only
to the user's private Colab worker. An unavailable GPU cannot produce a new image;
there is no local GPU or pasted-shirt fallback.

## Changes

The old recovery controller pinned a hostname permanently and paused on every
replacement. It now requires two matching, spaced GPU identity observations from
the same bridge session, blocks adoption while a local inference job is active,
then rechecks the adopted hostname inside the executing recovery cell. No
credentials from a mismatching runtime are accepted. Existing notebook cells,
weights, configurations, tokens and results are retained.

Recovery checks the actual Python environment and required model files, rather
than trusting a completion marker from an earlier runtime. A Colab filesystem
lock serializes recovery calls. Setup/worker launches are capped at three per
hour. An idle worker with an expired tunnel is restarted only after three spaced
failed checks; command-line ownership is verified before signalling its PID.
An active generation marker prevents this restart.

Three verified runtime replacements in fifteen minutes trigger a cooldown rather
than reinstalling endlessly after runtime crashes. Setup constrains torch,
torchvision and NumPy to the compatible versions already installed in Colab and
disables parallel Xet download buffering. This reduces avoidable installer churn;
it cannot prevent Google from terminating a runtime or prove a particular crash
was caused by memory pressure.

`POST /gradio_api/run/status` authenticates the worker token and reports whether
the pinned FASHN model and CUDA are loaded. Listing an endpoint or saving a URL
does not establish readiness. The app checks with a four-second network timeout
and a ten-second cache keyed by URL **and** token. Snapshot readiness expires
after thirty seconds.

During live restoration the Gradio JSON component emitted `root={...}` Python
representation text instead of a JSON object. The worker now explicitly encodes
JSON into text outputs for status and generation. Both clients accept JSON text
or legacy JSON objects, reject malformed values and verify the model revision.
Python representation text is never evaluated. Notebook exceptions supersede
preceding progress lines and become a retryable `recovery_failed` state.

- `GET /api/tryon/availability` reads the monitor without requiring PostgreSQL.
- `POST /api/tryon/retry` wakes the existing monitor; repeated clicks coalesce.
- New inference submissions validate inputs and model readiness. Idempotent
  resubmissions return their existing job even during a later outage.
- An interrupted result stream retries GET for the same event at most twice,
  with backoff and the existing total timeout. Generation POST is never retried.
- Completed jobs and original/generated images remain in local storage. A page
  reload resumes the saved job. Poll requests expire after eight seconds and
  back off during outages; upload acknowledgements expire after forty-five seconds.

The UI reports Ready, Preparing, Recovering, or Temporarily unavailable. A delayed
notebook call remains recorded instead of being replayed. After prolonged
preparation it shows an outage and a Retry action. Google sign-in, notebook
permission prompts and GPU allocation may still require the user; these cannot
be bypassed by the app. The existing comparison component and its styles were
not changed.

Notebook recovery supervises actual setup/loading for at most three minutes in
the executing cell, emitting state progress. It returns immediately for a changed
runtime, an unavailable GPU, failed setup, or unrelated work; supervision expiry
leaves the running process intact. The bridge preserves the pending request ID
through an API restart. This is bounded supervision of necessary work, not an
idle-runtime keepalive.

## Garment input and quality

The sample action and garment rail now select `data/raw/sage-polo.jpg`, a real
flat-lay piqué polo photograph. Its origin is recorded in
`data/raw/sage-polo-source.json`. The original striped garment is still available
at its existing endpoint. The polo is supplied to the actual FASHN VTON 1.5 model
with the original studio person photograph; it is never used as an AFTER image.
An AFTER result is displayed only after successful inference. Selecting a polo
does not itself prove garment quality: the generated neckline, sleeves, hem,
identity preservation and artifacts still require full-resolution review.

The real sample job `f773078b-48fc-4283-863b-b26ccf7bd0d4` completed in 24.591
seconds using the private Colab T4 (16.045 seconds generation, 18.620 seconds
worker time). Its 800 x 1200 result shows a sage polo with a coherent collar,
short sleeves and hem. The original face, outer background and lower body remain
pixel-identical in the measured regions. Fine fabric and button details are
softened, so commercial detail fidelity is still partial. Evidence and visual
review are in `experiments/recovery-polo/`; one example does not guarantee the
same speed or quality for every photo.

`/tryon?job=<UUID>` opens a real retained job through the existing API and stores
that selection for refresh. It does not submit inference, change the comparison
layout, or replace another person's uploads with this example. Invalid IDs are
ignored; unavailable jobs use the existing error handling. Completed results
remain viewable even while the next Colab runtime is being restored.

## Verification

Targeted Python tests cover replacement verification, runtime alternation,
active jobs, stale health, rotated credentials, missing model files, owned
process restart, bounded stream retries and retained event IDs. Browser tests
exercise recovery, explicit retry, hanging health requests, upload preservation,
job restoration, and the unchanged comparison UI. Those tests do not fabricate
evidence of a new neural result. Current live-inference evidence and limitations
are recorded in `implementation-status.md`.

On 22 October, a local app restart encountered an expired tunnel and a different
GPU hostname. The automatic controller verified the replacement, restored the
worker and returned to Ready without manual notebook setup. The retained polo
job still returned success. A live Chromium test loads that exact job and its
images, checks refresh/slider/zoom/download, simulates a health-request outage
and confirms the generated result remains accessible. The main viewer component
and its styles are unchanged.

Final saved verification: 597 Python tests passed; 14 Chromium tests passed and
one fresh-upload test was deliberately skipped. TypeScript, the production Vite
build and Ruff passed. The complete suite also exercised real measurement,
brand-size and account APIs. No duplicate polo inference was needed to verify
the viewer after the API restart.

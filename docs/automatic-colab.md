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

The returned HTTPS tunnel/token are written atomically to ignored
`.runtime/online-connection.json`. The running API adopts them without restarting.
Each submitted inference retains its original URL and event ID, even if the
connection file changes. Failed generation requests are never retried implicitly.
The default remote timeout is 600 seconds because measured T4 generations exceed
180 seconds. This prevents premature failures; it does not improve model latency.

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

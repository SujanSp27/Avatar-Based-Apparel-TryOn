# Colab GPU inference

The self-contained [Virtual_TryOn_GPU notebook](../notebooks/Virtual_TryOn_GPU.ipynb)
runs the existing 2D inference pipeline on a Linux GPU runtime. It requires no Git
remote, repository upload, local database or Windows Python environment. Google
sign-in, GPU allocation, and Google's own authorization prompts remain account
actions; the agent can perform notebook setup and inference once the connected
Colab runtime is authorized. No paid runtime is purchased by this notebook.

The notebook installs a separate environment and checks CUDA before loading the
pretrained model. It evaluates CatVTON's pinned `mix-48k-1024` checkpoint at
768 × 1024, 50 steps, guidance 2.5, seed 42. FASHN semantic parsing, the existing
replacement mask, identity preservation, and the garment-fidelity rejection
check remain active. No image-overlay fallback is available. Model and parser
assets are fetched from their official hosts with the project's pinned revisions
and checksums. Runtime and package reports record the actual cloud environment.

## Verified progress through 13 October 2026

On 12 October, the connected notebook reported a Tesla T4 with 15,360 MiB of
VRAM (`experiments/colab-hardware-report.json`). Source extraction and the
isolated dependency/download setup completed. That verifies setup, not a loaded
cloud model or completed cloud inference: no generated Colab image has yet been
retrieved or visually accepted.

On 13 October, the combined runner exported four real failure reports from a
T4 runtime with Python 3.12.14 and torch 2.5.1+cu121. They identified an inherited
Colab plotting-backend setting that prevented MediaPipe import before model
inference. `scripts/colab_runtime.py` now sets `MPLBACKEND=Agg` inside the
inference process; the corrected rerun is pending. The archive and extracted
reports are retained under `experiments/colab-tryon-results-20261013.zip` and
`experiments/runs/colab-initial-environment-failure`.

A later browser reconnection opened a different, empty scratch notebook. Its
probe found no NVIDIA device. The earlier T4 report describes the earlier
runtime; it does not establish the hardware of the currently connected notebook.
The agent is reconnecting and checking the active runtime again. Google sign-in,
connection consent, and selecting **Runtime > Change runtime type > T4 GPU**
remain browser account actions when prompted. Dependency installation, source
transfer and inference are handled by the agent after the runtime is available.

The three completed local CatVTON configurations remain visually rejected:
the first two lost the cream stripes, and the reduced-resolution mixed checkpoint
invented a different pattern. The local native-resolution run was interrupted
before producing a final image. Moving the run to Colab makes a larger GPU
available; acceptable fitting still requires actual inference and image review.

## What is transferred

`scripts/build_colab_notebook.py` embeds a deterministic source ZIP using a fixed
allowlist. The archive contains inference code, upstream licenses, dependency
requirements, download/setup scripts, and five explicit regression images:

- The exact studio person and striped garment previously reported by the user,
  matched by SHA-256 against the retained inputs.
- Two garment photographs and one person photograph from CatVTON's pinned
  official examples, accompanied by their attribution/rights manifest.

No `.env`, credentials, private upload directory, database, checkpoints, virtual
environment, logs from earlier private runs, or frontend dependencies are
included. The archive is verified before extraction; every member is checked
against `SOURCE_MANIFEST.json`. Extraction rejects path traversal, duplicate
members, symlinks, hash mismatches and unexpected contents.

The default destination is `/content/avatar-vton-<source-hash>`. Google Drive is
not mounted by default. The optional persistence cell requires an explicit
`SAVE_RESULTS_TO_DRIVE = True` change and Google's authorization; it copies only
the generated result ZIP into `MyDrive/AvatarVTON`. It does not search or read
unrelated Drive content.

## Evidence and acceptance

Four inference cases run sequentially in separate processes: the exact striped
regression, a different garment, a different person, and the supported `shirt`
category. This adapter supports T-shirts and shirts only. Each process saves its
real inputs, masks, model output, final candidate when generated, model
provenance and error/report information. The notebook displays the original
person and actual garment beside the candidate. Rejected raw model output is
explicitly labeled a diagnostic, not a successful virtual try-on.

Review neckline, shoulders, both sleeves, hem, old-shirt removal and preservation
of the uploaded garment's pattern/colors. Compare identity, hair, hands, body
proportions and background against the original. A zero process exit code or a
non-rejection by the conservative stripe check does not establish natural fit
or overall garment fidelity. Results remain pending visual review until the
actual images are inspected.

The notebook downloads an archive containing the actual run artifacts. It does
not generate body measurements or invent a recommended size. Brand-specific
sizing remains independently implemented by the application's existing engine.

`scripts/collect_colab_results.py` imports downloaded result archives into an
empty local inspection directory, checking allowed paths, file sizes and
available SHA-256 entries before writing. Failed runs remain failures; generated
candidates remain pending visual inspection.

## Training

User authorization permits fine-tuning if it becomes justified. The supplied
images are unpaired regression fixtures, not a supervised try-on dataset. This
notebook performs pretrained inference only. Fine-tuning requires a suitable
licensed paired dataset, person/garment-disjoint evaluation split, a reproducible
training objective/configuration, and hardware capacity; none is inferred from
access to a larger GPU. CatVTON and the parser retain their research licenses.

## Continuing across chat interruptions

`scripts/colab_notebook_control.py run-all` prepares one notebook code cell that
checks for a GPU, verifies and extracts the source, sets up the isolated
environment, executes the four regression cases sequentially and exports the
result ZIP. Image inspection remains a separate notebook cell so the combined
tool response does not exceed the official bridge's message limit. It excludes the optional Drive
authorization cell. Once started, these stages do not wait for another chat
turn between cells. This combined cell has been compiled locally; its complete
cloud execution is still pending.

The agent checks the connected notebook's cell IDs and execution state before
resuming work. Existing mappings are preserved when explicitly staging a new
session; a mismatched notebook is not assumed to contain the previous job.
Completed reports and result artifacts must be retrieved before treating a
runtime as disposable. A running notebook cell is not a guarantee that Colab
will retain the runtime, GPU allocation or files indefinitely. Reconnecting to
a new scratch notebook does not resume an old process.

## Rebuilding and fallback operation

The agent rebuilds the notebook after modifying any included source:

```text
.venv/Scripts/python.exe scripts/build_colab_notebook.py
.venv/Scripts/python.exe -m pytest tests/test_colab_notebook.py
```

`experiments/colab-notebook-report.json` records archive/notebook SHA-256 values,
the exact file manifest and static checks. Those checks validate packaging,
privacy exclusions and executable Python cells; they do not imply successful
cloud execution or acceptable generated images.

The 12 October local regression run passed **273 Python tests**
(`experiments/colab-pytest-report.xml`), and both existing browser tests passed
(`experiments/browser-test-report.json`). The browser tests exercise the local
3D workflow, size recommendation and GLB controls; they do not validate neural
2D fitting or prove a Colab inference result.

If the connected Colab browser is unavailable, the fallback is to open the
generated notebook in Colab, authorize a GPU runtime, then execute its cells in
order. This is a fallback operation, not a requirement to repeat local project
setup. Result downloads work without Google Drive authorization.

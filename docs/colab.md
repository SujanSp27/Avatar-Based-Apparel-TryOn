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

The existing four-case job **completed**. Its browser download was already present
when the local bridge connection expired. The archive was copied into
`experiments/colab-corrected-results-20261013.zip` (16,107,471 bytes; SHA-256
`37038cec9aac4d011e8878d822d8ab2933de42215eb718747832cb131b6bbea5`).
All 98 files were recovered under `experiments/runs/colab-corrected-20261013` and
available artifact hashes were verified. No Colab restart, new cloud notebook,
or new inference was performed during recovery.

Run `20261013T103702748573Z` used Python 3.12.14, torch 2.5.1+cu121 and Tesla T4
(14.56 GiB reported by PyTorch). Model provenance confirms actual mixed-checkpoint
loading and 768 by 1024 inference, 50 steps, guidance 2.5, seed 42.

| Case | Seconds | Inspection |
|---|---:|---|
| Reported striped shirt | 144.331 | Rejected: native output invents beige fabric and loses the stripes; quality guard withheld the final PNG |
| Different garment (95 jersey) | 146.090 | Generated, then rejected visually: severely distorted digits and side-edge artifacts |
| Different person (vest to T-shirt) | 148.972 | Generated, then rejected visually: missing sleeves in raw and final output; shoulder remnants |
| Shirt category (black graphic shirt) | 148.112 | Promising prototype candidate with plausible fit; small print and underarm-edge defects remain |

The [local image gallery](../experiments/colab-review-20261013/index.html) includes
the real inputs, raw images and final candidates. The
[review report](../experiments/colab-review-20261013/report.json) records visual
findings and zero changed pixels in parsed face/hair/hands/lower-clothing regions
for all three final candidates. These pixel checks do not prove perfect parsing
or natural fit. The exact striped-input acceptance remains unmet.

The revised local sleeve mask uses existing shoulder/elbow landmarks to admit
short-sleeve generation. Offline tests and previews confirm additional upper-arm
coverage without opening protected classes. No neural inference with this mask
revision has run, per the user's instruction. The existing local notebook source
package was updated; the cloud notebook and archived run were left untouched.

Earlier environment-only failures are preserved separately under
`experiments/runs/colab-initial-environment-failure`. They exposed Colab's inherited
`MPLBACKEND=matplotlib_inline` setting; the completed job verifies the `Agg` fix.
They are not model-quality results and must not be confused with the recovered
16 MB archive. Earlier local low-resolution outputs also remain separate evidence.

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
turn between cells. Its complete cloud execution and exported artifacts have now
been recovered. **Do not execute `run-all` again to recover this completed job.**

`experiments/colab-recovery-state.json` identifies the original cell
`Em_0D8PY0j5r`, request `27a77575-8908-4770-b629-3351a2105b11`, archive and review.
The local bridge's last `processing` status is stale: its process has exited.
The current live runtime status is unknown, but the job's completion is proven
by its four reports and exported outputs. Opening the official bridge's default
scratch notebook does not recover this old execution. No manual intervention
was needed to retrieve the already-downloaded results.

The local gallery was opened in headless Chromium: all four case sections and
all 23 saved images loaded with no page errors (`experiments/colab-gallery-browser-report.json`).
This browser check does not run inference or change any recovered image.

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

The 13 October recovery continuation passed **278 non-integration tests in 44.07 seconds**,
with 16 integration cases excluded to honor the instruction against new inference.
Ruff and `pip check` passed. The revised notebook package is a local artifact only;
`experiments/colab-executed-notebook-report.json` retains the source manifest used by the
completed cloud run. Recovery never stages or executes the updated package in Colab.

For an explicitly authorized future evaluation, the agent can use the packaged
notebook after checking the existing runtime. That is a new evaluation, not
recovery. This continuation's instruction prohibits new runs and new notebooks;
the updated mask therefore remains untested by neural inference. Result downloads
work without Google Drive authorization.

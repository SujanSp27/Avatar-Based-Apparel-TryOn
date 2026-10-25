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

## Active continuation (14 October 2026)

The notes above describe the completed 13 October recovery. The user subsequently
requested a new Colab evaluation and supplied the existing saved notebook URL.
`scripts/colab_server.py` reconnects the pinned official bridge to that exact Drive
notebook; it validates the host/path and rejects scratch notebooks and URL fragments.
The runtime probe found a Tesla T4 with 15,360 MiB and no previous project files.
The earlier downloaded archive remains intact locally. The runtime was not restarted.

The revised source archive is
`e1370ca73948bf04546bebdec75ab505b01a0e358fd283c2a0196de0a07ace37`
(39 allowlisted files). Existing notebook cell `V3iNa7O92K-q`, bridge request
`497dc51f-1194-4525-89d4-293276ec38eb`, was submitted at 09:57 UTC. This is a new
four-case evaluation of the corrected sleeve masks, not a replay of the recovered
job. Do not submit it again while its execution is unresolved. A bridge timeout
does not establish that the notebook cell stopped; inspect existing downloads and
execution state first. No training or fine-tuning is involved.

The local web app now uses persisted asynchronous jobs with refresh recovery and
real step progress. Those jobs use local hardware. The Colab notebook remains a
separate interactive GPU evaluation; no tunnel or Colab-hosted HTTP worker is used.

The four-case run above **completed** at 10:12 UTC. The 16,141,392-byte archive is
`experiments/colab-sleeve-results-20261014.zip`, with 102 verified files collected into
`experiments/runs/colab-sleeve-20261014`. The local review is
`experiments/colab-review-20261014/index.html`. Three images were generated, but the
stripe regression was rejected and the vest case still lacks sleeves. Completed
inference is not visual acceptance.

The subsequent two-case comparison uses the existing vitonhd checkpoint, native
384x512 resolution, and a rounded shoulder-cap mask. Its source archive hash is
`1c2df277fa3e392fd076f9bb463e721eeb93cbf2cf64a72bfee66b3d96cdb1b3`.
`experiments/colab-comparison-20261014.py` refuses to overwrite an earlier comparison
and requires the completed four-case archive plus its existing virtual environment.
It does not reinstall dependencies. The insertion request is preserved under
`.runtime/colab-bridge/awaiting-connection`, pending a successful runtime probe.

Evening update: the runtime probe returned a T4 but **no previous project files**.
The original insertion was never sent and remains archived. After local recovery of
all completed artifacts, the pinned environment is being restored in the same saved
notebook. Comparison cell `n-4YNzbo-7cG`, request
`2a0b8daa-c1c9-45d8-8cdf-e199b01b5eb0`, runs only the two new cases. The comparison
script was adjusted to use this restored environment. The four-case job is not replayed.
`experiments/colab-continuation-state-20261014.json` records both evaluations separately.

## Recovery safeguards (15 October 2026)

The saved comparison cell proves both cases completed and a 5,622,834-byte ZIP was
created. Its striped case was rejected; its second-person case generated an image.
However, no new ZIP was found locally, and the current runtime reports no project
files. Its second image therefore has **not** been visually reviewed. A successful
notebook log is not enough to claim acceptable fitting.

The local bridge now permits bounded 8 MiB WebSocket messages so an embedded source
cell can be read without the upstream 1 MiB limit disconnecting it. Origin and token
checks remain intact. The notebook exporter now includes at most four JPEG recovery
previews of at most 128 KiB each, labelled as unreviewed candidates or rejected
diagnostics, with input and full-image hashes. Full PNGs/reports stay in the ZIP.
This improves future recovery; it cannot recreate an unretrieved comparison image or
guarantee that Google saves notebook outputs. The prepared notebook has not been
executed again as part of this recovery.

The user subsequently confirmed that the **original tab still has the project folder**.
An empty runtime in the connector is therefore not proof that every runtime's files
are gone. The requested manual action is only to download the existing ZIP from that
original tab, which the notebook connector cannot select. The saved execution output
is preserved in `experiments/colab-comparison-execution-20261015.json`; no comparison
inference was replayed during recovery. Forty-four focused recovery/notebook/job tests
passed in 4.62 seconds and Ruff passed (`experiments/recovery-tests-20261015.xml`).

The supplied Downloads folder `colab-tryon-results (2)` was subsequently checked:
its ZIP hash, source manifest and all four reports match the already recovered
14 October morning run. `experiments/download-identity-20261015.json` records this.
The user confirmed the later 5,622,834-byte ZIP is no longer available. Recovery of
that comparison image is blocked; retain its completion log without a visual verdict.

After the user's continuation, the existing notebook's runtime probe returned a
T4 with no project files. A new, explicitly separate three-case conditioning
ablation was submitted in cell `3R0B-DHoStfR`, request
`c34abe96-2bc0-4dd0-a7ce-9e431c684177`, using verified source archive
`38a9b75373f46da755c0bdaac32a5e811e1f6b7ce8156849ee232e2d3bff07cc`.
The original notebook and runtime were not restarted. The isolated environment
must be restored because its previous files are absent. Check
`experiments/colab-conditioning-state-20261015.json` before taking any action;
do not replay an unresolved cell.

This compares official and experimental reference-anchored conditioning on the
same striped input, then checks the second person with the experimental mode.
Checkpoint, rounded sleeve mask, seed, guidance and native resolution stay fixed.
It is an inference ablation, not training or the trained Re-CatVTON method.
`--conditioning reference-anchor` is explicit; the application's default stays
official until actual results justify a change. Adapter/runner tests passed
86 cases, and packaging/service tests passed 34 cases.

`scripts/retrieve_colab_archive.py` reads an existing result ZIP through one
dedicated notebook export cell in bounded 512 KiB chunks. It retains request IDs,
checks every chunk and the full ZIP, and resumes pending reads without submitting
them again. It never executes inference. Use `python -m scripts.retrieve_colab_archive`.
The importer accepts `--expected-manifest` to reject an archive from a different
source revision before writing any results. A generated report without its final
PNG is also rejected. These recovery checks do not assess garment realism.

Both 15 October evaluations are now completed, recovered and visually reviewed.
The conditioning archive has 79 files (SHA-256
`c20ccdd55490f7ee77c771ad1cc57a132b25bc46d3ef9894e4f205b9fabe3f90`);
the two additional garment cases have 55 files (SHA-256
`1f053e520f9e18e32734db4c49b37d50afeb835374f32b1facb630b31f023a26`).
The latter used source `b792ecc27c6a0ae3fc3890f96a9495e4181b0c6ccc1166da2740f08bedf1de16`,
cell `_IBlIxGVXfIC`, request `394d896f-d255-4280-a35e-e06fbab49369` and reused the
existing runtime's verified environment/checkpoints without reinstalling them.
No cloud job remains pending; do not replay these completed evaluations.

The three photographed studio-person candidates now retain recognizable uploaded
garments. Text, collar and stripe-placement errors remain. The second-person image
is rejected because the model narrows its shoulders; the new compositor guard
detects this instead of erasing original skin. Galleries and individual observations
are linked from `docs/implementation-status.md`. The application now defaults to the
evaluated reference-anchor mode, while the low-level model/notebook runner keep
explicit conditioning selection for reproducible comparisons.

# Wardrobe curation — 28 October 2026

This is an ongoing evaluation, not a claim that twenty garments are approved.
No product records, source assets, favorites, personal photos or results are deleted.

## Audit and stages

1. Audit the 57 locally available catalog references, actual decoder, source bytes,
   categories, pinned worker and private API. Preserve a baseline and source sheets.
2. Test 38 individually selected candidates against a fixed studio photograph and
   the upstream mirror example, keeping seed, precision and model settings fixed.
3. Review actual inputs, parser masks, conditioning tensors, raw and composite outputs.
   Retest changes in separate directories. Do not replace evidence from a failed run.
4. Publish exactly twenty only if every selected item passes both person cases,
   objective checks, explicit visual review and measured under-30-second latency.
   Archive complete metadata and exclusion reasons before atomically publishing.
5. Check catalog/security/browser regressions and the existing compact result UI.

## Current model and discovered failure

FASHN VTON 1.5 source commit `7c0f10af3f91ad4048fe9729c470a13ef905d25a`, weights
`7720683168567eb5a2a4c67f15116c6e29c83ded`; private Colab Tesla T4, FP16,
576 × 864, guidance 1.5, seed 42, 10 steps. Existing parsing/preservation and
conditional-branch optimization are unchanged. Size inference remains separate.

The model accepts `tops`, `bottoms`, `one-pieces`; application categories map to
these groups. That mapping alone never establishes garment quality. Ethnic
multi-piece/draped references have no supported mapping. Six older research
references lack established commercial image rights and are excluded from the
production candidate pool, while their original records remain intact.

The [pinned official pipeline](https://github.com/fashn-AI/fashn-vton-1.5/blob/7c0f10af3f91ad4048fe9729c470a13ef905d25a/src/fashn_vton/pipeline.py)
disables garment masking for `flat-lay`, which it describes as product shots with
plain backgrounds. Several community catalog photographs instead show colored
bedding/floors or hangers. Actual raw output transfers background colors into
unrequested fabric: red bedding becomes a red garment and pale backgrounds become
extra sleeves/underlayers. This occurs before final compositing. Correct category,
reference bytes and tensors are checked against retrieved trial artifacts;
missing artifacts never count as a pass.

The controlled green-polo experiment removes only the observed background using
its actual saved FASHN mask, retaining all foreground pixel values and dimensions.
The new result removes the extra beige sleeves/hem layer, at 26.525 seconds observed
end to end (24.597 server, model/transport stages saved in its trial). The same
experiment on the black polo still retains hanger-like stripes at the neckline
and changes the jeans: rejected. Neither experiment is a blanket preprocessing
change or an approval of every background mask.

The current ledger covers **63 trials across 38 garments**: 38 original-reference
cases, 24 background-only cases and one separately retained transport retry.
There are **60 generated images, all inspected at full resolution**, and three
failed requests. Three studio cases look plausible (green polo, teal shirt and
burgundy sweater), but all three fail on the mirror person with sleeve/wrist,
shoulder or hem artifacts. The teal studio case also exceeds the timing limit.
Therefore
**zero garments currently pass the complete two-person approval contract**.

Measured end-to-end times span **26.422–36.560 seconds**; 33 of the 60 generated
cases were strictly below 30 seconds. Faster generation is not a quality pass.
Shorts/skirt trials can retain jeans or invent split garments even after the
reference background is removed. Fine prints, lettering, cuffs and buttons are
often lost. These are observed model/reference limitations, not reasons to lower
the acceptance threshold or label every supported category reliable.

The latest reserve tests make the input-background limitation particularly clear:
an orange checked shirt initially becomes a small shirt photograph printed on a
different top. Its reviewed background-only variant restores checked fabric but
still introduces an inner layer and broken cuffs. An ivory tie-neck blouse loses
the tie and neckline construction; printed leggings become plain black trousers
even with a neutral background. The grey crop-top parser reaches the source image
border, so that background transformation was rejected before inference.

Saved raw/composite comparisons also isolate boundary errors. Removing the
shoulder-projection step in an **offline diagnostic only** removes some pointed
sweater artifacts but exposes old arm fragments; that change was not promoted.
No model setting, production preservation mask or source garment shape was changed
to hide these failures. A separate 20-step diagnostic request failed at transport
before returning an event. After recovery verified a new idle T4, a separately
saved 20-step run completed in **55.846 seconds** (1.940 preprocessing, 46.693 GPU
generation, 1.938 postprocessing/saving). It improves the right sleeve but retains
a left upper-arm edge artifact and changes the round neckline into a V-neck.
It is rejected. Decoded input hashes, seed, guidance and model profile match the
28.634-second ten-step baseline; the runtime changed, so this is not a controlled
warm-cache latency benchmark. All 15 audit files were recovered, tensor/mask
checks pass, and parsed protected pixels remain identical. These diagnostic runs
are separate from the 63 standard trial counts. The app still uses ten steps.

## Acceptance contract

- Source must decode through the real `normalized_image`, with supported format,
  minimum 128 px side and maximum 20 MP; images are not upscaled to claim detail.
- Border outlier fraction >10% (35 RGB-unit distance from median border), Laplacian
  variance <30 and short edge <384 px are review flags only. They cannot certify
  foreground accuracy or automatically reject simple low-texture fabric.
- Actual parser labels must align with original inputs; category clothing must
  occupy at least 2% of its reference. Edit mask coverage must be 0.5–85% of the
  output. These reject empty/excessive masks, not subtle fit errors.
- Recorded RGB conditioning is H×W×3, pose conditioning H×W×1 with finite-value
  checks in the worker and recorded SHA-256 fingerprints. Transport-aware input
  hashes distinguish JPEG95 conditioning from a lossless decoded source.
- Real inference must complete; output must decode, preserve original dimensions,
  have >=0.5% changed pixels, and match its saved byte hash. A returned image is
  **generated**, never automatically approved.
- Both fixed people require full-resolution visual review with reference fidelity,
  anatomy, boundaries and preservation rated >=4/5; no major artifacts. A 4 means
  convincing appearance with only minor detail loss, not exact physical fit. Every
  review records reviewer, timestamp, output hash and concrete notes. Automated
  color or mask metrics cannot replace this review.
- Strict observed end-to-end latency <30 seconds for both tested cases. Worker
  preprocessing, generation, postprocessing, network and API times remain separate.
  Poll/download overhead is included in the observed time; cold starts and shared
  Colab variability prevent a universal guarantee. Do not discard a slow run to
  report only a faster repeat.

## Reproduction and recovery

From the repository root, using the existing private Colab worker:

```powershell
.venv/Scripts/python.exe -m scripts.evaluate_wardrobe audit
.venv/Scripts/python.exe -m scripts.evaluate_wardrobe create-session
.venv/Scripts/python.exe -m scripts.evaluate_wardrobe run --candidates data/catalog/wardrobe-candidates-v1.json
.venv/Scripts/python.exe -m scripts.retrieve_wardrobe_audits
.venv/Scripts/python.exe -m scripts.retrieve_wardrobe_audits --transport http
.venv/Scripts/python.exe -m scripts.curate_wardrobe report
.venv/Scripts/python.exe -m scripts.report_wardrobe_trials --additional experiments/wardrobe-neutral-retry
.venv/Scripts/python.exe -m scripts.curate_wardrobe publish
```

`create-session` is a one-time normal signup, not an admin or authentication bypass.
Cookies stay under ignored `.runtime/`. Do not run another browser test with that
same session while evaluation is using it. Resuming reuses the saved idempotency
key and polls accepted jobs; 401/429/503 preflight failures do not create new jobs.
The app's 12-per-15-minute account limit remains enforced. The evaluator pauses
on rate limits; resume in the next window. It never starts local GPU inference.
The notebook helper can require Google's browser permission even while the GPU
worker remains usable; pending calls must be recovered, not replayed blindly.
Artifact retrieval now journals pending cell replies per trial, resumes those
same reads, validates returned filenames/base64 and reports actual recovered and
missing file counts. `--ids` and `--people` restrict retrieval to saved cases.
The updated private worker also exports saved audit files over its authenticated
HTTP endpoint. Each read requires the worker token, exact run ID and both decoded
input hashes. Only a fixed, size-bounded file list from a completed run can be
retrieved; the client verifies names, sizes and SHA-256 hashes before writing.
No inference is triggered by a read. Eight real cases have all 15 available audit
files recovered this way, without waiting for a notebook-browser connection.
The evaluator records generation timing **before** artifact transfer, downloads
audits immediately, and can resume a matching partial file without overwriting
conflicting evidence. The recovery source archive includes the audit module.
The bridge saves a completed reply before refreshing tool discovery, and allows
240 seconds for a recovery cell that supervises setup for up to 180 seconds.
Discovery and browser-connection calls retain short bounded timeouts.
Discovery timeout no longer terminates a live helper and rotates its socket token;
it keeps the existing browser connection and retries discovery with backoff.

Experiment inputs/results stay in ignored `experiments/wardrobe-curation/` and
`experiments/wardrobe-neutral/` and `experiments/wardrobe-neutral-retry/`. Original catalog metadata remains in
`data/catalog/garments-v2.json`; reviewed candidates and publication policy have
separate versioned manifests. `publish` refuses a shortfall and writes an archival
snapshot before selecting the twenty passing items. Source or metadata changes
invalidate approval; there is no manual "approve HTTP 200" switch.

Private review outputs:

- `experiments/wardrobe-curation/report.md`: all 57 catalog records, individual
  baseline status, failure reasons and remaining acceptance gates.
- `experiments/wardrobe-review/summary.json`: all 63 trials, input/output hashes,
  source/model versions, stage timings and current visual decisions.
- `experiments/wardrobe-review/comparisons.html`: local original/reference/output
  triptychs and concrete review notes, without external scripts or image hosting.
- `experiments/wardrobe-neutral/inputs/*-review.json`: explicit background-mask
  review. Hanger/tag-contaminated and clipped masks are rejected before retesting.
- `experiments/wardrobe-step-diagnostic/white-tee-20-recovered/comparison.html`:
  actual original/reference/10-step/20-step comparison, review, input-hash checks
  and measured stage timings. No quality approval or speed claim is inferred.

## Result UI and security

The comparison retains identical image framing, thin slider, side-by-side mode,
540 px desktop limit and existing palette. A compact information row shows actual
dimensions and measured server duration, without calling generation a quality pass.
Inspect details can show the normalized uploaded garment associated with that
specific completed result. It is a private owner-authorized asset; old results
without the new field remain usable. Missing references have an explicit state.
New catalog submissions include their stable product ID, and the API validates
the actual uploaded bytes, category and photo type against that record.

## Verification status

Reports, images, ratings and exact current counts are in the generated evaluation
report, not inferred from this document. Twenty approvals have **not** been reached.
The publication manifest stays staged and existing discovery records remain visible
with accurate unreviewed status until the acceptance gate is met. No garment source
or user data was deleted. Publishing refuses the shortfall. Existing favorites and
source records remain intact; approved-image hashes are rechecked before use.

Frontend production build passed. The earlier verification passed 691 Python tests,
18 browser regressions and a separate live browser test of two saved real results.
The live check verified exact private download hashes, anonymous denial, image
refresh, garment references, slider interaction and mobile/desktop layout without
submitting duplicate inference. An additional final regression run includes the
artifact-resume, failed-job-report and stale-review checks; its result is recorded
in the implementation status once it completes.

Latest recorded verification: **722 Python tests passed**, then **63 focused
tests passed** after final audit/recovery guards, and **90 focused tests passed**
after adding review-ledger regressions. Ruff and the 183-module production
frontend build passed. The combined comparison, fashion catalog, wardrobe quality
and saved-real-output browser run passed **17/17** checks. This includes actual
private image downloads and layout interactions; it does not certify garment fit.
The ledger tests reject incomplete/stale reviews, retain failed attempts alongside
retries and prevent repeated directory arguments from counting a trial twice.
Four additional benchmark tests verify that audit downloads do not inflate
generation timing, exactly 30 seconds fails the strict target, saved runs cannot
be overwritten, and failed requests never trigger duplicate inference. A further
live browser test passed after restarting the local app, reading the existing
private results and checking exact downloads without submitting new inference.

All 60 completed outputs remain local. Six older generated cases have missing
parser/conditioning audits after their Colab runtimes expired; those checks remain
unverified. Another inference cannot replace those missing historical artifacts.
On 28 October the local app and databases were restarted after an interruption.
The notebook helper reconnected to the existing notebook, but the previous T4 and
worker URL had expired. Automatic recovery independently verified the replacement
T4, restored the worker, reached real model readiness and completed the new
20-step diagnostic. No user prompt, runtime reset or local GPU was needed in
this recovery. A healthy local app alone is not evidence of available GPU inference.

Suggested commit once verification is complete:
`Add evidence-gated wardrobe curation and private garment comparison details`

# Wardrobe curation — 27 October 2026

This is an ongoing evaluation, not a claim that twenty garments are approved.
No product records, source assets, favorites, personal photos or results are deleted.

## Audit and stages

1. Audit the 57 locally available catalog references, actual decoder, source bytes,
   categories, pinned worker and private API. Preserve a baseline and source sheets.
2. Test 28 individually selected candidates against a fixed studio photograph and
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

The complete first-person baseline now covers all 28 candidates: 27 generated
images and one connection failure before a remote event was acknowledged.
Fifteen controlled background-only trials produced additional images, including
two second-person tests. All 42 generated images were inspected at full resolution.
Two single studio cases look plausible (green polo and teal shirt), but both fail
on the mirror person with sleeve/shoulder artifacts and altered hems. Therefore
**zero garments currently pass the complete two-person approval contract**.

Measured end-to-end times span **26.426–36.560 seconds**; 18 of the 42 generated
cases were strictly below 30 seconds. Faster generation is not a quality pass.
Shorts/skirt trials can retain jeans or invent split garments even after the
reference background is removed. Fine prints, lettering, cuffs and buttons are
often lost. These are observed model/reference limitations, not reasons to lower
the acceptance threshold or label every supported category reliable.

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
.venv/Scripts/python.exe -m scripts.curate_wardrobe report
.venv/Scripts/python.exe -m scripts.report_wardrobe_trials
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
The bridge saves a completed reply before refreshing tool discovery, and allows
240 seconds for a recovery cell that supervises setup for up to 180 seconds.
Discovery and browser-connection calls retain short bounded timeouts.
Discovery timeout no longer terminates a live helper and rotates its socket token;
it keeps the existing browser connection and retries discovery with backoff.

Experiment inputs/results stay in ignored `experiments/wardrobe-curation/` and
`experiments/wardrobe-neutral/`. Original catalog metadata remains in
`data/catalog/garments-v2.json`; reviewed candidates and publication policy have
separate versioned manifests. `publish` refuses a shortfall and writes an archival
snapshot before selecting the twenty passing items. Source or metadata changes
invalidate approval; there is no manual "approve HTTP 200" switch.

Private review outputs:

- `experiments/wardrobe-curation/report.md`: all 57 catalog records, individual
  baseline status, failure reasons and remaining acceptance gates.
- `experiments/wardrobe-review/summary.json`: all 43 trials, input/output hashes,
  source/model versions, stage timings and current visual decisions.
- `experiments/wardrobe-review/comparisons.html`: local original/reference/output
  triptychs and concrete review notes, without external scripts or image hosting.
- `experiments/wardrobe-neutral/inputs/*-review.json`: explicit background-mask
  review. Hanger/tag-contaminated and clipped masks are rejected before retesting.

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

Final local verification on 27 October: **701 Python tests passed**, followed by
**25 focused tests passed** after the final helper changes. Ruff, Prettier and the
183-module production frontend build passed. A combined browser run exposed two
test-session races; after waiting for real refresh rotation and second-tab
bootstrap, all **11 comparison tests passed**. Catalog/private-result checks also
passed (including the opt-in live saved-output browser check). No session security
or inference quality threshold was weakened to obtain these results.

The current Colab tab was reattached through the updated helper. It reports a new
T4 runtime with no previous project directory; safe automatic restoration is in
progress. All 42 completed images remain local. The last two mirror-case parser
audits were not retrieved before the old runtime disappeared and cannot be claimed
as verified. Another inference is not a substitute for those missing old artifacts.

Suggested commit once verification is complete:
`Add evidence-gated wardrobe curation and private garment comparison details`

# Reported blouse regression

This folder retains the actual user's input pair and controlled FASHN VTON 1.5
experiments. Generated files are evidence, not application fallback images.

- Original job: `9358ff94-2e51-4f55-8518-7e2bfdd8a4fa`.
- Original run: `0f5b8261-75ed-49a7-9a71-d036367273d0`.
- Person SHA256: `fd47aaaf6f46ab59ea9df9f2858d624044ce3bc3e745523ff578fd426cdf10fa`.
- Garment SHA256: `182917cd3a6380ffb7994bdac0e7cce8d197af4b2ae344d98657e85dcffff96d`.
- Source: `7c0f10af3f91ad4048fe9729c470a13ef905d25a`.
- Weights: `7720683168567eb5a2a4c67f15116c6e29c83ded`.
- Baseline: T4, FP16, 504 × 756, guidance 1.5, seed 42, flat-lay,
  segmentation-free, JPEG95 transport, 10 steps. All inference is on private Colab.

## Findings

The actual upload and `blouse` → `tops` mapping are correct. The unwanted white
fabric exists in raw model output before compositing. The official flat-lay path
retains the photograph's background. In this case neutralizing that background,
while retaining the detected fabric, removes the invented white layer. This is
evidence for a conditioning problem; it is not proof of general garment fidelity.

| Experiment | Change relative to comparison | End-to-end seconds | Visual finding |
|---|---|---:|---|
| baseline | Reported 10-step failure | See original diagnostics | White sleeves and white waist layer |
| steps20 | Baseline: only 10 → 20 steps | 40.373 | White layers remain; reject |
| framed20 | steps20: crop empty reference margins | 36.664 | White layers remain; reject; not used in production |
| masked20 | steps20: official person masking enabled | 39.395 | White fabric remains; reject |
| masked-neutral20 | masked20: reference background becomes neutral 127 | 37.217 | White layer removed in raw output; cropped hem exposes midriff; existing coverage gate rejects final |
| neutral20 | Planned mask-free neutral reference | No inference | Worker expired before an event was created; not a model result |
| reference-correction20 | steps20: integrated reference-background correction | 40.302 | No white layer; crop coverage gate rejected the run before the later reference-aware compositor change |
| app-correction10 | Normal app settings, integrated reference and compositor fixes | 31.901 | White layer removed; protected regions exact; fine fabric detail softened and small boundary steps remain |
| native-correction10 | app-correction10: only resolution profile to 576 × 864 | 33.987 | Better flutter sleeve/eyelet appearance; smocking softened; body/hem length not identical to reference proportions |
| app-native-fullparse10 | Final native profile plus full-canvas preservation parsing, through the real app | 31.319 | No invented white layer; smoother hair/arm boundaries, dark flutter sleeves; smocking and hem proportions remain approximate |

For masked20, 60.468% of the eroded, unprotected generated clothing region was
pale, versus 0.710% of the reference fabric. For masked-neutral20 that generated
fraction fell to 0.112%. These are diagnostic pixel statistics, not probabilities
or quality scores. The garment's smocking and sleeve construction still need
visual inspection at full resolution. A successful request alone is insufficient.

## Current implementation

`ml/vton/garment_reference.py` handles only confidently parsed dark flat-lay tops
against a plain pale backdrop. It changes non-fabric pixels to the model's neutral
value; it does not crop, resize or recolor the fabric. Worn references, other
categories, ambiguous backgrounds and incomplete masks keep their original path.
Photographed grey shadows are not counted as missing dark fabric.

`ml/vton/garment_fidelity.py` rejects a large invented pale clothing component
for a uniformly dark reference. It abstains on white/multicolored references and
does not certify the sleeve, neckline, texture or identity. The worker saves
actual conditioning, raw output, parsing and diagnostics for inspection.

The coverage check now distinguishes a confidently segmented, geometrically
short flat-lay bodice from a long garment. It permits at most 30% newly exposed
torso in the lower 40% of the old top, retains the original 20% limit for other
skin and caps total exposure at 40%. Arm/leg distortions remain rejected. This is
a conservative heuristic, not proof of the appearance of previously hidden skin.
All generated skin is identified in diagnostics. Background seams exposed by
shorter sleeves receive bounded blending only into the same adjacent class.

The native-resolution comparison improves sleeve construction and avoids the
white-layer defect. The profile is retained for quality, with its measured
34-second latency explicitly recorded. A separate parser-only Colab test showed
that interpolating logits to the final image before classification avoids the
stepped edges caused by nearest-neighbour upscaling of a smaller label map. The
worker now uses that full-output-resolution preservation mask; official model
conditioning and image dimensions remain unchanged.

## Reproduce

With the existing private Colab worker genuinely ready, run from repository root
(choose a fresh output directory; the script refuses to overwrite earlier runs):

```powershell
.venv/Scripts/python.exe scripts/benchmark_online_vton.py --person experiments/blouse-fidelity/baseline/personInput.bin --garment experiments/blouse-fidelity/baseline/garmentInput.bin --category blouse --photo-type flat-lay --steps 20 --input-encoding jpeg95 --output experiments/blouse-fidelity/reference-correction20
.venv/Scripts/python.exe scripts/retrieve_online_audit.py experiments/blouse-fidelity/reference-correction20
```

The retrieval command only recovers saved artifacts; it never starts inference.
If a run times out after receiving an event ID, recover that event rather than
submitting the same generation again. Compare input hashes, actual conditioning,
raw/final images and masks; examine the neck, both sleeves, hem, hair and bag.

Local regression checks (CPU only):

```powershell
.venv/Scripts/python.exe -m pytest tests/test_garment_reference.py tests/test_dark_garment_fidelity.py tests/test_vton_input_audit.py tests/test_online_vton.py tests/test_online_composite.py tests/test_colab_runtime.py tests/test_manual_colab_deploy.py -q
```

24 October continuation: 637 CPU tests passed, 3 integration tests excluded.
The actual `app-correction10` job passed a live browser check including refresh,
both comparison modes, download and a simulated health-network interruption.
Its `visual-review.json` records remaining detail/edge limitations. Final native
profile and parsing changes were subsequently verified in real app job
`f5b254bc-0660-44e0-a0c1-e2689c67cd28` after the existing Colab recovered.
All actual raw output, masks, conditioning and diagnostics were recovered locally.
`app-native-fullparse10/visual-review.json` records full-resolution review and
remaining texture limitations. The live browser test passed for this job,
including refresh, comparison modes, download and a simulated health interruption.

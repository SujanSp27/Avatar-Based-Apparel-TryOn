# Online inference performance work - 20 October 2026

The current acceptance target is **a visually correct fresh result within 30
seconds**, revised by the user on 20 October. Earlier targets and individual
timings below remain historical evidence. Fresh native-resolution 15-step tests
now take 22.252-26.443 seconds, but garment quality remains under review. Timing
alone is not acceptance and these observations are not a service guarantee.

Fresh generation has improved from **292.278 seconds to 54.583 seconds** for the
reviewed native-resolution striped-shirt example. A reduced-resolution experiment
finished in **14.914 seconds**, but its sleeve and hem artifacts fail the visual
acceptance criteria. **Acceptable try-on within 30 seconds is not yet verified.**

All model inference below ran on the user's existing Colab Tesla T4. Person and
garment photos remain restricted to that Colab worker; permission to use free
resources does not authorize uploading them to a public Hugging Face demo. No
local GPU, new training, pasted garment overlay or cached generated result was used.

## Recorded results

Each row links to the saved benchmark. Times include a fresh image generation;
end-to-end time also includes preprocessing, transport and result retrieval. These
are individual observations, not latency percentiles or a service guarantee.

| Profile | Steps | Model time | End-to-end time | Visual assessment |
|---|---:|---:|---:|---|
| [BF16, native 576 x 864](../experiments/online-runs/striped-20/benchmark.json) | 20 | 280.628s | 292.278s | Rejected: jagged hem/trouser transition and simplified shoulder/collar boundaries |
| [FP16, native 576 x 864](../experiments/online-runs/striped-fp16-20/benchmark.json) | 20 | 46.538s | 54.583s | Improved controlled example: no visible old-shirt fragments, continuous hem and aligned sleeves; simplified folds and imperfect collar/pattern proportions remain |
| [FP16, reduced 384 x 576](../experiments/online-runs/striped-fast-10/benchmark.json) | 10 | 9.868s | 20.186s | Rejected: artificial upper-arm transitions and exposed strip below hem |
| [FP16, reduced 384 x 576](../experiments/online-runs/striped-fast-15/benchmark.json) | 15 | 10.039s | 20.725s | Rejected: artificial upper-arm transitions and exposed strip below hem |
| [FP16, upper-body crop, 384 x 576](../experiments/online-runs/striped-crop-fast-10/benchmark.json) | 10 | 6.750s | 14.914s | Rejected: visible beige/white hem remnants and unnatural sleeve/arm boundaries |
| [FP16, upper-body crop, 384 x 576](../experiments/online-runs/striped-crop-fast-15/benchmark.json) | 15 | 11.477s | 22.920s | Rejected: visible beige/white hem remnants and unnatural sleeve/arm boundaries |
| [FP16, native, guidance 1.0](../experiments/online-runs/striped-native-cfg1-10/benchmark.json) | 10 | 13.464s | 21.274s | Rejected: abrupt neck skin transition and imperfect hem |
| [FP16, native, guidance 1.0, official clothing mask](../experiments/online-runs/striped-native-masked-10/benchmark.json) | 10 | 12.431s | 19.627s | Rejected: mismatched exposed arm skin and generated trouser patch below hem |
| [FP16, native, guidance 1.0, lossless patch transport](../experiments/online-runs/striped-native-patch-10/benchmark.json) | 10 | 11.764s | 22.377s | Identical decoded pixels to the earlier striped guidance-1.0 result; same rejected boundaries |
| [Second person, graphic T-shirt, native guidance 1.0](../experiments/online-runs/rhude-native-patch-10/benchmark.json) | 10 | 10.288s | 18.644s | Rejected: clipped hem, exposed shoulder strip, minor graphic distortion |
| [Dress, native guidance 1.0](../experiments/online-runs/dress-native-cfg1-10/benchmark.json) | 10 | 13.325s | 35.592s | Full-body validation passed; rejected for artificial newly exposed legs, sleeve transitions and background fragments |
| [Second person, revised hem/shoulder boundaries](../experiments/online-runs/rhude-native-boundary-10/benchmark.json) | 10 | 13.181s | 31.078s | Continuous hem with no original-shirt fragments; minor shoulder-edge artifacts and graphic distortion remain |
| [Striped, JPEG95 conditioning](../experiments/online-runs/striped-native-jpeg-20/benchmark.json) | 20 | 22.600s | 29.810s | Rejected: skin colour profile and hard neckline transition |
| [Striped, corrected sRGB colours](../experiments/online-runs/striped-native-color-20/benchmark.json) | 20 | 19.873s | 25.318s | Skin tones corrected; hard neckline and denim band still rejected |
| [Striped, semantic transition blend](../experiments/online-runs/striped-native-transition-20/benchmark.json) | 20 | 22.590s | 30.005s | Neck/hem bands improved; collar corners and simplified fabric remain |
| [Striped, semantic transition blend](../experiments/online-runs/striped-native-transition-15/benchmark.json) | 15 | 16.194s | 23.230s | Similar to 20 steps; strict visual acceptance not established |
| [Graphic shirt, second person](../experiments/online-runs/rhude-native-transition-15/benchmark.json) | 15 | 16.624s | 22.252s | Recognizable graphic and continuous hem; shoulder outline rejected |
| [Tiered skirt](../experiments/online-runs/trouser-native-transition-15/benchmark.json) | 15 | 16.689s | 23.318s | Rejected waist seam/detail; fixture was mislabeled as trousers but is a skirt |
| [Dress](../experiments/online-runs/dress-native-transition-15/benchmark.json) | 15 | 16.988s | 24.340s | Rejected: large newly exposed skin/background area |
| [Graphic shirt, expanded contour experiment](../experiments/online-runs/rhude-native-contour-15/benchmark.json) | 15 | 18.525s | 26.443s | Rejected: rough shoulder contour; this expansion was reverted |

The native FP16 assessment is recorded in
[`visual-review.json`](../experiments/online-runs/striped-fp16-20/visual-review.json).
The reduced-resolution assessments above come from inspecting their saved
`tryon-2d.png` files. Their benchmark JSON still says `pending inspection`; this
document records the subsequent rejection. The original face remains recognizable
in these images, but face preservation alone does not establish acceptable fitting.
One striped-shirt example does not validate other people, clothing categories or
lighting conditions. Both guidance-1.0 experiments have saved raw model outputs,
source/target parsing labels, edit masks and `visual-review.json` assessments.
The 19.627-second image meets the timing target but fails the combined acceptance
criterion. An additional local skin-colour correction was rejected for visible
seams and was not deployed.

## Implementation and limits

The pinned FASHN VTON 1.5 source is
`7c0f10af3f91ad4048fe9729c470a13ef905d25a`; model revision is
`7720683168567eb5a2a4c67f15116c6e29c83ded`. Its upstream pipeline selects BF16 via
`torch.cuda.is_bf16_supported()`, which includes emulation by default. Explicit FP16
avoids that dtype selection on T4. The completed FP16 reports record the effective
dtype, GPU, Torch/CUDA versions and peak allocated GPU memory (3028 MB for the native
run; 2527.1 MB for these reduced-resolution runs).

The native comparison also includes the revised semantic compositor, so its visual
improvement cannot be attributed to precision alone. The compositor allows a bounded,
connected top extension over the waistband while protecting the head, hands and
unrelated lower-body pixels. Raw output and semantic labels are retained for review.
Reported exact preservation outside the edit mask is a pixel-level check, not proof
that semantic labels or clothing boundaries are correct.

`ml/vton/checked_sampler.py` retains the pinned Euler update and rejects non-finite
predictions, guidance and updated states before clamping or image conversion.
CPU tests cover NaN/Inf predictions, guidance overflow, final-state overflow and
equivalence to the upstream algorithm. Reduced resolution, crops and fewer than
the upstream recommended fast preset of 20 steps remain experimental; their current
images must not be presented as a validated fast-quality preset.

`config/online-worker.json` now persists the reviewed FP16/native profile with
guidance 1.5, no crop, segmentation-free conditioning and the conditional-branch
shortcut disabled. Automatic recovery validates this profile and seeds the Colab
configuration only if it is absent; it preserves existing runtime settings and
running work. Guidance 1.0 and skipping unused unconditional predictions have now
been measured on native-resolution images above, but their visual defects prevent
promotion to the default profile.

Lossless transport is implemented for sanitized inputs and generated output. Inputs
use WebP only when smaller than PNG; the worker returns lossless WebP, and the API
validates response type, declared/actual format, dimensions and payload size before
saving a PNG. The local CPU-only
[`lossless-transport.json`](../experiments/lossless-transport.json) check measured
25.23% fewer bytes for the person image, 3.33% for the garment and 23.81% for the
reviewed result, with identical decoded pixels. These are serialization measurements,
not an isolated end-to-end speed improvement. The two native guidance-1.0 runs
used this transport; they also changed guidance and step count, so those timings
cannot attribute speed gains to transport alone.

The latest transport sends only the changed pixels of the **actual generated
image**, with lossless RGBA and validated canvas coordinates. It reconstructs that
image exactly on the API; it does not paste the uploaded garment. CPU round-trip
checks are recorded in [`patch-transport.json`](../experiments/patch-transport.json).
The live striped test returned 75,346 bytes instead of 290,476 bytes and reproduced
the previous output pixel-for-pixel. Network variation still increased total time
on that particular run. The second-person test returned 116,070 bytes and took
18.644 seconds, but its hem failed visual review.

The compositor's revised hem rule retains the complete connected generated top
when its extension over the source waistband is within 40% of the original
clothing height. It rejects excessive extensions instead of clipping the hem.
The initial 35% rule rejected a sloping-waist corner in the
[first hem test](../experiments/online-runs/rhude-native-hem-10/benchmark.json).
Raw output and masks were recovered and inspected before revising that bound.
The follow-up above has a continuous hem. Narrow source-arm / generated-background
gaps immediately beside generated clothing can use projected interior garment
pixels; broader limb changes and generated bare skin are excluded. This does not
erase an arm to conceal a model error. Face, hands and unrelated lower-body
pixels remain unchanged. Residual shoulder contour artifacts still fail the full
acceptance criterion.

`ONLINE_VTON_INPUT_ENCODING=jpeg95` is an **optional experiment**, not the default.
It uses quality-95 JPEG without chroma subsampling when smaller than lossless
transport. The second-person pair falls from 1,155,144 to 400,460 uploaded bytes.
Conditioning pixels change, so image quality must be re-evaluated. The generated
changed-pixel patch is applied to the original local PNG: tests prove exact face
and background preservation outside that patch. Legacy full-frame responses are
rejected with this setting. The live comparisons above now use this encoding.
They measure the complete request; quality remains image-dependent.

The supplied studio JPEG embeds a ProPhoto RGB profile. Stripping it before
converting its pixels to sRGB caused a visible skin-tone error even when face
pixels were preserved numerically. `normalized_image` now performs the colour
conversion before metadata removal and retains transparency. Three regression
tests cover colour conversion, alpha and invalid profiles. Earlier studio-image
benchmarks predate this correction.

The semantic compositor now blends newly exposed skin/denim into a bounded,
connected region of the same semantic class. It leaves original face/hair/hands,
the neural fabric interior and distant pixels unchanged. This removes the hard
band where a lower collar or shorter hem crossed the source clothing boundary;
it does not repair arbitrary generated anatomy. Results exposing skin over more
than 20% of the replaced clothing region are rejected with
`coverage_change_too_large`. The long-to-short dress example triggers that rule;
an error is not counted as a successful fast generation.

Worker diagnostics now separate preprocessing, generation and postprocessing/saving.
Transport diagnostics include normalized/uploaded/downloaded image byte counts and
preparation, encoding, request/stream and saving times. Those counters make future
comparisons attributable; they do not retroactively add missing stage timings to the
older benchmarks above. The two native guidance-1.0 reports contain these timings.

`scripts/benchmark_online_vton.py` records input hashes, remote event IDs, actual
timings and fresh output. Use a new output directory for each experiment. Recover
an existing event instead of resubmitting a generation after a transport timeout.
Only pose/parser results are cached; every benchmark image is generated anew.

Official dress and trousers fixtures are prepared under `data/raw/fashn-samples/`,
with source revisions and hashes in its manifest. Saved results above do not
establish their inference quality or support for every kind of dress. Repeat timing,
broader category validation and acceptable quality within 30 seconds remain open.
The first [dress test](../experiments/online-runs/dress-native-masked-10/benchmark.json)
was rejected before generation by a whole-image lower-body area threshold, despite
a visibly full-body input. `lower_body_visible` now measures relative to person
area and extent, with background-padding regression tests. A new live dress test
passed this input check, but its generated image failed visual review as recorded
above. Resolving validation does not establish acceptable dress generation.

Latest broad local verification: **447 CPU-only Python tests passed with zero failures or
errors** in `experiments/online-profile-transport-tests.xml`, covering worker profile
validation/recovery, lossless image round trips, response validation and sampler
safeguards. The earlier `experiments/online-recovery-hem-tests.xml` records 351 passed
and 2 integration tests deselected. Tests validate transport, recovery and mask
behavior, not photographic realism or live deployment. Runtime identity
checks prevent recovery from silently installing or launching work on a different
Colab machine. A live allocated GPU and authenticated notebook remain prerequisites.

References: [pinned FASHN pipeline](https://github.com/fashn-AI/fashn-vton-1.5/blob/7c0f10af3f91ad4048fe9729c470a13ef905d25a/src/fashn_vton/pipeline.py),
[PyTorch BF16 support API](https://docs.pytorch.org/docs/2.14/generated/torch.cuda.is_bf16_supported.html).

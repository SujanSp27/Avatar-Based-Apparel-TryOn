# Online inference performance work

The last completed baseline is a fresh FASHN VTON 1.5 generation on a Colab Tesla
T4 at native 576 × 864 resolution, 20 sampling steps and seed 42. It took 280.628
seconds in the model pipeline and 292.278 seconds end to end. Its image and report
are in `experiments/online-runs/striped-20/`. It does not meet the ten-second target.

The pinned upstream pipeline chooses BF16 using `torch.cuda.is_bf16_supported()`.
That call includes emulation by default, which can select BF16 on T4. The first
controlled optimization is explicit FP16: load the weights in that dtype and keep
the same checkpoint, resolution, seed, inputs, CFG strength and 20 steps. No new
training, image overlay, cached generated output, or local GPU is used.

The checked sampler in `ml/vton/checked_sampler.py` preserves the pinned upstream
Euler update. It rejects non-finite predictions, guidance and updated states before
clamping or image conversion. CPU tests cover prediction NaN/Inf, guidance overflow,
final-state overflow and equivalence to the original algorithm. A finite image is
not evidence of acceptable garment quality: each real result still needs review.

`scripts/deploy_online_colab.py worker --precision fp16` selects the experimental
profile only when starting a stopped worker. The worker records Torch/CUDA versions,
GPU capability, effective dtype, peak allocated memory and actual timings. It also
records an active-generation marker and saves raw output before compositing gates.
The upstream profile remains available; FP16 is not yet the validated default.

`scripts/benchmark_online_vton.py --steps 20 --output <new-directory>` records fresh
results, input hashes and remote event IDs. Never reuse an output directory or
resubmit an event to recover a timed-out request. The first FP16 comparison must
finish and be visually inspected before testing fewer steps. Ten/fifteen steps are
below the upstream recommended fast preset of twenty and need separate evaluation.

Official dress and trousers examples are prepared under `data/raw/fashn-samples/`,
with source revisions and hashes in its manifest. They are public example inputs,
not model-generated substitutions for user photos. Their inference and visual
acceptance are not yet verified.

Verification on 17 October: 351 Python tests passed, 2 integration tests deselected;
no local CUDA was used. See `experiments/online-recovery-hem-tests.xml`. Live FP16
timing and category acceptance remain pending until the restored Colab worker is
ready. Runtime identity is checked before setup writes or process launches; a
changed notebook connection cannot silently redirect restoration.

The semantic compositor now allows a generated top to overlap a bounded waistband
area instead of clipping every pixel against the original trouser boundary. It
requires local hem proximity and connectivity after applying that bound; hands,
head and unrelated trouser pixels remain protected. This change has synthetic-mask
regression coverage but still needs photographic validation. Future comparisons
must distinguish model inference timing from this separate compositing change.
The worker saves raw output and source/target label maps for that review.

References: [pinned FASHN pipeline](https://github.com/fashn-AI/fashn-vton-1.5/blob/7c0f10af3f91ad4048fe9729c470a13ef905d25a/src/fashn_vton/pipeline.py),
[PyTorch BF16 support API](https://docs.pytorch.org/docs/2.14/generated/torch.cuda.is_bf16_supported.html).

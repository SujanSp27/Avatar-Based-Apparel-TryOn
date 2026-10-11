# Pretrained 2D try-on: implementation and verification

Updated 11 October 2026. The application now routes 2D requests to CatVTON, conditioned on
the uploaded person, uploaded garment and a semantic clothing replacement mask. The previous
geometric overlay is disconnected from the application API. **Real CatVTON inference completed,
but both reviewed results were rejected because they lost all uploaded cream stripes.**
The natural-fitting and garment-fidelity acceptance criterion remains unmet. Further model
and preprocessing experiments are pending review; successful generation alone is insufficient.

## Audit of the reported result

`ml/tryon2d/service.py` generated the old result with a landmark-derived four-corner
`warpPerspective` and image compositing. There was no pretrained garment deformation or
image-synthesis model in that path. Its independent resizing/pasting explains the flat
fabric, incorrect sleeve shapes, neckline holes and visible original beige shirt. The
module is retained as explicitly labelled debug code; `backend/app/photo_tryon.py` imports
`ml/vton/service.py` instead. Model failure never falls back to that overlay.

The reported case is retained locally as run `9658bcca-8a2b-4a88-a134-cea3ff8739dd`: a
1000 by 1500 person image and 600 by 660 striped garment image. Their hashes match the local
studio-person and synthetic striped-garment fixtures. Inputs and outputs remain in ignored
local storage. A synthetic garment is a software regression input, not proof of general
performance on photographs of retail products.

An initial lightweight DM-VTON integration loaded real official warp/generator checkpoints
and completed CPU inference in 24.901 seconds on this case. Visual inspection rejected it:
the neckline turned pink, sleeves contained skin-like holes, and details blurred. This is
evidence that a real model can still fail the task. Its 192 by 256 output is not the selected
application backend and is not described as an accepted fix.

The rejected output and visual findings are recorded in
`experiments/dmvton-rejected-report.json`; `visualAcceptance` is explicitly `rejected`.

CatVTON then completed the exact reported case on CUDA in **493.331 seconds**, including
model loading and parsing, using 50 DDIM steps, guidance 2.5 and seed 42. Its neckline,
sleeves and folds looked more natural, and the semantic compositor retained original protected
pixels, but the result was a plain pale teal shirt. **None of the uploaded cream stripes
survived.** This is a failed garment-fidelity result, not an accepted fix. The report is
`experiments/catvton-initial-report.json`; native and final PNGs are under
`experiments/runs/catvton-initial/reported-striped-shirt/`. That run preceded the newer
mask dilation and cream-fabric segmentation correction described below.

A second run applied the corrected segmentation, dilated replacement mask, guidance 5 and
the float32 convolution arithmetic workaround. It completed in **315.413 seconds**; its
50-step denoising portion took approximately 227 seconds versus 397 seconds initially.
Visual inspection again rejected both native and final outputs: the shirt was darker teal
but still lacked every cream stripe, with white shoulder outlines and a collar compositing
seam. `experiments/catvton-guidance5-report.json` records this result. These implementation
changes improve execution but have not solved garment fidelity or all boundary artifacts.

## Selected model and pinned provenance

| Component | Official source | Pinned revision |
|---|---|---|
| CatVTON inference source | [Zheng-Chong/CatVTON](https://github.com/Zheng-Chong/CatVTON/tree/999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e) | `999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e` |
| Garment attention weights | [zhengchong/CatVTON](https://huggingface.co/zhengchong/CatVTON/tree/2969fcf85fe62f2036605716f0b56f0b81d01d79/vitonhd-16k-512) | `2969fcf85fe62f2036605716f0b56f0b81d01d79`, `vitonhd-16k-512` |
| Inpainting UNet, scheduler and checker | [Stable Diffusion v1.5 inpainting](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-inpainting/tree/8a4288a76071f7280aedbdb3253bdb9e9d5d84bb) | `8a4288a76071f7280aedbdb3253bdb9e9d5d84bb` |
| VAE | [stabilityai/sd-vae-ft-mse](https://huggingface.co/stabilityai/sd-vae-ft-mse/tree/31f26fdeee1355a5c34592e401dd41e45d25a493) | `31f26fdeee1355a5c34592e401dd41e45d25a493` |
| FASHN parsing source | [fashn-AI/fashn-human-parser](https://github.com/fashn-AI/fashn-human-parser/tree/f2771f2fb8655349e87e2869bbde7ace0bd06f2c) | `f2771f2fb8655349e87e2869bbde7ace0bd06f2c` |
| SegFormer-B4 parser weights | [fashn-ai/fashn-human-parser](https://huggingface.co/fashn-ai/fashn-human-parser/tree/1f80c34dbab321c5730dda5c3fea279fd3e97498) | `1f80c34dbab321c5730dda5c3fea279fd3e97498` |

Checkpoint SHA-256 values are pinned in `ml/vton/catvton.py`, `ml/vton/parsing.py` and the
download scripts. Download manifests retain source URLs, revisions, lengths and checksums.
The adapter verifies hashes, loads safetensors locally and strictly loads the learned
attention state. No model download or remote inference occurs during an upload request.

Only package-relative imports change in the vendored CatVTON source. The application
adapter reuses its denoising pipeline, with sequential classifier-free guidance to lower
peak VRAM, FP16 CUDA loading, VAE slicing, numeric checks and the official image safety
checker on CPU. The checker runs for every output and rejects rather than substituting a
static image. The custom CatVTON attention processors are retained; generic attention
slicing must not replace them. FASHN preprocessing reuses the official OpenCV `INTER_AREA`
resize to 384 by 576 and ImageNet normalization.

The optional official `mix-48k-1024` attention checkpoint is also downloaded and hash-verified,
with the same source/repository revisions: 198,303,368 bytes, SHA-256
`a1fc093f1b6744623079e6f4e7313411f524e388c4b7467df1e0e7f577cba23a`.
`scripts/download_vton_mix.py` writes a separate `mix-download-manifest.json` without changing
the baseline manifest. The [official application](https://raw.githubusercontent.com/Zheng-Chong/CatVTON/999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e/app.py)
uses this mixed checkpoint at 768 by 1024; the [paper's implementation details](https://arxiv.org/html/2407.15886v1)
distinguish it from the dataset-specific 384 by 512 evaluation models. It is an experimental
option here, not the selected application checkpoint or evidence of accepted output quality.

## Image and mask flow

1. Validate and detect the person; save the original image, person mask and pose diagnostics.
2. Run the pretrained human parser over the original pixels. Its 18 labels include face,
   hair, upper clothing, trousers, arms, hands, legs, feet and background. It does **not**
   predict separate neck, left-arm or right-arm labels.
3. Crop a portrait window containing the head and clothing, then aspect-preserving pad the
   person and semantic labels to 384 by 512. `ml/vton/masking.py` builds a white-edit mask
   covering the old shirt, sleeves, shoulders and neckline, with an eight-pixel elliptical
   context dilation. Protected head/hair/hands/lower-body classes constrain that dilation.
   The context reduces old-clothing leakage when the mask is downsampled into VAE latents;
   the inference window is never used as a rectangular replacement mask.
4. Segment the actual garment using transparency/plain-background segmentation or semantic
   parsing for worn garments. Plain-background thresholding now adapts to measured background
   noise, retaining cream stripes previously discarded near sleeve edges. Crop and
   aspect-preserving pad the garment; use a white background for model conditioning.
   `vton-garment-input.png` saves the exact conditioning image. The garment is never
   geometrically pasted as output.
5. Run CatVTON with the person, segmented garment and binary replacement mask. The configured
   inference uses 50 DDIM steps, guidance 2.5 and seed 42. The selected checkpoint is scoped
   to `t-shirt` and `shirt`; dress and trouser requests are rejected on this path.
6. Restore the neural result into the original coordinates. Semantic compositing sets full
   opacity on every predicted old-clothing pixel, avoiding blended remnants of beige fabric.
   Preserve original face, hair, exposed limbs, background and unrelated clothing pixels.
   A narrow adjacent bare-torso region can admit a generated collar transition.
7. Save the original/result PNGs, native inputs/output, parsing maps, replacement mask,
   preservation mask, alpha and provenance. Return their real local URLs only after export.

The current conservative preservation policy limits sleeve or hem extensions onto exposed
arms, background or lower clothing. It preserves identity but can constrain a different
garment silhouette. Parser errors at collars, thin hair or occluded sleeves can still cause
artifacts. Exact preservation of *predicted* protected pixels is a software invariant, not
proof that every anatomically protected pixel was classified correctly. Native 384 by 512
generation can lose stripe, logo and fabric detail when enlarged. No unconditional guarantee
of realistic fitting, material physics or accurate hidden geometry is made.

## Local environment and setup

The detected machine has Python 3.12, **torch 2.5.1+cu121**, torchvision 0.20.1+cu121,
an NVIDIA GTX 1650 with 4 GB VRAM, and 8 GB system RAM. CUDA tensor operations, checkpoint
loading and the initial 50-step CatVTON run were actually executed. Evidence is in
`experiments/vton-hardware-report.json` and `experiments/catvton-initial-report.json`.
Earlier 3D checks used CPU torch. The current environment is captured in
`requirements-vton-cuda.lock.txt`; `requirements.lock.txt` remains the earlier CPU record.
CPU float32 is supported by the adapter but is not validated as a practical alternative on
this 8 GB machine.

The installed GTX 1650/cuDNN FP16 convolution produced NaNs from finite inputs. The actual
first failing UNet layer is recorded in `experiments/vton-numerics.json`; the layer benchmark
in `experiments/vton-convolution-report.json` reproduced the failure even with deterministic
cuDNN. Native FP16 convolution with cuDNN disabled produced finite values and enabled the
initial complete run, but was slow. Float32 cuDNN convolution also produced finite values and
was faster in the measured layer. `ml/vton/precision.py` now applies float32 convolution
arithmetic only to the affected model instances, retaining FP16 resident weights and casting
results back to their input dtype. It leaves checkpoint parameters/aliases intact. Its focused
tests passed, and the guidance-5 run completed all 50 denoising steps with this workaround.
The measured run was faster, but its garment-fidelity and boundary reviews failed. A numeric
fix or speed improvement is not visual acceptance.

For a prepared project environment, the reproducible model provisioning commands are:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-vton.txt
.venv/Scripts/python.exe scripts/download_parser.py
.venv/Scripts/python.exe scripts/download_vton.py
```

`requirements-vton.txt` pins transformers 4.49.0, diffusers 0.29.2 and accelerate 0.31.0;
these dependencies are installed and `pip check` passes. It does not replace the existing
torch profile or install a second OpenCV package. The
Windows/Python 3.12 CUDA wheel can be streamed without pip's large in-memory download cache:

```powershell
.venv/Scripts/python.exe scripts/download_cuda_runtime.py
.venv/Scripts/python.exe -m pip install --no-cache-dir --no-deps --force-reinstall '.runtime/wheels/torch-2.5.1+cu121-cp312-cp312-win_amd64.whl'
```

The downloader checks the official wheel's SHA-256. The wheel is approximately 2.45 GB;
allow additional space for extraction. CatVTON's selected assets total approximately
2.86 GB, plus the 256 MB parser checkpoint. `VTON_ROOT` defaults to `assets/vton`, and
`VTON_DEVICE` defaults to `cuda`. `GET /api/health` reports `vton2d` readiness; file/readiness
checks do not establish successful model loading or visual quality. Low memory can still
produce an actionable inference failure. Requests are serialized to avoid concurrent models
competing for the same small GPU.

## Verification and acceptance

`experiments/runs/parser-validation/verification.json` records real checkpoint loading,
identical repeated parsing for the studio person and striped garment, and inspected semantic
boundaries. Parser/mask unit tests cover protected-pixel invariants and complete replacement
of predicted clothing. These are parsing/compositing results, not try-on acceptance.

`scripts/validate_pretrained_vton.py --all` runs the retained striped-shirt case, a different
garment, a different person, the shirt branch, and unsupported category checks. It records
actual timings, memory, input hashes, model provenance and failures. A `generated` result
requires separate visual review of neckline, shoulders, both sleeves, hem, old-shirt removal,
garment pattern, identity and background. A `pending human inspection` entry is not a pass.

Current verification checkpoint: the historical DM-VTON output and both reviewed CatVTON
outputs were visually rejected. CatVTON CUDA generation is demonstrated; accepted garment
fidelity, multi-case evaluation and live neural API/browser generation remain pending.
Earlier 9 October overlay results must not be counted as validation of this replacement.

The prior full Python suite passed **89 tests in 38.33 seconds**, with three upstream warnings;
the record is `experiments/vton-pytest-report.xml`. After the latest implementation changes,
**33 focused adapter/precision tests passed**. The expanded full suite remains pending.
Ruff and dependency consistency checks passed. The frontend production build and TypeScript
passed on 10 October: 382 transformed modules, 302-second Vite build, with a large-chunk
warning (`experiments/vton-ui-build-report.json`). Its source has not changed since that build.
Two non-inference browser tests passed for category scope and unavailable-model errors.
None of these tests establishes natural fitting or garment fidelity.
`scripts/validate_vton_api.py` is prepared to exercise the real reported input, generated
asset provenance, unchanged protected pixels, changed old-clothing pixels, independent size
recommendation and unsupported categories. The updated `scripts/validate_2d_api.py` checks
Auto/2D/strict-3D routing with a 900-second inference timeout and writes
`experiments/pretrained-2d-api-report.json`; its new live results are also pending.

The independent brand sizing engine remains unchanged. 2D responses contain no invented
measurements or recommended size. `/api/sizing/recommend` still uses supplied physical
measurements and actual versioned chart records; the image model does not receive brand,
size or fit preference as generation controls.
Actual independent sizing requests produced S and XXL for different supplied dimensions;
`experiments/vton-independent-size-report.json` records the inputs, chart provenance and
explanations. These are sizing-engine checks, not measurements recovered from a 2D image.

## Training and licensing

The user's latest request permits training if feasible. No new model has been trained.
There is no paired, consented person/garment/target-image training corpus or disjoint labelled
validation set in this repository. The available isolated uploads cannot support a credible
fitting model or establish generalization; training on them would not demonstrate the desired
fix. With 4 GB VRAM and 8 GB RAM, even inference requires careful memory handling, and no
feasible full training configuration has been established. A working, visually evaluated
pretrained baseline remains the immediate requirement before any targeted fine-tuning.

CatVTON code/checkpoints use [CC BY-NC-SA 4.0](https://github.com/Zheng-Chong/CatVTON/blob/999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e/LICENSE).
FASHN identifies its model as inheriting the [NVIDIA SegFormer license](https://github.com/NVlabs/SegFormer/blob/master/LICENSE),
whose use limitation covers research/evaluation purposes. The Stable Diffusion base and VAE
retain their respective upstream model terms. Vendored notices are retained. This selection
is a local research integration, not a commercially cleared deployment.

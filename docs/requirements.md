# Supported research scope

The user-authorized 2D path extends the original 3D specification. The UI now defaults to
`tryonMode=2d`. The API default remains `auto`: first attempt the controlled 3D path, then
use pretrained 2D generation for an allowlisted full-body/reconstruction failure. `3d`
keeps the strict full-body contract. Invalid files, multiple detected people and insufficient
visible anatomy still fail with an actionable error. Failure to load or run the neural
model must never silently invoke the old geometric garment overlay.

For **2D**, support is limited to a single clothed person with visible shoulders and torso,
and **T-shirts or shirts**. The selected CatVTON `vitonhd-16k-512` checkpoint is used only
for upper-body garments; dresses and trousers return `vton_category`. Person images require
at least 256 pixels on each side; 2D garment images allow 128 pixels per side. Prefer a clear
product image on a plain contrasting background, or transparent PNG. Human parsing can
extract a visible top from a worn garment image, but this remains harder than a clean
product image. Native diffusion input/output is 384 by 512 pixels before restoration into
the original image dimensions, so enlarged results cannot recover missing fine detail.

The model conditions on the actual uploaded garment and source person, with a semantic
mask covering the existing upper clothing. FASHN parsing identifies face, hair, arms,
hands, clothing, lower body and background. It has no separate neck or left/right arm
classes. Postprocessing preserves original pixels outside the semantic edit area; source
clothing pixels are fully replaced rather than blended back. This preservation depends on
segmentation accuracy. The revised mask reserves pose-guided space on the proximal upper arms
for short sleeves, and composition admits only model-generated clothing there. The correction
has been exercised on local CUDA and Colab T4. Significant generated shoulder/arm shrinkage
is rejected rather than hidden by erasing original skin. Long-sleeve changes and large
hem changes remain unvalidated; prefer short-sleeved product photographs.
Natural neckline, sleeve alignment, pattern retention and lack of old-shirt fragments
require visual inspection; neither mask tests nor successful inference prove realism.

The generated PNG and original-photo comparison are available when inference succeeds.
Body measurements, size recommendation and 3D mesh URLs remain null for 2D results.
Brand and fit are recorded, but fit preference is not a CatVTON conditioning input. The
independent sizing API continues to recommend from supplied measurements and versioned
brand charts. [Model setup and validation state](vton-model.md) record the current neural
pipeline's limitations; photorealistic or production-ready fitting is not yet established.

The following full-body, measurement and mesh requirements apply to **3D**:

Single adult, front-facing, standing upright, complete head and feet visible, arms slightly
separated from torso and legs uncrossed. Plain contrasting background, even lighting, fitted
clothing. JPEG/PNG/WebP, minimum 256 pixels on each side, maximum 20 megapixels/12 MB.
Use known height 120–220 cm; omitted height uses an explicitly disclosed 170 cm assumption.
Reject missing/low-visibility joints, multiple detected people, cropped feet/head, severe pose
deviation, blank foreground and unreadable images. Heuristics cannot guarantee detection of
all occlusion or multiple-person cases. Out-of-scope inputs must never be silently claimed valid.

Garments: one flat-lay T-shirt, shirt, dress or trouser on a plain contrasting background;
no hangers/mannequins/people, transparent PNG supported. Category supplied by user. Template
geometry and image texture approximate the garment; image pixels alone do not provide physical
dimensions. Optional length/width in cm override silhouette-derived proportions.

Brands: two explicitly synthetic, versioned demonstration brands (Atelier Demo, Everyday Demo),
sizes XS–XXL. They are test data, not retailer charts. Database APIs accept sourced real charts.
Chart intervals describe **body measurements**, cm; regular fit compares directly to intervals.
Tight/loose preference shifts the target by -2/+4 cm. Size score is a weighted distance, not a
probability. Out-of-chart recommendations are flagged; no fit guarantee.

Outputs: estimated height, shoulder width, chest, waist, hip, arm length, inseam, thigh;
OBJ/PLY/GLB body, garment and dressed GLB, preprocessing masks/crops/keypoints, body parameters,
front/side/back previews and interactive orbit/zoom/360 viewer. Coordinates: metres, Y up,
front +Z. Every result records provenance, chart version, uncertainty assumptions and timings.

Reconstruction: HMR2/SMPL is the selected optional research adapter; licensed SMPL assets are
not bundled. The working CPU baseline uses pretrained MediaPipe 3D pose and person segmentation
with a deterministic parametric surface. It is not SMPL/SMPL-X topology or learned body-shape
recovery, and cannot recover hidden depth, facial identity or body shape under loose clothes.
Derived circumferences and size recommendations are exploratory, not validated anthropometry.

Cloth: controlled template relaxation plus surface collision projection. Not a calibrated
material simulation; seams, layering, pockets, buttons and arbitrary pose cloth are out of scope.

Evaluation: mesh validity, silhouette IoU, pose reprojection error, MPJPE/P-MPJPE when ground
truth exists; measurement MAE/MAPE/RMSE; exact/adjacent/top-2 size accuracy; collision rate,
alignment/identity/texture/occlusion/artifact review; success/failure rate, latency, RAM/GPU.
Separate people and garments across train/validation/test. Augmentations of one photo remain
the same identity; synthetic fixtures are not human-accuracy validation.

Local research use: binds loopback; application uploads stay in local storage. The separate,
user-authorized Colab evaluation uses only the explicit regression-fixture allowlist.
No public deployment or multi-user authentication is included. Delete a run through the API
to remove its inputs and generated outputs. Admin writes can be protected by ADMIN_TOKEN.

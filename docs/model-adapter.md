# Body reconstruction: implemented and unavailable paths

## Verified implementation

`PersonPreprocessor` uses the actual MediaPipe Tasks `PoseLandmarker` API in `IMAGE` mode,
with the official Full float16 v1 `.task` checkpoint, three-person detection limit, and
segmentation output. It stores 33 normalized landmarks, 33 world landmarks, mask, bounding
box and normalized crop. Inference is deterministic for the checked sample and serialized
because a shared task instance is not used concurrently.

The public task returns pose and segmentation, **not body-surface shape parameters**.
See the [MediaPipe Python guide](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python).

`MediaPipeTemplateReconstructor` derives frontal widths from the segmented silhouette,
scales using supplied height, assumes torso depth ratios, and constructs a smooth union
of elliptical torso sections and limb/head primitives with marching cubes. The output is a
canonical A-pose, not the original camera pose. Body identity and unobserved anatomy are not
recovered. SMPL compatibility is explicitly `false` in `bodyParameters.json`; pose landmarks
are never mislabelled as SMPL rotations or beta coefficients.

Each mesh must be finite, closed, consistently wound, positive-volume and within supported
height bounds. The measurement service rejects merged torso/arm sections. OBJ, PLY and GLB
are exported only after validity checks. Measurements use actual mesh sections and landmarks;
the uncertain geometry they measure remains a major source of error. Circumference uncertainty
is a labelled heuristic, not a calibrated confidence interval. `confidence` is null.

## Selected research target: HMR2 / 4D-Humans

The [official HMR2 setup](https://github.com/shubham-goel/4D-Humans#installation-and-setup)
requires a separately downloaded neutral SMPL body model after registration. The file is absent
in this repository. No licensed asset was downloaded from an unofficial mirror or fabricated.

The upstream [demo](https://github.com/shubham-goel/4D-Humans/blob/main/demo.py) was inspected:
it uses `hmr2.models.load_hmr2`, `ViTDetDataset`, torch inference and predicted SMPL vertices.
Its suggested Python 3.10 research environment and Detectron2 stack were not represented as
working inside this Python 3.12 app. Installing those without the mandatory body model would
not make inference work.

`HumanReconstructor` / `BodyResult` define the boundary. `HMR2Reconstructor` is an explicit
availability gate, **not an implemented inference adapter**. Selecting `HUMAN_BACKEND=hmr2`
with strict `tryonMode=3d` returns 503, naming missing paths; even if paths are filled, the current adapter refuses to
claim validation. `hmr2Available` is false in health. Implementing and validating upstream
inference plus anatomical landmark conversion is still required before enabling it.

After the user's request to allow 2D when 3D is unavailable, `tryonMode=auto` may instead
call the pretrained 2D CatVTON service for supported 3D limitations. It records the original
reason and returns null meshes, measurements and sizing. This does not enable or claim HMR2
inference. `tryonMode=2d` calls that image model directly, with FASHN semantic parsing.
The former OpenCV garment overlay is no longer an application fallback. Missing neural
weights or failed inference return errors. See [2D model status](vton-model.md) for current
checkpoint provisioning and visual-validation limits.

PIFuHD was also examined as a non-SMPL alternative. Its official documentation recommends
at least 8 GB GPU memory; the local GPU has 4 GB. Its official checkpoint HEAD response reports
1,548,375,177 bytes. It reconstructs a clothed surface rather than the underlying parametric
body. It was not installed or claimed to work. See [PIFuHD requirements](https://github.com/facebookresearch/pifuhd#requirements).

## Environment evidence

`experiments/hardware.json`: Windows 11, Python 3.12, approximately 7.75 GB RAM, GTX 1650 4 GB.
The original CUDA 12.1 torch installation failed with disk exhaustion; incomplete local CUDA files
were removed and CPU torch 2.5.1 installed and tested. No system Python dependencies were
downgraded. Open3D 0.19 and the SMPL-X 0.1.28 Python package are installed and imported.
`scripts/inspect_open3d.py` independently verifies the exported body is watertight,
edge/vertex manifold, orientable and free of self-intersections. These packages are listed
separately in `requirements-3d.txt` and captured in the complete lock file; the baseline
does not depend on them. Blender, a licensed SMPL model, HMR2 inference and calibrated cloth
physics are absent. Installing the SMPL-X package does not supply licensed body-model assets.

The 10 October CatVTON integration makes a separate CUDA installation/inference attempt
with the same torch 2.5.1 version and a streaming wheel downloader. The earlier hardware
and CPU verification record does not establish that new GPU path; its outcome belongs in
the current [implementation status](implementation-status.md).

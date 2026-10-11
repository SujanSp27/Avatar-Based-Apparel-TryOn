# Assets and provenance

- `bodyModels/pose_landmarker_full.task`: official Google MediaPipe model, downloaded by script.
  `download-manifest.json` records its exact SHA-256 and source URL.
- `garmentModels`: procedural garment templates live in `ml/garment/templates.py`; generated
  category GLBs and previews are in `experiments/runs/garments`, per-request assets in `data/processed`.
- `textures`: textures are derived from the uploaded garment and embedded in generated GLB.
- Licensed SMPL files and pretrained HMR2 checkpoints are **not bundled**.

Public test images are downloaded to ignored `data/raw`, not treated as user-owned data:

- Studio person: Or Hakim, [Unsplash](https://unsplash.com/photos/lT9oxD8HOLY), full-body studio
  portrait. Sample use is identified separately from user uploads. Height 172 cm is a test
  calibration, not the subject's known height.
- Additional fashion photo: source URL in download manifest; used only for pose rejection.
- 4D-Humans examples: [upstream example folder](https://github.com/shubham-goel/4D-Humans/tree/main/example_data/images).
- COCO/OpenPose samples: [upstream media folder](https://github.com/CMU-Perceptual-Computing-Lab/openpose/tree/master/examples/media);
  these demonstrate multi-person/occlusion/extreme-pose failures and retain their original source rights.
- Yoga: official MediaPipe sample URL in manifest.
- `garment-demo.png`: synthetic striped T-shirt fixture drawn deterministically by
  `scripts/create_demo_garment.py`. It is not a retailer product photo.

Review upstream licensing before redistributing downloaded photos/checkpoints. Downloads use
HTTPS and the manifest records local hashes; those hashes are provenance records, not signatures
from the upstream publishers.

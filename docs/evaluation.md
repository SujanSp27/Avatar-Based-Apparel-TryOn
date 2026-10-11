# Evaluation and acceptance evidence

The six milestones are executable independently:

1. `scripts/validate_reconstruction.py` runs pretrained pose inference on downloaded images,
   rejects unsupported cases, validates meshes and writes OBJ/PLY/GLB and three previews.
2. `ml/measurement/service.py` accepts a mesh plus anatomical landmarks; the analytical ellipse
   test checks section accuracy independently of reconstruction, and real-sample tests ensure
   the chest section does not include connected arms.
3. `POST /api/sizing/recommend` and sizing tests operate without images or a body model.
4. `scripts/validate_garments.py` creates every controlled template, joined with manifold solid
   unions before removing cuffs/neck/hem caps, assigns a photo UV texture and reloads GLB.
5. The same script fits every template to a real pose-derived mesh, records collision diagnostics
   and saves dressed previews/GLBs. Collision checks sample vertices and triangle centres.
6. `scripts/smoke_api.py --all-categories` uploads real image bytes through live PostgreSQL-backed
   FastAPI and checks asset HTTP responses, GLB headers and scene geometries. Playwright then
   uploads through the browser, verifies size/results and actual GLB loading, and exercises views.

Reports live in `experiments/`: reconstruction, garment, API, pytest XML, browser JSON,
hardware and aggregate evaluation. Browser PNGs are actual screenshots of the running app.
The synthetic striped garment stresses segmentation of pale stripes on a pale background.
Using it for all category tests tests geometry branches, not semantic category classification.

`ml/evaluation/metrics.py` implements MAE, RMSE, MAPE with explicit zero exclusion, silhouette
IoU, MPJPE, scaled/rotated/translated P-MPJPE, exact/adjacent/top-2 size accuracy, and strict
person/garment split validation. Metric arrays must have matching finite values. Ground truth
must use consistent units/joint definitions. No true accuracy score is populated without labels.

`scripts/evaluate.py --ground-truth manifest.json` accepts run IDs, measured dimensions,
actual preferred sizes and optionally paired joints. Without ground truth it reports operational
success/failure, latency, RSS and sampled penetration only. These mixed development-run
aggregates are not held-out generalization results. Human review dimensions are provided in
`data/regression/review-template.json`: garment alignment, identity, texture, occlusion and
artifacts. Empty entries mean unassessed.

Generalization is **not established**. Public samples mostly exercise rejection. The accepted
studio subject lacks tape measurements, calibrated camera information and 3D scan ground truth.
There is no diverse held-out human dataset here, no statistically calibrated uncertainty and
no verified retailer chart/preferred-size labels. Different heights and synthetic geometry
tests cannot substitute for different people. Keep every photo/augmentation of one identity
in the same split, and do not reuse garments across splits when assessing garment generalization.

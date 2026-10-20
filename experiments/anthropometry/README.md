# Measurement backend verification

`live-api/report.json` is the final live HTTP evidence for 20 October 2026.
The API ran real MediaPipe CPU inference and persisted both successful extraction
records in the project's MongoDB. Cold/warm latency: 2.6757/0.6725 seconds.
No virtual try-on inference was submitted during these tests.

`live-api/cold-annotated.png` and `warm-annotated.png` were fetched through the
returned static URLs and decoded as PNG. The local sample was uploaded with an
assumed 172 cm test height, not a measured ground-truth height. The final
annotation was visually inspected: chest/waist sections exclude arms, separate
thigh sections do not span both legs, and pose points align with the sample.
The lower chest proxy is below the fullest chest; it is not a tape measurement.
The specified hip-joint formula produces 52.44 cm, which is not an accurate outer
hip circumference. These limits are returned by the API.

`focused-tests.xml`: 37 tests, including actual CPU model inference and repeat
determinism. `full-regression.xml`: 506 CPU tests passed, 3 integration cases
deselected; the new real integration is covered by the focused run.

Earlier diagnostic artifacts:

- `annotated/`: before mask refinement; chest and waist incorrectly included
  part of the arms (134.7 and 110.65 cm). These are **rejected diagnostic outputs**.
- `refined-report.json`: intermediate validation run before adaptive chest
  section selection; studio photo rejected, three other photos failed strict
  heel/ankle visibility. These are not current acceptance results.
- `section-debug.png`, `section-mask.png`: CPU mask/section inspection.
- `refined/`: reviewed final geometry before HTTP deployment.

No anatomical ground truth was available, so these records demonstrate
implementation and validation behavior, not measurement accuracy or calibrated
size confidence. Original photo source is the credited studio sample fetched by
`scripts/download_samples.py`; no user photos were sent to a third-party service.

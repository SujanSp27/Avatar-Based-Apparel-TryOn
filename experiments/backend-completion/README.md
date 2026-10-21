# Backend acceptance — 21 October 2026

- `unit-tests.xml`: 530 CPU regression tests, zero errors/failures. Three integration
  tests were excluded by `-m 'not integration'`; real CPU inference is checked below.
- `live-api/report.json`: 29 actual HTTP checks against the running local API,
  MongoDB and PostgreSQL. Combined CPU pose extraction/size recommendation,
  persisted-record retrieval, annotation PNG download, exact Nike M midpoint,
  identical saved/direct sizing, validation, and deletion all passed. The sample's
  height was supplied as 172 cm for testing, not ground-truth calibration.
- `live-api/annotated.png`: inspected full-body pose/section annotation. Shoulder,
  knee and ankle landmarks follow the pictured person. The chest section is below
  the fullest chest; the hip proxy uses joint spacing and underestimates outer
  circumference. These numerical outputs remain approximate and warnings persist
  into recommendations. This image is not a virtual try-on output.
- `live-api/openapi.json`: actual schema from the running app, 33 operations.
- `restarted-api/`: all 29 live checks passed again after restoring stopped local
  API/database processes. Combined extraction/sizing took 6.4253 seconds; same
  estimates and saved/direct scores, all newly created artifacts deleted.
- `browser-tests.json`: four Playwright regressions passed in 12.7 seconds after
  services were restored. Earlier attempts encountered stopped local processes;
  the final run checks automatic status recovery, no 3D controls and real legacy
  sizing. Worker readiness is controlled in two tests; no GPU generation is tested.

TypeScript and the Vite production build passed (1.69s bundling), as did Ruff and
`pip check`. The existing documented Rollup tree-shaking workaround remains.

The live acceptance script deletes only the measurement it created, including its
annotation, segmentation mask and diagnostic JSON. Copies in this evidence folder
are retained intentionally. No existing user record or try-on result was deleted.

The measured initial combined operation was 4.021 seconds. It does not establish
VTON latency or anthropometric accuracy. No GPU inference or public-demo upload
was submitted. Colab reported `runtime_changed`; measurement/sizing readiness
returned 200 while try-on readiness returned 503. A live connection is required
before generating another try-on.

Reproduce backend acceptance with `.venv/Scripts/python.exe scripts/verify_backend_api.py`.
The script accepts only a loopback API URL and uses configured admin credentials
without saving them to reports. Full regression command:
`.venv/Scripts/python.exe -m pytest -m 'not integration' -q`.

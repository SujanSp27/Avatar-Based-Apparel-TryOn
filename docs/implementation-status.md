# Current implementation status - 19 October 2026

The latest user direction is **2D only, existing Colab only, no local GPU**, with
automatic connection at app startup and no manual connection control in the UI.
The user reconfirmed that photos must remain in their Colab only; public GPU demo
uploads are not authorized. The latest speed target is 10-20 seconds for a fresh,
visually acceptable result. No local GPU is used for inference.
Previous scope and verification records are preserved in
[the archive](archive/implementation-status-before-online-only.md); the original
root specification file is no longer present. The phase labels below are historical
references, and the active requirements are in [requirements.md](requirements.md).

| Phase | Requirement | Status | Evidence |
|------|------|------|------|
| 0 | Explicit image/category/privacy scope | IMPLEMENTED | `docs/requirements.md`; image validation and category enums |
| 1 | FastAPI, React, PostgreSQL, local assets | IMPLEMENTED | Running app, API/database/browser tests; local base requirements exclude GPU/3D dependencies |
| 1 / 12 | Automatic Colab connection and status-only UI | IMPLEMENTED | `backend/app/colab_connection.py`, `scripts/auto_connect_colab.py`; startup monitor; automatic browser recovery tests |
| 1 / 12 | Restore missing worker on existing GPU | IMPLEMENTED | `scripts/colab_worker_recovery.py`; runtime identity checked before writes, owned-process checks, pinned setup, bounded retries, no inference replay. Validated `config/online-worker.json` seeds missing runtime configuration only; recovery unit tests |
| 2 | Person/garment decoding, pose/parsing in online model | IMPLEMENTED | `online_vton.py`, FASHN official preprocessing; actual T4 inference report |
| 3 / 4 | 3D human reconstruction and mesh measurements | BLOCKED | Removed from active scope at user's request; no image-derived measurement claims |
| 5 / 6 | Versioned charts and explainable size engine | IMPLEMENTED | Existing database/API/engine retained; independent measured-input size API/browser test |
| 7 / 8 / 9 / 10 | 3D garments, fitting, cloth simulation and GLB scene | BLOCKED | Removed from active scope at user's request; replaced by photo generation |
| 7 / 8 / 9 | Real pretrained image-based garment generation | PARTIALLY IMPLEMENTED | FASHN VTON 1.5 native FP16 result has a continuous hem, aligned sleeves and no visible old-shirt fragments in the reviewed example. Simplified folds/collar proportions remain; reduced-resolution experiments have unacceptable sleeve/hem artifacts |
| 11 | Uploads, eleven categories, photo type, original comparison and PNG output | IMPLEMENTED | `frontend/src/App.tsx`, `PhotoViewer.tsx`; seven browser tests passed |
| 12 | Colab-only transport, jobs, failures, reconnect without local fallback | IMPLEMENTED | Transport/DB/job/reconnection tests; same worker URL retained throughout an in-flight event. Lossless input/output transport, exact-pixel round-trip tests, response type/format/dimension checks and stage diagnostics |
| 13 / 14 | Evaluation records and broader quality/generalization | PARTIALLY IMPLEMENTED | Eight saved striped-shirt benchmarks and images, plus a rejected dress-input check; native FP16 review and experiment rejections in `docs/online-performance.md`. Broad FASHN category quality remains unvalidated |
| 15 | Acceptable fresh generation within 10-20 seconds | PARTIALLY IMPLEMENTED | Native FP16/20 steps improved from 292.278s to 54.583s end to end. Cropped 384 x 576/10 steps reached 14.914s but failed visual review; the combined speed-and-quality target is not met |
| 16 | Complete production-quality application | PARTIALLY IMPLEMENTED | Web/API/size engine and online generation exist; garment quality, cloud environment isolation and latency need further work |

Saved benchmark evidence is detailed in [online-performance.md](online-performance.md).
The 54.583-second native FP16 image was reviewed on 18 October: face recognizable,
hands retained, sleeves aligned, no visible old-shirt fragments and a continuous
hem. This is one controlled example, not production-quality acceptance across
categories. Reduced-resolution 10/15-step images and their cropped variants retain
unnatural sleeve transitions and hem artifacts; none qualifies as an accepted fast
preset. Native guidance-1.0 / 10 steps reached 21.274s; adding the official clothing
mask reached 19.627s. Both failed visual review. Raw outputs and masks are saved;
the faster settings are not promoted to the tracked default profile.

Recorded connection and local verification (historical checks, not a claim that
an ephemeral Colab session is currently live):

- 422 CPU-only Python tests passed with zero failures or errors in
  `experiments/online-profile-transport-tests.xml`. Coverage includes strict worker
  profile validation, seeding absent configuration while preserving existing files,
  lossless transport, malformed response rejection and sampler safeguards. These
  local tests do not imply that the latest worker changes are live in Colab.
- `experiments/lossless-transport.json` records CPU serialization checks: the person
  payload was 25.23% smaller and the reviewed result payload was 23.81% smaller,
  with identical decoded pixels. These are byte savings, not measured reductions in
  end-to-end inference time. Worker and transport stage timings are now recorded to
  measure the remaining costs on a subsequent live run.
- 351 CPU-only Python tests passed, 2 integration tests deselected, after runtime
  pinning and hem changes. `experiments/online-recovery-hem-tests.xml` records the
  run. Hem tests cover waistband overlap, disconnected label patches, excessive
  extension, sloped hems, and exact protection of unrelated pixels. These tests
  validate mask behavior, not realistic photographic fitting.
- 51 focused Python tests passed, including expired-worker recovery, bounded
  retries, existing-task preservation, connection rotation, real size API and jobs.
- Seven Playwright tests passed: automatic preparation/readiness without clicking,
  API loss/recovery without reload, no avatar controls, independent sizing, and
  retained-job recovery. Network-state tests use controlled responses and do not
  establish model image quality.
- On 16 October, one additional live Playwright test passed against the restored Colab T4:
  the app reached Ready without connection controls; sample inputs enabled Generate.
  `experiments/automatic-colab-ready.png` was visually inspected and
  `experiments/automatic-colab-connection.json` records live readiness and no local GPU.
- Ruff and TypeScript checks pass. The production frontend build passed (59
  modules, 212.18 kB JavaScript / 67.07 kB gzip).
- Live startup reopened the saved notebook automatically. It had a T4 but its
  temporary worker files had expired; pinned setup completed, the worker loaded,
  and the new tunnel was adopted automatically. No extra generation was submitted
  for this connection verification. A saved URL never substitutes for a live probe.

The 17 October connection reached several different runtime hostnames. Recovery
now refuses to mutate a runtime different from the verified pin. The original
292.3-second result and the subsequent native/reduced-resolution FP16 images and
timings are safely local under `experiments/online-runs/`.
The reviewed native FP16/guidance-1.5 settings are persisted in
`config/online-worker.json` for restoring missing runtime configuration. Existing
settings and running jobs are preserved. A native guidance-1.0 experiment has not
run; it has no speed or quality claim here.
`scripts/online_worker.py` also saves source and generated semantic label maps
alongside raw output, allowing subsequent visual review to separate model,
parsing and compositing errors.

Colab can require Google authentication/consent or GPU selection. Those browser
actions cannot be automated by the notebook helper. Automatic restoration requires
the already-authorized notebook, network access and an allocated GPU. The current
Colab profile inherits system packages; unrelated inherited-package conflicts
are recorded by pip and a fully isolated, clean profile remains unfinished.

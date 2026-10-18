# Current implementation status — 17 October 2026

The latest user direction is **2D only, existing Colab only, no local GPU**, with
automatic connection at app startup and no manual connection control in the UI.
The original phase plan is retained for history. Previous verification records
are in [the archive](archive/implementation-status-before-online-only.md).

| Phase | Requirement | Status | Evidence |
|------|------|------|------|
| 0 | Explicit image/category/privacy scope | IMPLEMENTED | `docs/requirements.md`; image validation and category enums |
| 1 | FastAPI, React, PostgreSQL, local assets | IMPLEMENTED | Running app, API/database/browser tests; local base requirements exclude GPU/3D dependencies |
| 1 / 12 | Automatic Colab connection and status-only UI | IMPLEMENTED | `backend/app/colab_connection.py`, `scripts/auto_connect_colab.py`; startup monitor; automatic browser recovery tests |
| 1 / 12 | Restore missing worker on existing GPU | IMPLEMENTED | `scripts/colab_worker_recovery.py`; runtime identity checked before writes, owned-process checks, pinned setup, bounded retries, no inference replay; recovery unit tests |
| 2 | Person/garment decoding, pose/parsing in online model | IMPLEMENTED | `online_vton.py`, FASHN official preprocessing; actual T4 inference report |
| 3 / 4 | 3D human reconstruction and mesh measurements | BLOCKED | Removed from active scope at user's request; no image-derived measurement claims |
| 5 / 6 | Versioned charts and explainable size engine | IMPLEMENTED | Existing database/API/engine retained; independent measured-input size API/browser test |
| 7 / 8 / 9 / 10 | 3D garments, fitting, cloth simulation and GLB scene | BLOCKED | Removed from active scope at user's request; replaced by photo generation |
| 7 / 8 / 9 | Real pretrained image-based garment generation | PARTIALLY IMPLEMENTED | FASHN VTON 1.5; saved striped-shirt output has hem/shoulder artifacts. Bounded hem-overlap fix passes semantic-mask tests; a fresh photographic comparison remains pending |
| 11 | Uploads, eleven categories, photo type, original comparison and PNG output | IMPLEMENTED | `frontend/src/App.tsx`, `PhotoViewer.tsx`; seven browser tests passed |
| 12 | Colab-only transport, jobs, failures, reconnect without local fallback | IMPLEMENTED | Transport/DB/job/reconnection tests; same worker URL retained throughout an in-flight event |
| 13 / 14 | Evaluation records and broader quality/generalization | PARTIALLY IMPLEMENTED | Actual benchmark/report and retained historical cases; broad FASHN category quality remains unvalidated |
| 15 | Under-ten-second fresh generation | BLOCKED | `experiments/online-runs/striped-20/benchmark.json`: T4 BF16/20 steps, 280.6s model, 292.3s end-to-end. No fabricated speed claim |
| 16 | Complete production-quality application | PARTIALLY IMPLEMENTED | Web/API/size engine and online generation exist; garment quality, cloud environment isolation and latency need further work |

Current connection verification:

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
292.3-second result is safely local; there is no completed FP16 benchmark yet.
`scripts/online_worker.py` also saves source and generated semantic label maps
alongside raw output, allowing subsequent visual review to separate model,
parsing and compositing errors.

Colab can require Google authentication/consent or GPU selection. Those browser
actions cannot be automated by the notebook helper. Automatic restoration requires
the already-authorized notebook, network access and an allocated GPU. The current
Colab profile inherits system packages; unrelated inherited-package conflicts
are recorded by pip and a fully isolated, clean profile remains unfinished.

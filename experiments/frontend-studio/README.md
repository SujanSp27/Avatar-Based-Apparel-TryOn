# Frontend verification — 21 October 2026

- `python-tests.xml`: 542 CPU backend tests passed; 3 integration tests deselected.
- `browser-tests.json`: 10 passed, 3 opt-in live-Colab tests skipped, 45.3 seconds.
- `npm-audit.json`: zero known vulnerabilities after same-major security updates.
- Strict TypeScript and production Vite build passed (172 modules, 6.28 seconds
  bundling; main JavaScript 263.26 kB / 83.90 kB gzip).
- Ruff and `pip check` passed.

Browser tests used real local signup/login, MongoDB profile data, CPU MediaPipe
extraction, Nike product chart scoring, saved scans and saved sizes. Manual metric
corrections in the test are explicit fixtures, not validated anthropometry.
The tests verified cookie attributes, refresh rotation across two tabs, forced
401 recovery, authenticated thumbnails, deletion and sign-out. Unit tests cover
cross-account isolation, refresh replay revocation, reset expiry and SMTP delivery
through a test adapter.

Screenshots cover measurement, sizing, signup and profile at desktop/mobile
widths. Axe WCAG 2 A/AA and 2.1 AA rules reported no violations on tested screens;
this is not a complete manual accessibility certification. Physical-camera capture
and OS share sheets were not manually exercised; camera denial and supported
capture lifecycle paths are implemented.

`tryon-retained-result.png` displays the actual historical CatVTON image associated
with local run `04360792-ad1f-4ec2-8ab7-1255eb8cecc0`. Its 253.9-second caption is
historical. This check verifies viewer loading, comparison, zoom and download,
not a new inference or an accepted fast model preset. Connection/recovery tests
use explicitly controlled transport responses. No GPU job or external photo upload
was submitted by this test suite. Current live Colab readiness is `runtime_changed`.

The app and both databases were restored after their local processes stopped
between sessions. Final readiness: frontend 200; API 200; MongoDB/PostgreSQL
available; measurement/sizing capabilities available; try-on unavailable until the
existing Colab worker is recovered. The API exposes 48 operations. SMTP is not
configured, so the UI correctly reports password-email delivery as unavailable.

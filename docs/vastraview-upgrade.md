# VastraView upgrade: audit and implementation plan

## Audit (25 October 2026)

Existing stack: React 19 + strict TypeScript/Vite, React Router, React Hook Form,
FastAPI/Pydantic 2, SQLAlchemy/PostgreSQL for chart versions and runs, MongoDB for
accounts and anthropometry, MediaPipe CPU estimation, pinned FASHN VTON 1.5 on
the user's private Colab GPU. Preserve the model, preprocessing, compositor and
one-job capacity. The runtime remains ephemeral, not an inference SLA.

Working: signup/login/logout, Argon2id, short access JWTs with issuer/audience
validation, atomic refresh rotation/reuse revocation, reset SMTP adapter,
authenticated scans and saved sizes, sourced charts with gaps, compact real-image
comparison, persisted job status, automatic bounded Colab restoration.

Critical gaps: public static run/annotation trees; jobs and measurement IDs are
not authorization; absent admin secret permits writes; signup enumerates emails;
no verification/account deletion/session management; catalog is a six-row Python
list without search/pagination/favorites; no HTTPS production configuration.
Existing sample image commercial rights are not established. No fabricated
brand products/charts will be seeded.

## Stages

1. Audit and baseline tests; record risks and preserve existing data.
2. Use supplied logo, metadata/favicon and shared brand component; database-backed
   catalog/taxonomy, honest brand coverage, product filters/details/favorites.
3. Extend existing authentication with single-use email verification, secure
   production validation, session management and password-confirmed deletion.
4. Profile preferences/history/favorites; explicit measurement saving consent.
5. Owner checks for jobs, images and annotations, browser-scoped guest ownership,
   fail-closed admin writes, rate limits, retention tooling and safe headers.
6. Backend/browser regression, build, dependency audit and deploy documentation.

## Security references

- [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [OWASP password recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
- [PyJWT claim validation](https://pyjwt.readthedocs.io/en/stable/usage.html)

Deployment review must separately verify SMTP delivery, licensed product assets,
HTTPS/cookies on real domains, backups, retention scheduling and sustained GPU
capacity. Code/test completion is not a production security certification.

## Implemented changes and verification

Branding/catalog: original logo and derived favicon viewport; existing shell,
auth and footer updated; real database catalog with 23-brand directory, 24-type
taxonomy and six attributed research references. Product cards have a shared
image frame, product detail/source/rights information and authenticated favorites.
No unsupported inventory or official partnerships are invented.

Accounts/privacy: maintained JWT/Argon2id integration, production verification
requirements, single-use email tokens, session management, profile units and
password-confirmed deletion. Protected run/annotation serving replaces public
static files; guests receive a signed browser-scoped cookie. Existing unowned
artifacts remain preserved and quarantined. User-specific caches are no-store.

Operations: versioned SQL history index, MongoDB indexes, request/concurrency
limits, privacy-safe errors, production-only HTTPS/secrets checks, non-root API
container, same-origin reverse proxy, separate production volumes and dry-run
retention tool. Production research samples are hidden rather than pretending
their commercial image rights are verified.

Verification: 647 backend tests and three CPU model integration tests passed.
Production frontend build, Ruff and dependency consistency passed. All 21 final browser
checks include actual MediaPipe extraction and six-metric sizing, cross-tab
session rotation, filters, favorites, account deletion, responsive accessible
catalog and the existing comparison controls. Two navigation races found by
the browser checks were corrected. Source edits are in `backend/app/accounts/`,
`catalog.py`, `private_data.py`, `main.py`, `anthropometry/router.py`, the React
feature modules, and `deploy/`; targeted new tests are `test_vastraview*.py` and
`e2e/vastraview.spec.ts` / `e2e/private-tryon-live.spec.ts`.

Fresh inference: the existing notebook verified/restored its replacement T4 and
completed job `2198597c-ce71-460e-9995-1a2a2b385488` in 32.102 seconds. Private
history/image authorization, refresh, slider, side-by-side, mobile layout,
health-network interruption and byte-identical download passed against that
actual result. Full-resolution visual review confirms sage polo construction,
with softened fine fabric/buttons; this is not a claim of perfect fitting.

Remaining gates are recorded in [implementation status](implementation-status.md)
and [deployment guide](vastraview-deployment.md), including actual email delivery,
container/HTTPS deployment, licensed catalog inventory, the MediaPipe/protobuf
advisory and reliable GPU capacity.

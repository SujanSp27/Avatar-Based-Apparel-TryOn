# VastraView deployment review

## Architecture and scope

The existing React 19/Vite frontend and FastAPI API remain. PostgreSQL stores
try-on runs and legacy chart versions. MongoDB stores accounts, immutable
anthropometry charts, catalog, favorites, saved measurements and access metadata.
MediaPipe measurement extraction is CPU-based. FASHN VTON remains on the owner's
private Colab GPU; no local GPU or third-party public image service is used.

This is a deployment-review candidate, not a certified production service.
The application uses one API worker and one bounded inference slot. Do not scale
Uvicorn workers or replicas until the persisted local job queue and Colab recovery
lock are replaced with a shared coordinator. Colab does not provide an SLA.

## Development

Use `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1`.
Frontend: `http://127.0.0.1:5173`; OpenAPI: `http://127.0.0.1:8000/docs`.
The script retains existing PostgreSQL/MongoDB data. Use `scripts/stop_owned.py`
to stop only the recorded web/API processes. Copy `.env.example` for a new install;
do not replace an existing `.env`. Empty ADMIN_TOKEN now denies admin mutations.

The exact supplied logo is copied using `python scripts/prepare_branding.py`.
The favicon embeds the same artwork in an SVG viewport. No substitute logo or
AI-edited wordmark is used.

## HTTPS deployment

1. Copy `.env.production.example` to `.env.production` outside version control.
   Generate independent secrets using `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
   Put them directly into the deployment's secret manager/environment. Use a
   separate ADMIN_TOKEN. Never reuse the development-generated signing key.
2. Configure real DNS, `PUBLIC_HOST`, `APP_PUBLIC_URL`, and exact HTTPS
   `CORS_ORIGINS`. Configure STARTTLS SMTP and verify sender-domain delivery.
   Production startup refuses missing signing secrets, insecure cookies,
   unverified signup mode, wildcard/non-HTTPS origins and missing SMTP settings.
3. Start only databases first:
   `docker compose --env-file .env.production -f compose.production.yml up -d db mongo`.
   Create a MongoDB application user with `readWrite` only on the `vastra`
   database using an authenticated operator shell. Enter the password at the
   prompt, not in shell history. Use its URL-encoded credential in MONGODB_URI.
   The API must not use the MongoDB root account.
4. Put the existing licensed pose checkpoint in `assets/pose`. Run
   `python -m scripts.download_catalog` to restore the 51 licensed catalog photos
   from pinned sources; add other authorized catalog images in `data/raw`.
   These are read-only mounts, never built into the
   image. Review ownership/permissions for UID 10001 on Linux bind mounts.
5. Build/start:
   `docker compose --env-file .env.production -f compose.production.yml up -d --build`.
   Caddy terminates HTTPS; Nginx serves the web build and proxies private images
   and API requests on the same origin. Database/API ports are not exposed.
   Keep the private Colab worker's URL/token in protected server configuration.
6. Check `/api/v1/health/live` and `/api/v1/health/ready?capability=sizing`.
   Measurement readiness also requires the checkpoint; try-on readiness requires
   both databases and the actual remote model. Verify a real inference on the
   intended Colab runtime. Docker cannot operate the desktop browser helper;
   automatic notebook restoration remains a local-development integration.

Container build/HTTPS/real SMTP delivery require deployment verification. Pin
reviewed image digests before release. The API deliberately does not trust public
forwarded-IP headers; validate trusted proxy IP handling and per-user/IP limits
under the final topology. Never expose port 8000 directly to the Internet.

## Accounts and private assets

Access JWTs are short lived and validate signature, issuer, audience and expiry.
Refresh cookies are HttpOnly, SameSite=Strict, Secure in production, rotated
atomically, with reuse revoking the session. A short HttpOnly access cookie lets
image elements load protected images. State-changing browser requests reject
foreign origins/Sec-Fetch-Site. Deploy frontend and API on one origin.

Production signup requires verification. Verification/reset links use URL
fragments, single-use hashed tokens and expiry. SMTP tests use a local test double;
deliverability and HTTPS links must be tested with the actual email provider.
No default production admin or OAuth integration is created.

New try-on jobs require an account. Run images, annotations and measurements have
an owner. Guest measurement and historical guest-result access use a signed
HttpOnly browser cookie. UUIDs and URLs are not authorization. Existing
unowned runs are retained but inaccessible through public routes; do not assign
them to the first visitor or expose the old static directory. An operator must
verify ownership offline before a deliberate metadata migration.

Profile saves are explicit actions with consent timestamps. Authenticated users
can delete scans, completed try-on images/results, favorites, sessions or their
account (password confirmation required). Account deletion refuses active work.
Local deletion does not erase Colab files or backups. Concurrent public-load
testing and independent security review remain release gates.

## Catalog and sizing provenance

`/api/v1/brands`, `/categories`, `/products`, `/products/{id}` and image routes
are data-driven. Twenty-eight brands are a directory, not invented inventory.
There are 51 newly sourced CC0/Pexels references plus six historical research
references in development. Production excludes those six restricted references.
The five editorial ethnic/co-ord outfits are browse-only; none claim model support
or available stock. Full source manifests and chart coverage are documented in
[the fashion upgrade report](fashion-platform-upgrade.md).

Publish real authorized assets with `PUT /api/v1/products/{id}` plus X-Admin-Token.
The schema requires a stable ID, source, license statement, audience, colors,
supported subcategory and a server-local image. The endpoint validates decoding
and confines the path to data/raw. It never fetches arbitrary URLs. Confirm actual
image rights before setting commercial_use=true. Supported sizes must come from
the product source; an empty list is shown as unavailable, never guessed.

Sizing stays independent from image generation. The six-metric midpoint error
and confidence formula remain unchanged. Chart versions record source URL,
market, gender, units and measurement basis. Source-unit inches are normalized
to centimetres for calculation; display can switch units. The similarity score
is not a calibrated fit probability. Add product-specific guides with the existing
administrative chart API, retaining apparel_id and immutable versions.

## Retention, backup and recovery

Default temporary-file retention: guest 24 hours; authenticated generated data
30 days. Saved profile scans are retained until explicitly deleted. Run:

```
python -m scripts.cleanup_private_data
python -m scripts.cleanup_private_data --apply
```

The first command is a dry run. Schedule cleanup daily with the API stopped to
avoid deleting files during an in-flight request. Processing/unowned legacy runs
and malformed records are preserved for operator review. Inspect dry-run counts,
then apply. Keep administrative deletion/audit logs limited to IDs and actions.

Back up PostgreSQL, MongoDB, protected assets and session-key configuration to
encrypted access-controlled storage. Test a coordinated restore before launch.
Define a backup expiry window and Colab artifact cleanup process; local deletion
alone is not a complete erasure policy. Restrict access to logs and never archive
the development experiment directory as public assets. `.gitignore` prevents new
private artifacts from being added; it cannot purge already tracked files or Git
history. Review those separately before publishing this repository.

## Verification and release gates

The 26 October [fashion upgrade report](fashion-platform-upgrade.md) supersedes
the counts below: 655 backend/CPU checks and a fresh private Colab run have been
verified. Browser results, measured latency, source coverage and remaining limits
are recorded there. No new deployment or inference SLA is implied.

On 25 October 2026, 647 backend tests and all three local-checkpoint CPU
integration tests passed. Strict TypeScript/Vite build, Ruff and `pip check`
passed. The final combined 21-test browser run passed and exercised catalog filters, accessibility, accounts,
measurements, sizing, session rotation, favorites, deletion and comparisons.
The opt-in `e2e/private-tryon-live.spec.ts` generated one actual sage-polo result
on the existing private Colab T4, verified owner-only access/history, downloaded
identical result bytes and retained the result across reload/health interruption.
Its session is kept only in ignored `.runtime/` files so rechecking resumes the
same job rather than issuing another GPU request.

The Compose configuration validates with `config --no-env-resolution --quiet`
using explicit non-production validation values. Docker's daemon is unavailable
in this environment, so this is not a successful container build or deployment.

Dependency audit: npm reported zero vulnerabilities. Compatible patches were
installed for FastAPI/Starlette, multipart, Pillow, PyJWT, PyMongo and pytest;
the remote Colab environment was left intact. The remaining Python advisory is
**CVE-2026-0994 / PYSEC-2026-1805**, reported twice for protobuf 4.25.9: nested
`json_format.ParseDict`/`Any` recursion can bypass its limit. MediaPipe 0.10.21
requires protobuf below 5, while the audit lists fixes in 5.29.6 and 6.33.5.
Do not force an incompatible protobuf upgrade. Migrate and regression-test the
pose dependency in isolation, then rerun the audit before release. The API does
not accept user protobuf structures, but that is not a blanket waiver of the
finding. Audit JSON is retained in ignored `.runtime/` files.

Run backend pytest, Ruff, frontend build, browser suites and dependency audits.
Use isolated test databases for destructive tests. Browser account tests create
only disposable example.com users. Existing retained neural output fixtures test
rendering and downloads; they do not prove a fresh model inference.

Before public release verify: real SMTP verification/reset, real HTTPS cookie/CSRF
behavior, licensed inventory, MongoDB least privilege, backups/restore, scheduled
retention, abuse/load limits, stable GPU capacity, current dependency advisories,
and independent security/privacy review. OAuth, MFA, horizontal queue scaling
and guaranteed generation latency are not implemented or claimed.

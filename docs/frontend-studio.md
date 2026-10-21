# FormFit Studio web application

The React 19 / strict TypeScript application uses real FastAPI services. It has
code-split routes, a shared cream/sage design system, accessible native dialogs,
React Hook Form/Zod validation and in-memory React contexts for sessions and active
measurements. It does not fabricate measurement, size or try-on results.

## Routes and capabilities

| Route | Behavior |
|---|---|
| `/measure` | JPEG/PNG/WebP upload with 10 MB validation, resizing and metadata removal; optional camera capture with alignment guide; cm/feet/inches height; CPU MediaPipe extraction; actual 33-landmark canvas; six editable metric cards; private profile save |
| `/sizing` | India brand/product guides, men's/women's collection, categories, manual or extracted measurements, exact weighted midpoint scoring, chart ranges, dimension-level fit indicators, rankings and heuristic confidence gauge |
| `/tryon` | Person/garment uploads, sample garment rail and filters, eleven model categories, automatic private Colab readiness, asynchronous job recovery, original/generated slider, side-by-side comparison, zoom, PNG download and platform file sharing |
| `/signup`, `/login` | Real account creation and login, password requirements and confirmation, terms acceptance, remember-me, safe return path and guest access |
| `/reset-password` | Single-use expiring reset links; token read from URL fragment and removed from browser address |
| `/profile` | Protected route; editable name/height, paginated private measurement history with authenticated thumbnails, reusable measurements, deletion and saved brand sizes |
| `/terms` | Data handling, research limitations and deployment notes |

The browser calls the existing `/api/tryon/jobs/{job_id}` endpoint. Reloading a
running job polls its original ID and does not submit another generation. Only
results declaring the pretrained rendering method enter the result viewer.
Photo generation is separate from the size engine. Chart similarity is explicitly
labelled as a heuristic, not a statistically calibrated probability or fit guarantee.

The measurement service returns `landmarks_normalized` as 33 arrays of
`[x, y, z, visibility]`. The browser draws these actual detections over the uploaded
photo. Changing the photo or height invalidates earlier estimates. Measurements
are approximate, especially circumferences inferred from frontal projections.

Brand options come from MongoDB. Four verified Nike/Puma India product charts and
fictional demo fixtures are present. Unavailable Adidas, Allen Solly and U.S. Polo
Assn. combinations explain their missing guide instead of inventing ranges. The
sample garment rail currently contains one labelled synthetic T-shirt; other
categories accept user uploads and show an honest empty catalog state.

## Accounts and session lifecycle

`backend/app/accounts/` provides the account and private-profile APIs. Passwords
are Argon2id hashes. Access JWTs expire after 15 minutes and live only in browser
memory. Refresh credentials are random, hashed in MongoDB, rotated atomically,
and delivered through an HttpOnly, SameSite=Strict cookie restricted to
`/api/v1/auth`. Remember-me sessions expire in 30 days; other sessions have a
browser-session cookie and a one-day server expiry. Logout and password reset
revoke server sessions, including outstanding access tokens.

The API client retries an expired access request once after refreshing. A single
promise coordinates simultaneous requests; the browser Web Locks API coordinates
rotation across tabs when supported. Cookies and JWTs are not written to local
or session storage. The only persistent try-on browser identifier is a job UUID.
Origin checks protect cookie-authenticated actions; MongoDB-backed rate limits
bound login, signup and password reset attempts. Account-owned scans, thumbnails
and sizes check ownership on every request.

Set `AUTH_SECRET` to a private random value of at least 32 characters for deployed
instances. Development generates a persistent key under ignored `.runtime/`.
HTTPS deployment requires `AUTH_COOKIE_SECURE=true`, the actual `APP_PUBLIC_URL`
and restricted `CORS_ORIGINS`. Password email delivery uses STARTTLS SMTP configured
with `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Without
delivery configuration the UI reports the real 503; it never claims to send mail.

## Verification and deployment limits

Regression tests live in `tests/test_accounts.py` and `frontend/e2e/studio.spec.ts`.
The latter exercises the real local account, CPU measurement and sizing APIs;
connection/failure tests explicitly control network responses. Retained-result
viewer tests load a genuine previously generated image and submit no new inference.
Screenshots and test reports are stored in `experiments/frontend-studio/`.

The implementation is a working local research application, not a claim of
enterprise deployment certification. Existing guest measurement annotations and
try-on assets still use legacy public local URLs; they need ownership enforcement,
retention policy and protected delivery before internet deployment. Private saved
profile thumbnails are authenticated. SSO, MFA, email verification, account deletion
and production SMTP provisioning are not included. Cross-browser/device testing
and physical tape-measure validation remain separate acceptance work.

The Colab runtime must actually be available for new image generation. Prior
timings and visual reviews remain in `docs/online-performance.md`; this frontend
work does not establish new inference quality or a guaranteed 30-second latency.

## Run and verify

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
.venv/Scripts/python.exe -m pytest -q -m "not integration"
cd frontend
npm ci
npm run build
npx playwright install chromium
npx playwright test
```

The normal browser suite never launches GPU inference. Live Colab tests require
their existing explicit environment opt-ins. The local app is at
`http://127.0.0.1:5173`; OpenAPI is at `http://127.0.0.1:8000/docs`.

# Fashion discovery and sizing upgrade — verified 26 October 2026

## Audit and sequence

Preserve React 19, FastAPI, MongoDB/PostgreSQL, the private Colab FASHN worker,
its model revision/settings, and the existing measurements and comparison UI.
Baseline from the previous milestone: 650 Python and 21 browser checks passed.

1. Enforce account authentication before new inference; preserve private ownership.
2. Source distinct reusable photographs and metadata, then expand data-backed
   discovery, filters and pagination. No manufactured inventory or brand claims.
3. Add explicitly scoped, sourced chart records with region, units, body/garment
   basis and verification. Never use garment dimensions as body measurements.
4. Improve the editorial homepage, catalog, chart controls and image error states.
5. Run API, model, ownership, chart, browser, build and responsive regression checks.

New inventory remains a discovery/reference collection, not a store with verified
stock. Unknown sizes and brands stay unknown. Unsupported layered/draped garments
remain browseable but are not offered to the inference model as supported inputs.

## Delivered implementation

- Two-column editorial homepage, original logo, forest/sage/ivory palette, full-length
  photograph, both requested CTAs and responsive layouts. The editorial image is
  explicitly separate from generated results. Existing comparison controls remain.
- **51 new unique references; 57 total** in development. New entries: 11 men,
  27 women and 13 unisex; 25 subcategories. Includes blazers, blouses, casual/formal
  dresses, chinos, crop tops, formal/casual shirts, hoodies, jackets, jeans,
  leggings, polos, shorts, skirts, sweaters, sweatshirts, tees/camisoles and five
  editorial kurta/kurti/saree/salwar/co-ord references. The latter are browse-only.
- Database-backed name/brand search, audience/category/color/occasion filters,
  name/newest/relevance ordering, pagination, details, attribution, favorites,
  safe image-error states and selection into the authenticated studio. The
  existing "Discover another look" rail now filters on the server.
- A 28-brand discovery directory does not imply stock or partnerships. New
  garment manufacturers/sizes are unknown and remain null/empty. These are
  references, not fabricated commercial listings. No alternate color is simulated.
- New try-on POSTs and manual recovery requests require a real account. The
  protected React route retains the product/job query through sign-in. Existing
  private-result ownership and historical guest asset access remain intact.
- 23 official body-chart scopes across six brands (plus six clearly marked demo
  scopes). Four existing India guides received new provenance versions without
  overwriting old records. Other new guides have explicit regional labels.
- Sizing now displays source/verification/date, region, sizing system and body
  versus garment basis; cm/in inputs and results; only published dimensions are
  required. Exact midpoint-error weights and heuristic confidence are unchanged.
  Missing guides offer other published category/market scopes. No automatic
  India/US/UK/EU label equivalence or guaranteed fit is claimed.

## Public image assets and rights

`data/catalog/garments-v2.json` records each ID, original image URL, source page,
credit, license URL, image dimensions and SHA-256 checksums. The 51 optimized local
images live at `data/raw/catalog/*.webp` (about 2.37 MiB total); private uploads are
never in this manifest. `python -m scripts.download_catalog` restores and verifies
them from their pinned sources before an API restart. This operation is repeatable
and fails on changed source bytes; it does not overwrite curated database fields.
Download public images before first deployment; the seed retries missing assets
instead of permanently publishing inactive records. The Docker API image includes
the manifest and mounts the public photo directory read-only.

- 46 distinct isolated/hanging garment photographs: [Clothing Dataset](https://github.com/alexeygrigorev/clothing-dataset),
  commit `7ed86a9cc56763b6acb35e41cb35184e43a5d218`,
  [CC0 license](https://github.com/alexeygrigorev/clothing-dataset/blob/7ed86a9cc56763b6acb35e41cb35184e43a5d218/LICENSE).
  These are community reference photographs, mostly 400 px wide, not newly shot
  high-resolution retail photography. They are not upscaled to claim extra detail.
- Five distinct editorial outfit photographs: Pexels IDs 13192043 (RAJESH KUMAR
  VERMA), 28332599 (Sabir Khan Shourov), 22064230, 22064197 and 22064213 (MK .).
  Source/credit is linked on each product detail. [Pexels license](https://www.pexels.com/license/)
  permits website use; no depicted person's endorsement or stock ownership is implied.
- Independent hero: [rehman yousaf, Pexels 13816068](https://www.pexels.com/photo/a-woman-wearing-a-beige-dress-13816068/).
  `frontend/public/editorial/beige-dress-{640,1200}.webp` are 20 KB and 53 KB,
  use responsive sources and preserve the full-body photograph. No generated outfit
  or private try-on input was substituted into this editorial section.
- The six older research references remain available locally; their commercial
  rights are unestablished, so production filtering continues to exclude them.
  Production currently has 51 licensed references, not 57 saleable products.

## Chart coverage and sources

Measurements are stored in canonical centimetres. Inch sources use exactly 2.54
cm/in. Published point measurements remain points (`lower == upper`); no ranges,
missing dimensions or regional conversions are invented. New source checks are
dated 25 October 2026; the preserved Nike/Puma checks remain dated 20 October.

| Brand | Published scopes | Market and source |
| --- | --- | --- |
| Nike | Men's/women's product-specific T-shirt body guides | India: [men HV4188-013](https://www.nike.in/nike-men-s-dri-fit-t-shirt/p/27753405), [women](https://www.nike.in/nike-sportswear-chill-knit-women-s-slim-mod-cropped-t-shirt/p/27753683) |
| Puma | Men's T-shirt, women's polo body guides (T-shirt category) | India: [men 634184](https://in.puma.com/in/en/pd/premium-essentials-mens-graphic-t-shirt/634184), [women 691419](https://in.puma.com/in/en/pd/essentials-elevated-womens-logo-polo-t-shirt/691419) |
| Manyavar | Men's kurta upper garment guide for M218838 | [India body table](https://www.manyavar.com/en-in/full-length-kurta-pajama/basic-cream-kurta-set/M218838.html). The larger garment chest in the product selector is deliberately excluded |
| Adidas | Men's/women's shirts, tees, standard trousers and shorts | UK: [men tops](https://www.adidas.co.uk/help/size_charts/men-shirts_tops), [women tops](https://www.adidas.co.uk/help/size_charts/women-shirts_tops), [men bottoms](https://www.adidas.co.uk/help/size_charts/men-pants_shorts), [women bottoms](https://www.adidas.co.uk/help/size_charts/women-pants_shorts). Not verified as India charts |
| Levi's | Men's/women's shirts, tees and jeans | [US official guide](https://www.levi.com/US/en_US/info/sizeguide). Waist labels are not literal body waist measurements; denim inseam is selected separately |
| H&M | Women's blouses, dresses, trousers and skirts | [Official Kosovo guide](https://www.hm.com/xk/customer-service/sizeguide/ladies/), EUR numeric labels. Not India-market equivalence |

Sizing-only categories such as kurta do not expand the inference model's category
support. Source inseam endpoints can differ (ankle versus floor), so measurement
instructions flag that distinction. The score is not a probability, calibrated
accuracy or a prediction of garment drape. The second-ranked chart match is shown
for comparison; it is not blindly described as a guaranteed comfortable alternative.

**Missing reliable imported scopes:** India Adidas; India Levi's/H&M; Allen Solly,
Peter England, Van Heusen, Louis Philippe, Raymond, Biba, W, Fabindia, Aurelia,
Libas, Max Fashion India, Zudio, Zara, Uniqlo, U.S. Polo Assn., Tommy Hilfiger,
Calvin Klein and remaining directory brands. No values were invented. Existing
India source notes document dynamic/inaccessible guides and garment-only data.
Libas' accessible general page did not supply an importable numeric table;
Biba's accessible staging/other-market guides were not treated as verified India
production data. Further product-specific research and chart-owner review remain.

## Bugs found and fixes

- Guest inference remained enabled: enforced account dependencies on the real API
  and frontend route; retained private ownership for old saved assets.
- Windows returned WebP as `application/octet-stream`: explicit image MIME types
  now work with `nosniff`, verified for every catalog image endpoint.
- MongoDB refused an index because free disk was below its 500 MiB threshold:
  removed only disposable audit/install/bytecode caches. Preserved uploads, model
  weights, result files and database data. Free space must be monitored in deployment.
- Clean-container catalog would miss its JSON manifest: added Docker COPY.
- Missing first-start photo assets could become permanently inactive seed rows:
  skip those records and retry until the public assets are restored.
- All six measurements were required even for a three-metric chart: UI and payload
  now use the selected chart's active subset. Values stay in centimetres internally.
- Size-chart UI assumed India for all guides: explicit country, source and sizing
  system now follow each immutable chart record.
- Browser test signup churn hit valid abuse limits: reuse real rotating sessions
  per suite; production throttles remain unchanged.
- A test captured cookies before page-reload refresh completed: wait for the
  restored signed-in page. Live inference tests now have separate artifact/report
  directories so concurrent suites cannot delete each other's trace files.

## Verification and remaining release gates

On 26 October: **652 regression tests passed**, plus **3 CPU checkpoint integration
tests passed**. Ruff, strict TypeScript/Vite production build, `pip check` and
the 51-image checksum restoration check passed. **28 browser regression tests
passed**, plus **one real private-Colab browser test**. Authentication is real;
controlled outage/rendering tests intercept inference transport and do not claim
model quality. The explicit live test submits only one saved idempotent job.

Commands executed (Python commands from repository root; npm commands from frontend):

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests -m 'not integration' -q --disable-warnings --maxfail=6` | 652 passed; 3 integration cases deselected |
| `.venv/Scripts/python.exe -m pytest tests -m integration -q --disable-warnings` | 3 passed using the actual CPU pose checkpoint |
| `.venv/Scripts/python.exe -m ruff check backend/app tests scripts/download_catalog.py` | Passed |
| `.venv/Scripts/python.exe -m pip check` | No broken requirements |
| `.venv/Scripts/python.exe -m scripts.download_catalog` | All 51 local source/optimized asset records verified |
| `npm run build` | Strict TypeScript and Vite production build passed, 183 modules |
| `npx playwright test vastraview.spec.ts fashion-platform.spec.ts studio.spec.ts online-tryon.spec.ts job-recovery.spec.ts results-comparison.spec.ts --max-failures=3` | 28 passed, 1.7 minutes; no skipped cases |
| `npx playwright test private-tryon-live.spec.ts --reporter=list --output=test-results-live` with `VASTRAVIEW_LIVE=1`, `VASTRAVIEW_LIVE_CASE=fashion-upgrade` | 1 passed; resumed the saved successful job after an initial parallel trace-directory collision; no second inference |
| `npx prettier --check` on changed TS/TSX/config files; `git diff --check` | Passed |

Browser coverage includes all 57 image URLs, product category/color filtering,
unsupported outfit handling, unit conversions and chart markets, actual signup,
login and return URLs, account deletion, refresh rotation, private saved scans,
measurement extraction, sizing, failed/hanging health checks, job recovery, stale
selection changes, equal-sized comparisons, slider, retry, details, sharing and
downloads. Hero/catalog views were checked at 375, 768 and 1440 px; measurements
also at 3840 px. Accessibility checks and no-horizontal-overflow checks passed.
Captured screens are in `experiments/vastraview/` and `experiments/frontend-studio/`.

The automatic connection recovered the existing private notebook and verified its
T4 worker. Fresh job `51c51dad-e812-4545-83ea-3c0d8986c6f1` used unchanged FASHN
VTON 1.5 settings: FP16, 10 steps, guidance 1.5, seed 42, 576 × 864 model canvas.
The output is 800 × 1200, from the actual studio-person and sage-polo inputs.
Measured API processing: **34.837 seconds**; GPU generation: **22.696 seconds**.
The owner can retrieve the result/history; an unauthenticated client gets 401.
Download bytes match the generated PNG, and reload/health failure preserve the
saved render without another inference POST.

Full-resolution visual review found the same identity, pose, hands, jeans, shoes,
background, sage color, collar and short sleeves, with no obvious beige-shirt
fragments or blue artifacts. Checked face/hair, lower-leg/shoe and outer-background
regions have zero changed pixels. The two-button placket and fine pique texture
are softened/lost; sleeves/hem are looser and longer than the reference. This is
not exact garment reconstruction or proof of physical fit. See
`experiments/vastraview/private-tryon-fashion-upgrade/visual-review.json` and
`after.png`. These private local artifacts are not published catalog imagery.

Final live health: frontend HTTP 200; `/api/v1/health/ready?capability=all` HTTP
200 with PostgreSQL/MongoDB and measurement/try-on capabilities available;
`local_gpu_used=false`. Availability describes that check, not a future guarantee.

Primary modified areas: `HomePage.tsx`, `features/catalog/`, `GarmentPicker.tsx`,
`features/sizing/`, `backend/app/catalog.py`, the anthropometry schemas/repository,
`main.py`/private auth dependencies, `data/catalog/garments-v2.json`, sourced chart
and brand manifests, `scripts/download_catalog.py`, API Dockerfile, API/browser
regressions and deployment documentation. This continuation additionally fixed
comparison-unit display, selector labels, session test races and Docker catalog
packaging; the model and image-processing code were left unchanged.

Production review still requires live SMTP verification/reset delivery, HTTPS
cookie verification on the actual domain, a successful Docker deployment, database
least-privilege credentials, backups/restore and retention scheduling, commercial
inventory, higher-resolution retail imagery, and stable GPU capacity. The existing
protobuf/MediaPipe advisory and dependency migration gate remain documented in
`vastraview-deployment.md`. This work does not certify the platform production-ready
or promise an always-available free Colab GPU or a sub-30-second latency SLA.

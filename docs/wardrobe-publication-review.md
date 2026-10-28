# Wardrobe publication review - 28 October 2026

**Approved: 0 of 20. Excluded from the active catalog: 57.** The requested quality threshold was not met. The active wardrobe is intentionally empty; it does not contain unreviewed filler. User uploads, private saved results and sizing remain separate from catalog approval. No source asset, product record, favorite record, account or private photo was deleted.

## Evidence and limits

**Photography follow-up:** [Catalog photography review](catalog-photography-review.md) records the separate display/reference implementation, four new licensed studio candidates and five additional real Colab trials. None earned complete approval. The 57 original IDs below are unchanged; these new trials are reported separately from the original baseline totals.

- Audited 57 original references: 46 supported, commercially usable candidates, five unsupported draped/multipart references and six research references without established commercial image rights.
- 71 actual standard-profile trials across all 46 supported candidates: 46 original-reference trials, 24 controlled background-only trials and one separate retry. 68 outputs generated and visually inspected; three requests failed. Original-reference trials: 44 generated failures of visual acceptance, one rejected for excessive coverage change and one connection failure.
- Three single-person visual passes in controlled background-only experiments do not qualify: each failed on the other fixed person. The production catalog still uses the original reference bytes. Experiments were not silently substituted.
- End-to-end observed generation time: **26.422 to 37.649 seconds**; **33 of 68** generated standard-profile cases were strictly below 30 seconds. Audit transfer follows generation and is not included in that metric. Worker preprocessing, GPU generation and postprocessing remain separately recorded.
- Both fixed people must pass reference fidelity, anatomy, boundaries and preservation ratings of at least 4/5, without major artifacts, plus valid masks/provenance and the strict timing target. A single critical failure prevents approval; additional expensive person runs were not repeated for already-failed references.
- Six historical outputs still lack some expired-runtime parser/conditioning artifacts. Missing evidence never counts as approval. A separate earlier 20-step diagnostic took 55.846 seconds and failed appearance review; it is not included in these 71 trials. Production weights, seed, guidance, masks and ten-step configuration were not changed to improve the score.

## Final approval list and distribution

No approved IDs or categories. The shortfall is **20 garments**. Every rejected or unverified source remains archived with its actual failure evidence. None can be represented as fitting every person perfectly.

## All source garments and exclusions

Counts below include saved controlled experiments, not just the original-reference trial. "Visual passes" are individual images, not garment approvals. All rows remain excluded. Exact per-case inputs, before/after images, masks, full review notes and timings are in the private evidence links below.

| ID | Garment | Category | Trials / generated / single-image visual passes | Observed seconds | Exclusion evidence |
| --- | --- | --- | --- | --- | --- |
| `edit-29864eb0` | Charcoal single-button blazer | jacket | 1 / 1 / 0 | 29.877 to 29.877 | General dark blazer silhouette transfers, but pinstripes, buttons and pocket detail disappear. Pale wrist slivers and a changed elongated inner-shirt hem remain. Too much construction/detail loss for approval. |
| `edit-644a1b3b` | Black tailored blazer | jacket | 1 / 1 / 0 | 29.853 to 29.853 | Black blazer silhouette transfers but buttons and pocket detail disappear, the scalloped hem changes, and an invented white inner top with a double collar replaces the beige shirt. Cuffs have uneven cutout boundaries. |
| `edit-98ec0a37` | Ivory tie-neck blouse | blouse | 2 / 2 / 0 | 26.422 to 28.436 | The sleeveless ivory tie-neck blouse is replaced with an invented tan-and-cream long-sleeve sweatshirt/coat, including a tag-like chest graphic and extra neckline. Wood background becomes tan fabric. Reference sleeveless construction is not transferred. |
| `edit-1347965a` | Blue floral blouse | blouse | 1 / 1 / 0 | 34.079 to 34.079 | Blue floral reference becomes a floral vest over invented peach sleeves, high neck and exposed hem layer. Tie-neck construction is lost; sleeves and hem are jagged. Face, hands, jeans, shoes and surrounding background retained. Severe reference/background contamination; rejected without rerunning another person. |
| `edit-2827caf7` | Lilac collared blouse | blouse | 1 / 1 / 0 | 28.532 to 28.532 | Lilac embellished-collar blouse becomes a colour-block top with olive sleeves, a beige shoulder patch and a V-neck. Collar jewels, fabric detail and side tie are missing. It does not match the reference. |
| `edit-9568b507` | Black button-front blouse | blouse | 2 / 2 / 0 | 28.439 to 30.606 | Black blouse gets different short sleeves and simplified design; unwanted white underlayer at hem. |
| `edit-ddfd02ed` | Black pleated sleeveless dress | dress | 1 / 1 / 0 | 29.768 to 29.768 | Black dress appears as a narrow tunic over jeans; shoulder wings, pale boundary and distorted arm transition; original dress silhouette lost. |
| `edit-0d3cf39f` | Burgundy panel dress | dress | 1 / 1 / 0 | 30.891 to 30.891 | Reference appears to show a zip/back panel; output has shorter loose lace sleeves and a split tunic hem over changed dark upper trouser legs, not the continuous dress silhouette. Neckline and zip/panel construction are inaccurate. Identity retained but lower-body clothing is partially changed. Unsuitable reference orientation/construction and model output; rejected. |
| `edit-55694d05` | Graphic monochrome dress | dress | 1 / 1 / 0 | 35.536 to 35.536 | Monochrome dress becomes a short T-shirt with a beige inner neckline and black hanger-like neck lines. Sleeve-edge pale remnant, distorted stripe geometry and lost dress length. Face/hair/hands/shoes and most jeans retained; this is not the supplied dress. |
| `edit-3f844e1e` | Blue gingham sleeveless dress | dress | 1 / 1 / 0 | 30.511 to 30.511 | Blue dress becomes a short top over black trousers; shoulder remnants and jagged outer-leg fragments; major silhouette failure. |
| `edit-b769e3fb` | Burgundy sleeveless dress | dress | 1 / 1 / 0 | 30.480 to 30.480 | Burgundy dress becomes a short top with yellow artificial sleeves and hem plus black/blue trouser sections; background contamination. |
| `edit-331737f8` | Grey color-block zip hoodie | sweater | 1 / 1 / 0 | 32.822 to 32.822 | Grey/black zip hoodie becomes an open vest with brown padded sleeves, a beige inner shirt, invented buttons and a changed collar/hood. Printed tag/logo and original cuff details are lost; wrist and shoulder edges jagged. Face, hands, jeans and background preserved. Strong background-to-fabric contamination, not a faithful hoodie transfer. |
| `edit-6edf8ea5` | Ivory zip hoodie | sweater | 2 / 2 / 0 | 30.495 to 34.799 | Ivory zip hoodie becomes a brown open coat with multiple pale inner layers. Hood, zipper and pockets are lost; wrist boundaries have pale streaks. The brown floor appears as unwanted garment colour. |
| `edit-d5964c78` | Powder-blue pullover hoodie | sweater | 1 / 0 / 0 | Not measured | Could not retrieve a valid result from the existing Colab worker. Reconnect its GPU runtime; local GPU inference is disabled. (Run 1d905592-2ab5-4ee6-83d8-600cc8d389c1) |
| `edit-febe9c7c` | Teal round-neck long-sleeve top | sweater | 2 / 2 / 0 | 28.512 to 30.212 | Round-neck top becomes collared button jacket over white long layer; original design not preserved. |
| `edit-9e19f45b` | Beige ribbed turtleneck | sweater | 1 / 1 / 0 | 34.435 to 34.435 | Ivory cable-knit turtleneck becomes a tan ribbed hoodie with plain brown sleeves. Rolled neck and diagonal cable construction disappear; a pointed left shoulder artifact and ragged wrists remain. Identity and lower clothing/background retained, but garment is a different design. |
| `edit-8648f194` | Burgundy ribbed sweater | sweater | 3 / 3 / 1 | 28.510 to 32.139 | Plain burgundy ribbed sweater becomes a pink/grey striped long top. Grey blanket is transferred as sleeves and torso bands; neck edge, hem length and fabric pattern are wrong. Background-only studio pass was not repeatable on the mirror person. |
| `edit-6b519a8a` | Pink zip-front jacket | jacket | 1 / 1 / 0 | 31.844 to 31.844 | Pink and printed shoulder motifs transfer, but the zipped jacket becomes open and shorter, pocket graphic is distorted, cuffs lose their construction and a white inner top replaces the original beige shirt. |
| `edit-d039bfd4` | Black padded jacket | jacket | 2 / 2 / 0 | 28.488 to 31.817 | Black padded jacket becomes shorter and open. Generated white cuffs and an unrelated printed inner top replace the original plain beige shirt. Quilting and closure do not match; wrist transitions are jagged. |
| `edit-c7ef3028` | Beige belted trench | jacket | 1 / 1 / 0 | 37.649 to 37.649 | Long double-breasted trench becomes a short open shirt/jacket over an invented beige underlayer with tan sleeve extensions. Coat length, cuff tabs, belt/pockets and button layout are missing or altered. Jagged/floating wrist edges and pale right-side strip. Identity and jeans/shoes/background retained, but not the supplied coat. |
| `edit-122f0c94` | Grey cropped trousers | trouser | 2 / 2 / 0 | 28.533 to 30.252 | Generated lower body remains blue denim-looking full-length trousers instead of the uploaded grey cropped trousers. No credible transfer of the reference silhouette, grey colour or cropped hem. Face, original upper garment and background remain intact. |
| `edit-9b94e20c` | Olive chinos | trouser | 1 / 1 / 0 | 31.697 to 31.697 | Olive color transfers but chino texture and construction are oversmoothed; distinct black/blue seam around preserved shirt hem. End-to-end exceeds 30 seconds. |
| `edit-d92f1cf7` | Light-blue jeans | jeans | 2 / 2 / 0 | 30.186 to 31.718 | Output remains almost the original dark blue jeans rather than reference light-blue jeans. Readable output does not establish transfer. |
| `edit-271405dc` | Indigo jeans | jeans | 2 / 2 / 0 | 28.861 to 30.183 | Invented pale knee bands and missing denim construction; false cuff boundaries on both legs. |
| `edit-c4010e8b` | Navy printed leggings | trouser | 3 / 2 / 0 | 28.482 to 28.564 | Generated black full-length trousers lose the reference navy/white fine print and fitted leggings construction. A thin blue-black outline and duplicate pale strip follow the source T-shirt hem. Lower-body color changed but the actual reference appearance is not preserved. |
| `edit-807f09b8` | Black straight trousers | trouser | 2 / 2 / 0 | 28.557 to 32.607 | Plausible black trousers but smooth tight fit changes reference silhouette; thin black/blue seam at shirt hem. End-to-end exceeds 30 seconds. |
| `edit-65550f31` | Blue pleated trousers | trouser | 1 / 1 / 0 | 31.670 to 31.670 | Full-length blue trousers become shorts with exposed knees, pale cuffs and original jeans below; major construction failure. |
| `edit-a59f077d` | Forest-green polo | t-shirt | 3 / 3 / 1 | 26.525 to 36.560 | Green polo color transfers, but invents beige long undersleeves and an extra beige hem. Unrequested layered outfit. Background-only studio pass was not repeatable on the mirror person. |
| `edit-1b2a7169` | Black short-sleeve polo | t-shirt | 2 / 2 / 0 | 26.440 to 26.519 | Black polo becomes an open outer layer over white long sleeves and a striped inner collar; hanger/reference contamination. |
| `edit-934c4462` | White microprint shirt | shirt | 2 / 2 / 0 | 28.481 to 32.165 | White microprint shirt replaced by unrelated red hooded garment; sleeve, collar and color are wrong. |
| `edit-4758e641` | Olive short-sleeve shirt | shirt | 1 / 1 / 0 | 26.426 to 26.426 | Mandarin shirt becomes an open short jacket over a white long-sleeve underlayer; neckline and construction incorrect. |
| `edit-b4b507dd` | Orange checked shirt | shirt | 2 / 2 / 0 | 28.082 to 28.503 | The generated result is a mustard long-sleeve top carrying a small picture of the orange checked shirt, including the floor-colored background, rather than wearing the reference shirt. Collar, opening and fabric construction are wrong; cuffs have jagged hand boundaries. |
| `edit-b070e185` | Silver-grey formal shirt | shirt | 1 / 1 / 0 | 28.597 to 28.597 | Silver shirt photograph appears printed on an invented red sweatshirt. Background color is treated as garment. |
| `edit-fe7ca6a3` | Grey button-front shirt | shirt | 2 / 2 / 0 | 27.631 to 30.581 | Grey shirt transfers with plausible folds but loses source pattern and has a separate pale hanging hem and altered sleeve cuffs. |
| `edit-4245ab7f` | Teal short-sleeve shirt | shirt | 3 / 3 / 1 | 26.607 to 34.780 | Teal shirt becomes open overshirt with pale long sleeves and extra pale hem. Reference sleeve length not preserved. Background-only studio pass was not repeatable on the mirror person. |
| `edit-1417c271` | Powder-blue athletic shorts | shorts | 1 / 1 / 0 | 28.563 to 28.563 | Athletic shorts become long brown trousers with leftover blue denim cuffs at both ankles. Reference pale-blue colour, green piping and short hem are absent. A black/blue seam and green patch remain beneath the original T-shirt. Upper body, face and background are preserved, but reference transfer fails. |
| `edit-66f92907` | Grey chino shorts | shorts | 1 / 1 / 0 | 30.461 to 30.461 | Grey shorts not transferred: output still shows full-length blue jeans; false dark seam below shirt. |
| `edit-39a96b4e` | Blue and lime sports shorts | shorts | 2 / 2 / 0 | 28.644 to 30.527 | Blue/lime shorts absent: result still contains original full-length blue jeans and no lime design. |
| `edit-29a50158` | Navy A-line skirt | skirt | 2 / 2 / 0 | 30.402 to 30.629 | Navy A-line skirt becomes short split shorts over dark upper trousers and blue lower jeans. Split construction and transitions invalid. |
| `edit-31fd2f8b` | Taupe pencil skirt | skirt | 1 / 1 / 0 | 29.721 to 29.721 | Taupe pencil skirt becomes short split shorts over brown trousers with blue ankle fragments; not the reference skirt. |
| `edit-7ec3c84f` | Mustard pleated skirt | skirt | 1 / 0 / 0 | Not measured | This outfit would expose too much skin hidden by the original clothing. Use a person photo with similar sleeve and hem coverage; the generated result was rejected. (Run ffa37254-77af-4fc2-b80e-3a182023c977) |
| `edit-c103d1a1` | White V-neck T-shirt | t-shirt | 2 / 2 / 0 | 28.512 to 28.634 | White short-sleeve printed T-shirt becomes an ochre long-sleeve open jacket with a beige extra inner top. Wooden floor transfers as outer fabric; reference silhouette, sleeves and colour are not preserved. |
| `edit-80653ab3` | Blue graphic crew-neck tee | t-shirt | 2 / 2 / 0 | 27.765 to 30.698 | Blue graphic transferred approximately; unwanted white hem layer and neckline ring remain; graphic lettering changes. |
| `edit-9b76f08a` | Grey ribbed crop top | blouse | 1 / 1 / 0 | 28.485 to 28.485 | Grey sleeveless ribbed crop top becomes a grey vest over an invented magenta long-sleeve layer derived from the blanket background. Neckline and hem are distorted, shoulder edges float, and cuffs are jagged. Actual parser reaches the image border, so automatic background-only preparation was refused. |
| `edit-86f96e47` | Printed tie-front crop top | blouse | 1 / 1 / 0 | 32.761 to 32.761 | Floral short-sleeve tie-front crop top becomes a green long-sleeve zip jacket with an upper printed panel, beige cuffs/inner shirt and grey hem layer. Green wall background has become fabric. Tie front and cropped silhouette disappear; jagged wrist edges. Severe garment mismatch; rejected. |
| `edit-a7a8fafc` | Ivory camisole | blouse | 1 / 1 / 0 | 32.699 to 32.699 | Ivory camisole turns into an apron-like top over an invented tan collared long-sleeve shirt. Strap neckline/lace, crop length and silhouette are lost; black tag-like chest mark and jagged cuff/shoulder edges appear. Identity, lower clothing and background retained. Severe invented clothing, rejected. |
| `editorial-13192043` | Charcoal patterned saree | unsupported | 0 / 0 / 0 | Not measured | Unsupported draped/multipart garment: no supported single-garment category mapping. Not sent to inference. |
| `editorial-28332599` | Black traditional kurta | unsupported | 0 / 0 / 0 | Not measured | Unsupported draped/multipart garment: no supported single-garment category mapping. Not sent to inference. |
| `editorial-22064230` | Peach embroidered kurta | unsupported | 0 / 0 / 0 | Not measured | Unsupported draped/multipart garment: no supported single-garment category mapping. Not sent to inference. |
| `editorial-22064197` | Marigold embroidered three-piece set | unsupported | 0 / 0 / 0 | Not measured | Unsupported draped/multipart garment: no supported single-garment category mapping. Not sent to inference. |
| `editorial-22064213` | Turquoise embroidered kurta set | unsupported | 0 / 0 / 0 | Not measured | Unsupported draped/multipart garment: no supported single-garment category mapping. Not sent to inference. |
| `navy-tee` | Navy crew-neck T-shirt | t-shirt | 0 / 0 / 0 | Not measured | Commercial image rights not established; excluded from this production evaluation. Historical research results are not approvals. |
| `sage-polo` | Sage pique polo | t-shirt | 0 / 0 / 0 | Not measured | Commercial image rights not established; excluded from this production evaluation. Historical research results are not approvals. |
| `navy-blouse` | Navy broderie blouse | blouse | 0 / 0 / 0 | Not measured | Commercial image rights not established; excluded from this production evaluation. Historical research results are not approvals. |
| `coral-dress` | Coral ruched dress | dress | 0 / 0 / 0 | Not measured | Commercial image rights not established; excluded from this production evaluation. Historical research results are not approvals. |
| `navy-gown` | Midnight evening dress | dress | 0 / 0 / 0 | Not measured | Commercial image rights not established; excluded from this production evaluation. Historical research results are not approvals. |
| `ivory-skirt` | Ivory tiered skirt | skirt | 0 / 0 / 0 | Not measured | Commercial image rights not established; excluded from this production evaluation. Historical research results are not approvals. |

## Private evidence

- [All trial timings and model/input fingerprints](../experiments/wardrobe-review/summary.json).
- [Before/reference/after comparisons with review notes](../experiments/wardrobe-review/comparisons.html). These are local private evidence, not publicly served assets.
- [Per-person baseline evaluation and remaining gates](../experiments/wardrobe-curation/report.md).
- [Archive made before publication](../experiments/wardrobe-curation/catalog-archive-20261028T085333426589Z.json): all source records, evaluations and the previous publication manifest.
- [Enforced publication manifest](../data/catalog/wardrobe-approved-v1.json).
- [Model, acceptance criteria and reproducible commands](wardrobe-curation.md).

## Implementation

- At most 20 verified IDs are published; an explicit `quality_shortfall` permits fewer without weakening approvals. Malformed publications fail closed. Changed source bytes, categories or photo type invalidate approval.
- Listings, search, facets, categories/counts, favorites, details, current and legacy image routes, and product-bound inference submissions all apply the publication policy. Database/source records are retained. Public image responses revalidate instead of serving hour-old archived content.
- The collection and garment picker explain the shortfall. Empty categories are omitted. The sample-photo action cannot reintroduce a rejected catalog garment; it loads the person and requests an uploaded supported garment when none is approved.
- The compact result viewer keeps real saved image URLs, alignment, slider, inspect/share/download controls and privacy. Catalog removal does not delete completed results.

## Validation

Backend: `.venv/Scripts/python.exe -m pytest -q` - **743 passed** (141.74 seconds; upstream deprecation/serialization warnings remain). Ruff: `.venv/Scripts/python.exe -m ruff check backend scripts tests` - passed. Frontend: `npm run build` - TypeScript and Vite passed (183 modules). **34 browser regressions passed**, followed by a passing final catalog check after the mobile notice adjustment, against the running app (catalog exclusions, uploads, authentication, sizing, measurement uncertainty, comparison interactions, downloads and simulated GPU outages). The 34-test report is preserved in `experiments/wardrobe-review/browser-regression-34.json`. A separate live saved-result check failed because the evaluation-account session was no longer accepted and the browser redirected to sign-in. It did not establish a new private-file/download pass. All 68 local output hashes remain intact. No ownership checks were bypassed to recover access.

## Changed files

- Publication: `data/catalog/wardrobe-approved-v1.json`, `wardrobe-candidates-v1.json`, `scripts/curate_wardrobe.py`; publication/access guards in `backend/app/wardrobe.py`, `catalog.py`, `garments.py` were completed during this continuation.
- UI: `frontend/src/features/catalog/CatalogPage.tsx`, `catalog.css`, `frontend/src/features/tryon/GarmentPicker.tsx`, `TryOnStudio.tsx`.
- Regression coverage: `tests/test_wardrobe_publication.py`, inventory fixtures in `test_garment_catalog.py`/`test_vastraview.py`, `frontend/e2e/curated-catalog.spec.ts`, upload fixture and existing catalog/comparison/recovery suites.
- Reports: this document, `docs/wardrobe-curation.md`, `docs/implementation-status.md`, and preserved private evaluation/browser evidence.

## Remaining work

The production model still invents layers, loses garment construction and produces boundary artifacts on these references. The 20-item quality objective is not achieved. Approving a wardrobe requires new successful evidence using suitable licensed references and repeatable multi-person results; broad category support is insufficient. No paid service, local GPU inference, model replacement or threshold relaxation was introduced. At the final health check, the local API, databases and existing Colab worker were Ready; no fresh generation was submitted for the saved-result check. A free Colab worker can expire. Saved files remain on disk independently of GPU availability, and accessing private results requires a valid owner session.

Suggested commit: `Enforce evidence-backed wardrobe publication and archive failed garments`

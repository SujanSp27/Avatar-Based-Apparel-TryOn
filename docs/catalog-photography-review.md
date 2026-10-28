# Catalog photography and reference review — 28 October 2026

## Outcome

**Existing product images replaced: 0. Production approvals: 0 of 20.** The archived 57 IDs are preserved. None has a verified, licensed studio photograph of the *same* garment that can safely replace its image. Assigning a different Ralph Lauren or Nike product to an anonymous archived garment would corrupt identity and favorites. Every existing ID is explicitly flagged in `data/catalog/image-replacement-review-v1.json`.

This update implements separate display and inference assets, sources four new studio candidates, and tests them on the existing private Colab worker. It does **not** claim the requested collection is complete. Cleaner photography improved one transfer, but none of the four candidates passed the complete, unchanged approval criteria. The Discover Apparel page continues to report the actual shortfall instead of publishing failures.

## Implemented image mapping

| Use | Stored data | Public API |
| --- | --- | --- |
| Cards, search, favorites, details, garment-picker cards | Optional `display_image.filename`; otherwise existing `filename` | `imageUrl`, `/api/v1/products/{id}/image` |
| Actual inference input and source quality hash | Existing `filename` and `photoType` | `referenceImageUrl`, `/api/v1/products/{id}/reference-image` |
| Display attribution | `display_image.source_url`, `license`, `license_url`, `attribution`, optional `attribution_url` | `displayImage`, with local filename omitted |
| Reference attribution | Existing `source_url`, `license`; optional license/photographer URLs | Existing product fields |

Both image routes enforce the same publication and production-license restrictions. Changing display bytes does not grant or invalidate inference approval; changing reference bytes still makes its approval stale. A display checksum mismatch fails closed. Admin updates validate paths, content, size, source metadata and checksum. Omitting the optional display field preserves an existing operator-curated display image; explicit `null` restores reference-image display. IDs and favorite relationships are not rewritten.

Try-on selection downloads `referenceImageUrl`; compatibility fallback to `imageUrl` applies only to older API records lacking the new field. A failed reference request never falls back to another picture. The existing neutral, responsive `object-fit: contain` cards remain. Details show distinct display attribution and an expandable reference preview when two images are configured.

## Source inspection

Twelve new source records were investigated; eleven downloaded photographs were opened and visually inspected. One original remained rate-limited. The host's published 960px renditions were available and are pinned by SHA-256. Garment pixels were not repainted, cut out, stretched or replaced. Files are local, not hotlinked.

| Source | License and attribution | Decision |
| --- | --- | --- |
| [Ralph Lauren multicolor shirt](https://commons.wikimedia.org/wiki/File:Multi_Color_Polo_Ralph_Lauren_Shirt.jpg) | CC BY 2.0, Robert Sheie / Menswear Market | Complete front mannequin view; tested, failed detail/boundary review |
| [Dale of Norway sweater](https://commons.wikimedia.org/wiki/File:Dale_of_Norway_sweater.jpg) | CC BY 2.0, Menswear Market | Clean product photo; crossed sleeves caused incorrect transfer |
| [Ralph Lauren patch sweater](https://commons.wikimedia.org/wiki/File:Polo_Ralph_Lauren_Gun_Patch_Sweater_(13973497074).jpg) | CC BY 2.0, Robert Sheie / Menswear Market | Clean product photo; crossed sleeves/patches caused extra fabric shapes |
| [Rare By Circle classic logo tee, front](https://commons.wikimedia.org/wiki/File:Rare_By_Circle_Classic_Logo_T-Shirt.jpg) | CC BY-SA 4.0, Badislavius | Studio person visual pass; mirror-person failure; not approved |
| [Paul Smith striped shirt](https://commons.wikimedia.org/wiki/File:Paul_Smith_striped_shirt.jpg) | CC BY 2.0, Robert Sheie | Professional folded display photo; no complete matching inference reference |
| [Fred Perry polo](https://commons.wikimedia.org/wiki/File:Fred_Perry_polo.jpg) | CC BY-SA 4.0, Francesc Fort | Folded with tags; incomplete silhouette |
| [Ralph Lauren Stadium shirt](https://commons.wikimedia.org/wiki/File:Polo_Ralph_Lauren_Stadium_shirt,_short_sleeves.jpg) and [second view](https://commons.wikimedia.org/wiki/File:Ralph_Lauren_Stadium_shirt,_short_sleeves_2.jpg) | CC BY 2.0, Menswear Market | Oblique side and back, not two products or acceptable front references |
| [Madras shirt](https://commons.wikimedia.org/wiki/File:Polo_Ralph_Lauren_Madras_plaid_shirt.jpg) | CC BY 2.0, Menswear Market | Original HTTP 429; not inspected or approved |
| [Classical polo](https://commons.wikimedia.org/wiki/File:Classical_polo_shirt.jpg) | CC BY-SA 3.0, Elkagye | Casual carpet photograph and uneven illumination; rejected |
| [Rare tee second image](https://commons.wikimedia.org/wiki/File:Rare_By_Circle_Classic_Logo_T-Shirt_1.jpg) | CC BY-SA 4.0, Badislavius | Back view of the same garment, excluded from front reference selection |
| [Cropped Wikipedia polo](https://commons.wikimedia.org/wiki/File:WP_polo_shirt_FRONT_Merchandise_shots-24_cropped.jpg) | Derivative claims CC0; source has CC BY-SA 3.0 and trademark notice | Conflicting license metadata and non-studio background; excluded |

These are licensed seller/contributor photographs, not official brand partnerships or verified inventory. No current stock, available sizes or fabricated product codes were added. The Rare brand's [own collection](https://rarebycircle.com/product-category/t-shirts-longsleeves/) was checked for brand context; the exact photographed reference identity and photo license are recorded from Commons, not inferred from a similar current listing.

Attribution and source/license links must accompany publication. Menswear Market requests a link to [the original seller](https://www.menswear-market.com/). CC BY-SA imagery requires compatible ShareAlike terms for publicly distributed adaptations; these trials remain private. Photo reuse permission is not endorsement or authentication of physical merchandise.

## Actual inference, unchanged production profile

FASHN VTON 1.5, private Colab Tesla T4, FP16, 576 × 864, 10 steps, seed 42, guidance 1.5. Source `7c0f10af3f91ad4048fe9729c470a13ef905d25a`; weights `7720683168567eb5a2a4c67f15116c6e29c83ded`. Existing preprocessing, category mapping, dark-fabric reference preparation and preservation logic were used unchanged. No local GPU, alternate inference provider, model download or extra training.

| Candidate ID | Person | Server seconds | Observed end-to-end seconds | Visual result |
| --- | --- | ---: | ---: | --- |
| `studio-rl-multicolor-shirt` | studio | 40.420 | 42.549 | Lost chest pocket, changed collar/buttons, imperfect cuffs; failed |
| `studio-dale-nordic-sweater` | studio | 35.717 | 38.176 | False short sleeves, neckline, pockets and extra hem layer; failed |
| `studio-rl-patch-sweater` | studio | 35.437 | 39.119 | Crossed sleeve/cuff shapes copied across torso, detail loss; failed |
| `studio-rare-classic-logo-tee` | studio | 34.368 | 36.350 | Visual pass with minor logo softening; timing failed |
| `studio-rare-classic-logo-tee` | mirror | 34.869 | 38.431 | Jagged collar/neckline and arm-preservation boundaries; failed |

All five outputs were inspected at full resolution against the actual reference and person. Output dimensions matched their inputs. All worker masks and conditioning artifacts were retrieved. Timings end when the result is retrieved; diagnostic transfer is separate. None met the strict under-30-second target. Already-failed folded garments were not rerun on a second person just to increase coverage.

The saved raw mirror-person output and final composite were also compared: the raw model alters the phone/hands and softens the face; the preservation composite restores original details but creates jagged neckline/forearm transitions where they do not align. Showing the raw output would violate identity/accessory preservation. This is an observed generation/compositing limitation, not a catalog URL error. The five-case mask/conditioning contact sheet is saved privately as `experiments/wardrobe-brand-sourcing/mask-inspection.jpg`.

Worker-only timing is retained separately in each `trial.json` under `diagnostics.stageSeconds`. For example, the multicolor shirt used 2.627 seconds preprocessing, 26.123 seconds generation and 1.109 seconds postprocessing/saving. The remainder of end-to-end time includes transport and application work; it must not be represented as GPU generation time.

## Assets and reproducibility

- Four source JPEGs: `data/raw/catalog-studio/` (gitignored public assets).
- Pinned source/usage records: `data/catalog/studio-candidates-v1.json` and `studio-candidates-v2.json`.
- Every new source decision: `data/catalog/studio-image-review-v1.json`.
- Before/reference/after, original source bytes, hashes, masks, tensors, timings and visual reviews: `experiments/wardrobe-studio-v1/` and `experiments/wardrobe-studio-v2/` (private; never publicly served).
- Source metadata and consolidated timings: `experiments/wardrobe-brand-sourcing/`.

Restore pinned public assets with `python -m scripts.download_catalog --manifest data/catalog/studio-candidates-v1.json` (repeat for v2). This does not publish products. Source changes or local edits stop restoration instead of overwriting them. `evaluate_wardrobe --source-manifest` evaluates staged records without changing catalog IDs; its saved source manifest is immutable. `curate_wardrobe report --source-manifest` applies the existing acceptance gates to staged trials. Publication through that staging option is explicitly refused.

The candidate manifests are snapshots from before inference; their initial `pending_inference` field does not override the subsequent source-review ledger or trial reports. Current decisions are in `studio-image-review-v1.json` and the two generated `report.json` files. No candidate manifest is included in the production seed.

## Verification executed

- `.venv/Scripts/python.exe -m pytest tests -q --disable-warnings --tb=short`: **748 passed**, 1591 warnings, 292.14 seconds. This full run started before the three staging tests were added.
- Final targeted suite: `pytest tests/test_catalog_images.py tests/test_catalog_staging.py tests/test_wardrobe_curation.py tests/test_fashion_catalog.py -q --disable-warnings`: **28 passed**, including the three new staging tests and the final checksum guards.
- `.venv/Scripts/python.exe -m ruff check backend scripts tests`: passed.
- `npm run build`: TypeScript and Vite passed; 183 modules.
- `playwright test --grep-invert 'saved wardrobe trials|live neural job|fresh upload|real private Colab result|existing private Colab connects'`: **37 passed**. Covers auth, measurements, sizing, catalog exclusion, favorites, image loading, desktop/tablet/mobile layouts, comparison controls, recovery and failures. Inference transport tests use explicit fixtures; they are not garment approvals.
- Three new browser regressions verify exact reference bytes/category/ID in multipart submission, no display-image fallback after a missing reference, and display/reference attribution and responsive layout. No browser page error was accepted as success.
- Five actual Colab inferences completed separately, reviewed above. No mocked result counts toward those five.
- Opt-in `wardrobe-live.spec.ts`, using the new evaluation session and three completed v1 trials: **1 passed**. All three real PNGs loaded after refresh, both comparison modes worked, reference inspection showed the saved garment, downloads matched recorded hashes, mobile layouts had no overflow, guest requests were denied, and no inference POST was submitted. This verifies result transport/rendering, not visual garment approval.
- Reloaded only the local API after jobs completed. OpenAPI includes the new reference route, archived IDs return 404, and frontend HTTP is 200. Database records, frontend process and Colab runtime were not reset.

Modified implementation files: `backend/app/catalog.py`; `frontend/src/features/catalog/CatalogPage.tsx`; `frontend/src/features/tryon/GarmentPicker.tsx` and `TryOnStudio.tsx`; `scripts/download_catalog.py`, `evaluate_wardrobe.py` and `curate_wardrobe.py`; new `tests/test_catalog_images.py`, `tests/test_catalog_staging.py`, `frontend/e2e/catalog-image-mapping.spec.ts`; parameterized `frontend/e2e/wardrobe-live.spec.ts`. New metadata/review records and this report document all sourced assets and exclusions.

Suggested commit: `Separate catalog photography from inference references and audit licensed studio candidates`.

## Remaining work

A complete replacement requires permissioned studio images of the exact archived garments, or separately identified new products with suitable complete front views and passing multi-person reviews. Four new sourced identities cannot legitimately replace 57 unrelated products under their old IDs. The current model's sleeve/detail fidelity and arm-boundary failures still prevent approval. All existing user data and archived evidence remain intact.

# Comparison alignment verification — 24 October 2026

The live viewer's After panel had a 1 px left border. Its 550 px grid cell
therefore contained a 549 px image, while Before used 550 px. `object-fit:
contain` then gave the photographs different scales and exposed a center seam.
The outer border also reduced the available canvas relative to its aspect ratio.
No extra grid column or large wrapper gap was reproduced in the current app.

The frame now uses a non-sizing outline; each image fills an equal, borderless
panel whose ratio comes from the original photograph. Slider mode uses the same
canvas twice with clipping and an absolute 1 px divider centered at the selected
percentage. Photograph rules now live together in `comparison.css`, removing
obsolete fixed ratios, height constraints and child-label selectors from
`studio.css`. No negative margins, cropped people or replacement backgrounds are used.

Matching aspect ratios at different resolutions are supported. Genuinely different
framing gets an explicit error rather than stretching/cropping. The selected mode,
current API result URL, bounded image retry and download/share behavior remain intact.

`male-shorts/` and `female-shorts/` contain retained genuine results and original
images from the requested turquoise shorts cases. Provenance records their run
IDs. They are layout fixtures, not product fallback images or model-quality claims.

Verification: 12 Playwright tests passed; strict TypeScript and Vite build passed.
Tests measure the actual contained image bounds, not just wrapper widths, at
1920, 1440, 768 and 375 px. Both photos have equal width/height/top and their
painted edges meet within 0.05 CSS px. Pointer/keyboard dragging, divider
alignment, resizing, stale-result invalidation, loading/timeout/error/retry,
share, correct downloaded bytes and accessibility are covered.

Screenshots `male-shorts-1440.png` and `female-shorts-375.png` were visually
inspected, along with the fresh blouse result. Console error checks passed.

The actual new private Colab T4 job `f5b254bc-0660-44e0-a0c1-e2689c67cd28`
completed in 31.319 seconds and passed the live viewer test without new inference
from the test itself. Its images, diagnostics, review and browser screenshots are
in `../blouse-fidelity/app-native-fullparse10/`. No local GPU or public image
service was used. Fine garment texture remains approximate and this does not
establish a sub-30-second guarantee.

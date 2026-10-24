# Compact comparison layout

The former width-driven portrait frame reached about 826 px tall side by side
and 1140 px in Slider mode at a 1440 px viewport. The existing component now
derives its maximum width from a 540 px desktop height, the actual photograph
ratio and the selected panel count, within an overall 1100 px maximum.
At tablet widths the height limit is 500 px; narrower viewports shrink naturally.

For the real 800x1200 photographs, the side-by-side image area is 720x540 px
and the slider is 360x540 px on desktop. The bordered card has 12 px padding
around the image and a compact footer. The title and controls sit above it.
Images retain their complete aspect ratio, meet without a center gap and use
the actual existing result URLs. No backend, model, upload or auth changes.

Browser verification uses the retained genuine male/female turquoise-shorts
images and the actual saved blouse job `f5b254bc-0660-44e0-a0c1-e2689c67cd28`.
It does not generate another image. Checks include 3840/1920/1440/768/375 px
layouts, height and width bounds, centering, equal painted image sizes, no center
gap, no slider gutters, header/footer separation, pointer and keyboard dragging,
image retry/switching, download bytes, sharing, zoom and accessible controls.

Screenshots in this directory record the compact layout; original alignment
screenshots remain in `../comparison-alignment/`.

25 October continuation: the final slider shrinks to the same 12 px image
padding as Side by side. Its action bar keeps Inspect details left and Share /
Download right on one desktop row; mobile actions use readable full-width rows.
The app and existing databases were restarted after the interruption. Verification
uses the completed job's saved assets, independently of current GPU availability.

Final verification: all 12 browser tests passed (34.0 seconds), the strict
TypeScript/Vite production build passed (174 modules), Prettier passed and
`git diff --check` reported no whitespace errors. The final slider, desktop
shorts comparison and mobile result screenshots were visually inspected. Both
the app page and the saved real job endpoint were checked after verification.

# Current supported scope

Later user instructions supersede the original 3D plan: 2D images only, online GPU
only, and the existing private Colab notebook only. There is no public third-party
VTON service fallback and no local GPU inference.

- Inputs: one clothed, front-facing person and one garment, garment category,
  and product/flat-lay versus worn-photo type. JPG/PNG/WebP, at least 128 pixels
  per side, below 20 megapixels and 12 MB per upload. Normalized to at most 1200px.
- Tops require a visible face/torso. Bottoms and one-piece garments require a
  visible lower body. Avoid crossed arms, severe occlusion and multiple people.
- Use a source outfit with similar sleeve and hem coverage. Results that reveal
  skin across more than 20% of the replaced clothing region are rejected: the
  model cannot faithfully reconstruct that hidden anatomy from this photo.
- Categories: T-shirt, shirt, blouse, sweater, jacket (tops); trousers, jeans,
  shorts, skirt (bottoms); dress, jumpsuit (one-pieces).
- Output: generated PNG at the normalized person's dimensions, original image
  comparison, actual timings, provenance and downloadable JSON. No mesh/GLB.
- Face, hands and unrelated regions are restored using semantic preservation.
  Parsing errors, unnatural edges and body-shape changes remain possible.
- Size advice is separate: actual user-entered centimetre measurements, selected
  brand chart/category and fit preference. It is not inferred from the generated
  image. Seed brands are explicitly fictional demonstration charts.
- Connection starts automatically with the API. Worker restoration never submits
  an image-generation job. Colab authentication and GPU allocation cannot be bypassed.
- Images go only to the user's private Colab worker. Local inputs/results and
  debugging metadata remain on disk until deleted. Do not share notebook outputs
  or ignored runtime files containing private worker credentials.
- No claim of universal garment support, calibrated physical fitting, or a
  sub-ten-second latency guarantee. All eleven transport mappings are tested;
  visual validation across those categories remains incomplete.

The latest user target (20 October) is **a visually correct result within 30
seconds end to end**, superseding the earlier 10-20 second target. Both image
quality and elapsed time must pass; returning an error after 30 seconds, reducing
steps until the garment is distorted, or reusing a cached result does not meet it.
Cold setup is reported separately. Shared Colab/network delays are measured and
must not be hidden from the request timing.

Evaluation records separate fresh end-to-end latency, worker/model latency,
input identity preservation and visual garment acceptance. Historical 3D
measurements and archived local CUDA runs do not describe the current system.

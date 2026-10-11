"""Conservative checks for catastrophic garment-conditioning loss.

This is not a learned perceptual metric or a general fitting-quality validator.
It only rejects a strongly striped reference becoming nearly textureless. It
abstains on other garments, ambiguous crops, and textured generated garments.
No image pixels are synthesized or changed by these diagnostics.
"""

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class GarmentFidelityResult:
    status: str
    reason: str
    reference: dict
    generated: dict
    version: str = "pronounced-horizontal-stripe-loss-v1"

    @property
    def rejected(self) -> bool:
        return self.status == "rejected"

    def as_dict(self) -> dict:
        return asdict(self)


def _central_fabric(image: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray | None, dict]:
    if (
        not isinstance(image, np.ndarray)
        or image.ndim != 3
        or image.shape[2] != 3
        or image.dtype != np.uint8
    ):
        raise ValueError("Expected a uint8 HxWx3 RGB image")
    if not isinstance(mask, np.ndarray) or mask.shape != image.shape[:2]:
        raise ValueError("Expected a garment mask matching the image height and width")
    if mask.dtype != np.bool_ and not np.issubdtype(mask.dtype, np.integer):
        raise ValueError("Expected a boolean or integer binary garment mask")
    values = set(np.unique(mask).tolist())
    if not (values <= {0, 1} or values <= {0, 255}):
        raise ValueError("Pass a binary garment mask, not a semantic label map")
    ys, xs = np.where(mask > 0)
    if len(xs) < 256:
        return None, {"usable": False, "reason": "too_few_garment_pixels"}
    left, right = int(xs.min()), int(xs.max()) + 1
    top, bottom = int(ys.min()), int(ys.max()) + 1
    width, height = right - left, bottom - top
    # Exclude collars, hems and sleeves. A semantic mask must confirm that this
    # entire central rectangle is fabric; otherwise no decision is justified.
    x0, x1 = left + round(width * 0.325), left + round(width * 0.675)
    y0, y1 = top + round(height * 0.20), top + round(height * 0.85)
    coverage = float(np.mean(mask[y0:y1, x0:x1] > 0)) if y1 > y0 and x1 > x0 else 0.0
    details = {"crop": [x0, y0, x1, y1], "maskCoverage": round(coverage, 5)}
    if x1 - x0 < 24 or y1 - y0 < 64 or coverage < 0.98:
        return None, {**details, "usable": False, "reason": "central_fabric_not_clear"}
    rgb = image[y0:y1, x0:x1].astype(np.float32)
    luminance = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    patch = cv2.resize(luminance, (128, 192), interpolation=cv2.INTER_AREA)
    return patch, {**details, "usable": True}


def _texture_features(image: np.ndarray, mask: np.ndarray) -> dict:
    patch, details = _central_fabric(image, mask)
    if patch is None:
        return details
    smooth = cv2.GaussianBlur(patch, (0, 0), 0.7)
    local = smooth - cv2.GaussianBlur(smooth, (0, 0), 12)
    rows = np.median(local, axis=1)
    rows -= np.mean(rows)
    contrast = float(np.percentile(local, 95) - np.percentile(local, 5))
    row_contrast = float(np.percentile(rows, 95) - np.percentile(rows, 5))
    pixel_rms = float(np.sqrt(np.mean(local**2)))
    row_rms = float(np.sqrt(np.mean(rows**2)))
    coherence = row_rms / max(pixel_rms, 1e-6)
    vertical_change = float(np.mean(np.abs(np.diff(smooth, axis=0))))
    horizontal_change = float(np.mean(np.abs(np.diff(smooth, axis=1))))
    horizontal_stripe_ratio = vertical_change / max(horizontal_change, 0.01)
    power = np.abs(np.fft.rfft(rows * np.hanning(len(rows)))) ** 2
    peak = int(np.argmax(power[4:25])) + 4
    harmonics = np.zeros(len(power), dtype=bool)
    for frequency in (peak, peak * 2, peak * 3):
        harmonics[max(4, frequency - 1) : min(len(power), frequency + 2)] = True
    spectral_share = float(power[harmonics].sum() / max(power[1:].sum(), 1e-6))
    pronounced = (
        row_contrast >= 50
        and coherence >= 0.90
        and horizontal_stripe_ratio >= 5
        and spectral_share >= 0.75
        and peak >= 4
    )
    return {
        **details,
        "localLuminanceContrast": round(contrast, 4),
        "rowLuminanceContrast": round(row_contrast, 4),
        "horizontalCoherence": round(coherence, 4),
        "horizontalStripeGradientRatio": round(horizontal_stripe_ratio, 4),
        "periodicSpectralShare": round(spectral_share, 4),
        "dominantCycles": peak,
        "pronouncedHorizontalStripes": bool(pronounced),
    }


def assess_garment_fidelity(
    reference: np.ndarray,
    reference_mask: np.ndarray,
    generated: np.ndarray,
    generated_mask: np.ndarray,
) -> GarmentFidelityResult:
    """Reject only obvious disappearance of pronounced horizontal striping.

    The two RGB images may have different sizes. Each mask is binary and marks
    only its own garment, not the full inpainting region. No pixel alignment or
    matching stripe count is required, allowing folds, perspective and lighting.
    A non-rejection does not mean the uploaded garment was reproduced correctly.
    Thresholds are conservative engineering heuristics, not calibrated accuracy.
    """
    source = _texture_features(reference, reference_mask)
    target = _texture_features(generated, generated_mask)
    if not source["usable"] or not target["usable"]:
        return GarmentFidelityResult("abstained", "insufficient_clear_fabric", source, target)
    if not source["pronouncedHorizontalStripes"]:
        return GarmentFidelityResult(
            "abstained", "reference_outside_stripe_guard_scope", source, target
        )
    ratio = target["localLuminanceContrast"] / max(source["localLuminanceContrast"], 1e-6)
    target["referenceContrastRatio"] = round(ratio, 5)
    # Reduced exposure can lower contrast without removing the pattern. Any
    # plausible surviving periodic/horizontal structure prevents rejection,
    # even though folds or unrelated texture could also create that evidence.
    retained_structure = (
        target["rowLuminanceContrast"] >= 2
        and target["horizontalCoherence"] >= 0.35
        and target["periodicSpectralShare"] >= 0.40
    ) or (target["horizontalStripeGradientRatio"] >= 1.2 and target["localLuminanceContrast"] >= 3)
    target["possibleRetainedStripeStructure"] = bool(retained_structure)
    # Both an absolute near-flat condition and a severe relative loss must hold.
    # Strong wrinkles, tilted stripes, changed stripe spacing, and ambiguous
    # textures intentionally prevent rejection; they need human evaluation.
    if target["localLuminanceContrast"] < 24 and ratio < 0.22 and not retained_structure:
        return GarmentFidelityResult("rejected", "pronounced_stripes_disappeared", source, target)
    return GarmentFidelityResult(
        "not_rejected", "no_catastrophic_stripe_loss_detected", source, target
    )

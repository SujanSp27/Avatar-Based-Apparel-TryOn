"""Publish actual pretrained try-on results, independently of physical sizing."""

from functools import lru_cache

from backend.app.config import settings
from backend.app.storage import AssetStore
from ml.preprocessing.images import ImageFeatures
from ml.vton.service import PretrainedTryOn


@lru_cache(maxsize=1)
def get_vton() -> PretrainedTryOn:
    return PretrainedTryOn(settings.vton_root, settings.vton_device)


def photo_result(
    store: AssetStore,
    run_id: str,
    person: ImageFeatures,
    garment_data: bytes,
    category: str,
    fit: str,
    fallback_reason: dict | None,
) -> dict:
    folder = store.folder(run_id)
    diagnostics = get_vton().render(person, garment_data, category, folder)
    warnings = [
        "Pretrained CatVTON generates clothing at 384 by 512 pixels. Inspect fine garment details and folds; this research model is not a guarantee of physically accurate fit.",
        "Original face, hair, exposed limbs, lower clothing and background are preserved according to semantic parsing; parsing errors can affect boundaries.",
        "The image model does not estimate body measurements or choose a clothing size. Use measured dimensions with the independent brand size engine.",
        "Fit preference is recorded for sizing, but is not an input to the pretrained image model.",
        "CatVTON and the human-parser weights have research/non-commercial license restrictions; see docs/vton-model.md.",
    ]
    if fallback_reason:
        warnings.insert(
            0, "3D was unavailable for this input; the pretrained 2D try-on model was used."
        )
        store.write_json(run_id, "3d-unavailable.json", fallback_reason)
    names = [
        "tryon-2d.png",
        "original-person.png",
        "vton-diagnostics.json",
        "garment-fidelity.json",
        "vton-model-output.png",
        "vton-replacement-mask.png",
        "vton-person-input.png",
        "vton-garment-input.png",
        "vton-garment-mask.png",
        "personParsing.png",
        "garmentParsing.png",
        "generatedParsing.png",
        "semantic-edit-mask.png",
        "semantic-preserve-mask.png",
        "old-clothing-mask.png",
        "semantic-alpha.png",
        "semantic-composite.json",
        "personMask.png",
        "personCrop.png",
        "garmentMask.png",
        "garmentCrop.png",
        "poseKeypoints.json",
    ]
    if fallback_reason:
        names.append("3d-unavailable.json")
    return {
        "mode": "2d",
        "renderingMethod": "pretrained-vton",
        "fit": fit,
        "recommendedSize": None,
        "score": None,
        "explanation": {},
        "candidates": [],
        "measurements": None,
        "avatarUrl": None,
        "bodyUrl": None,
        "garmentUrl": None,
        "previewUrl": store.url(run_id, "tryon-2d.png"),
        "originalUrl": store.url(run_id, "original-person.png"),
        "fallbackReason": fallback_reason,
        "provenance": {
            "backend": diagnostics["modelVersion"],
            "pretrainedComponent": "CatVTON garment-conditioned diffusion; FASHN SegFormer-B4 human parser",
            "shapeRecovery": "masked garment-conditioned diffusion inpainting",
            "validatedAnthropometry": False,
            "weights": diagnostics.get("model", {}),
        },
        "warnings": warnings,
        "fitting": None,
        "photoAlignment": diagnostics,
        "artifacts": {name: store.url(run_id, name) for name in names},
    }

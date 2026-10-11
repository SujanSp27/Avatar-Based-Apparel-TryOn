"""Real service quality-gate integration with deterministic model/parser doubles.

These tests exercise image decoding, framing, composition, and the real quality
guard. They do not establish that the pretrained inference output is realistic.
No GPU, downloaded checkpoints, or semantic model inference is required.
"""

import io
import json

import numpy as np
import pytest
from PIL import Image

from ml.errors import PipelineError
from ml.preprocessing.images import ImageFeatures
from ml.vton.parsing import HumanParse
from ml.vton.service import NATIVE_SIZE, PretrainedTryOn


class ControlledParser:
    def __init__(self, person_labels, garment_labels):
        self.answers = [person_labels, garment_labels, person_labels]
        self.calls = 0

    def predict(self, rgb):
        labels = self.answers[self.calls]
        self.calls += 1
        assert labels.shape == rgb.shape[:2]
        return HumanParse(labels.copy(), {"modelVersion": "test-parser-double"})


class PlainShirtPrediction:
    provenance = {"backend": "test-model-double", "checkpoint": "none"}

    def __init__(self):
        self.calls = 0

    def predict(self, person, garment, mask):
        self.calls += 1
        assert person.size == garment.size == mask.size == NATIVE_SIZE
        assert set(np.unique(np.asarray(mask))) <= {0, 255}
        # Deliberately loses the supplied stripes, simulating the recorded defect.
        return Image.new("RGB", NATIVE_SIZE, (70, 105, 102))


def controlled_inputs(striped):
    labels = np.zeros((512, 384), np.uint8)
    labels[40:115, 145:235] = 1
    labels[145:430, 90:300] = 3
    person_rgb = np.full((512, 384, 3), 240, np.uint8)
    person_rgb[labels == 1] = (184, 129, 92)
    person_rgb[labels == 3] = (194, 170, 129)
    person = ImageFeatures(
        image=person_rgb,
        mask=(labels > 0).astype(np.uint8) * 255,
        crop=person_rgb,
        bbox=(0, 0, 384, 512),
    )
    rgba = np.zeros((320, 240, 4), np.uint8)
    rgba[:, :, :3] = (45, 96, 92)
    if striped:
        rows = np.arange(320) % 26 < 7
        rgba[rows, :, :3] = (220, 225, 204)
    rgba[15:305, 20:220, 3] = 255
    garment_labels = np.where(rgba[:, :, 3] > 0, 3, 0).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(rgba).save(buffer, format="PNG")
    return person, labels, buffer.getvalue(), garment_labels


def configured_service(tmp_path, monkeypatch, labels, garment_labels):
    service = PretrainedTryOn(tmp_path, device="cpu")
    service._parser = ControlledParser(labels, garment_labels)
    service._model = PlainShirtPrediction()
    monkeypatch.setattr(service, "_load", lambda: None)
    return service


def test_stripe_loss_is_rejected_with_provenance_and_no_published_final(tmp_path, monkeypatch):
    person, labels, garment_data, garment_labels = controlled_inputs(striped=True)
    service = configured_service(tmp_path, monkeypatch, labels, garment_labels)
    original = person.image.copy()

    with pytest.raises(PipelineError) as caught:
        service.render(person, garment_data, "t-shirt", tmp_path)

    assert caught.value.code == "vton_garment_fidelity_failed"
    assert caught.value.status_code == 422
    assert "stripes" in str(caught.value)
    assert not (tmp_path / "tryon-2d.png").exists()
    assert service._model.calls == 1
    assert service._parser.calls == 3
    np.testing.assert_array_equal(person.image, original)

    fidelity = json.loads((tmp_path / "garment-fidelity.json").read_text(encoding="utf-8"))
    diagnostics = json.loads((tmp_path / "vton-diagnostics.json").read_text(encoding="utf-8"))
    assert fidelity["status"] == "rejected"
    assert fidelity["reason"] == "pronounced_stripes_disappeared"
    assert fidelity["reference"]["pronouncedHorizontalStripes"]
    assert diagnostics["garmentFidelity"] == fidelity
    assert diagnostics["model"] == service._model.provenance
    assert diagnostics["qualityValidated"] is False
    assert diagnostics["compositing"]["identityPreservedExactly"] is True
    assert diagnostics["compositing"]["changedPixelsOutsideEditMask"] == 0
    assert diagnostics["garmentSegmentation"] == "provided-alpha"

    # Retaining the raw failed model output is intentional debugging evidence.
    # It is not copied into the public final-result filename or replaced by RGB
    # from the striped reference as a fallback.
    with Image.open(tmp_path / "vton-model-output.png") as raw_prediction:
        pixels = np.asarray(raw_prediction)
        assert pixels.shape == (512, 384, 3)
        assert np.all(pixels == [70, 105, 102])
    for name in (
        "vton-garment-input.png",
        "vton-replacement-mask.png",
        "personParsing.png",
        "generatedParsing.png",
        "semantic-edit-mask.png",
    ):
        assert (tmp_path / name).is_file()


def test_solid_reference_abstains_without_preventing_a_normal_result(tmp_path, monkeypatch):
    person, labels, garment_data, garment_labels = controlled_inputs(striped=False)
    service = configured_service(tmp_path, monkeypatch, labels, garment_labels)

    diagnostics = service.render(person, garment_data, "shirt", tmp_path)

    assert (tmp_path / "tryon-2d.png").is_file()
    assert diagnostics["garmentFidelity"]["status"] == "abstained"
    assert diagnostics["qualityValidated"] is False
    with Image.open(tmp_path / "tryon-2d.png") as final:
        pixels = np.asarray(final)
        np.testing.assert_array_equal(pixels[labels != 3], person.image[labels != 3])
        assert np.all(pixels[labels == 3] == [70, 105, 102])

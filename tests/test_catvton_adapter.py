"""Failure contracts only: these tests do not assess generated-image quality."""

import hashlib
import json
from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from ml.errors import PipelineError
from ml.vton import catvton
from ml.vton.service import PretrainedTryOn


def write_asset_tree(folder):
    """Small, deliberately invalid model files; never real model weights."""
    for name in catvton.REQUIRED_FILES:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"unit test asset")


@pytest.mark.parametrize(
    "missing",
    ["base/unet/config.json", "base/safety_checker/model.fp16.safetensors"],
)
def test_missing_required_assets_fail_before_model_loading(tmp_path, missing):
    write_asset_tree(tmp_path)
    (tmp_path / missing).unlink()

    with pytest.raises(PipelineError) as error:
        catvton.CatVTONModel(tmp_path, "cpu")

    assert error.value.code == "vton_model_unavailable"
    assert error.value.status_code == 503
    assert missing in str(error.value)


def test_corrupted_checkpoint_is_rejected_by_pinned_hash(tmp_path):
    write_asset_tree(tmp_path)

    with pytest.raises(PipelineError) as error:
        catvton.CatVTONModel(tmp_path, "cpu")

    assert error.value.code == "vton_checkpoint_invalid"
    assert error.value.status_code == 503
    assert "SHA-256" in str(error.value)


@pytest.mark.parametrize(
    "problem", ["source_revision", "path_traversal", "config_hash", "empty_files", "file_size"]
)
def test_invalid_manifest_is_rejected_before_model_loading(tmp_path, monkeypatch, problem):
    write_asset_tree(tmp_path)
    digest = hashlib.sha256(b"unit test asset").hexdigest()
    # The manifest checks are independent of the actual multi-GB checkpoints.
    monkeypatch.setattr(catvton, "CHECKPOINTS", dict.fromkeys(catvton.CHECKPOINTS, digest))
    records = [
        {"file": name, "sha256": digest, "bytes": len(b"unit test asset")}
        for name in catvton.REQUIRED_FILES
        if name != "download-manifest.json"
    ]
    record = next(record for record in records if record["file"] == "base/unet/config.json")
    manifest = {"sourceCommit": catvton.SOURCE_COMMIT, "files": records}
    if problem == "source_revision":
        manifest["sourceCommit"] = "unexpected revision"
    elif problem == "path_traversal":
        record["file"] = "../outside-model-folder.json"
    elif problem == "config_hash":
        record["sha256"] = "0" * 64
    elif problem == "empty_files":
        manifest["files"] = []
    else:
        record["bytes"] += 1
    (tmp_path / "download-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PipelineError) as error:
        catvton.CatVTONModel(tmp_path, "cpu")

    assert error.value.code == "vton_checkpoint_invalid"
    assert error.value.status_code == 503
    assert "manifest" in str(error.value)


@pytest.mark.parametrize("mask_value", [0, 255])
def test_empty_or_whole_person_mask_cannot_start_inference(mask_value):
    model = object.__new__(catvton.CatVTONModel)
    model.pipeline = Mock(side_effect=AssertionError("Inference must not start"))
    person = Image.new("RGB", (384, 512), "white")
    mask = Image.new("L", person.size, mask_value)

    with pytest.raises(PipelineError) as error:
        model.predict(person, person, mask)

    assert error.value.code == "vton_invalid_mask"
    assert error.value.status_code == 422
    model.pipeline.assert_not_called()


def bare_adapter():
    """Exercise adapter control flow with small tensors and no checkpoint load."""
    import torch

    model = object.__new__(catvton.CatVTONModel)
    model.device = torch.device("cpu")
    model._lock = Lock()
    person = Image.new("RGB", (384, 512), "white")
    mask = Image.new("L", person.size, 0)
    mask.paste(255, (100, 150, 280, 400))
    return model, person, mask


def test_cuda_out_of_memory_becomes_retryable_typed_failure(monkeypatch):
    import torch

    model, person, mask = bare_adapter()
    model.pipeline = Mock(side_effect=torch.cuda.OutOfMemoryError("test allocation failure"))
    cleanup = Mock()
    monkeypatch.setattr(torch.cuda, "empty_cache", cleanup)

    with pytest.raises(PipelineError) as error:
        model.predict(person, person, mask)

    assert error.value.code == "vton_memory_exhausted"
    assert error.value.status_code == 503
    cleanup.assert_called_once()


def test_rejected_generated_image_is_never_returned():
    import torch

    model, person, mask = bare_adapter()
    model.pipeline = Mock(return_value=[person])
    model.feature_extractor = Mock(
        return_value=SimpleNamespace(pixel_values=torch.zeros((1, 3, 2, 2)))
    )
    model.safety_checker = Mock(return_value=(None, [True]))

    with pytest.raises(PipelineError) as error:
        model.predict(person, person, mask)

    assert error.value.code == "vton_output_rejected"
    assert error.value.status_code == 422
    model.safety_checker.assert_called_once()


@pytest.mark.parametrize(
    ("failure", "code", "status"),
    [
        (ImportError("dependency missing"), "vton_dependency_unavailable", 503),
        (MemoryError("allocation failed"), "vton_inference_failed", 500),
        (RuntimeError("operator failed"), "vton_inference_failed", 500),
        (
            PipelineError("vton_checkpoint_invalid", "corrupted checkpoint", 503),
            "vton_checkpoint_invalid",
            503,
        ),
    ],
)
def test_service_failure_never_returns_a_preview(tmp_path, monkeypatch, failure, code, status):
    service = PretrainedTryOn(tmp_path, "cpu")
    monkeypatch.setattr(service, "_load", Mock(side_effect=failure))
    render = Mock(side_effect=AssertionError("No inference or preview after load failure"))
    monkeypatch.setattr(service, "_render", render)

    with pytest.raises(PipelineError) as error:
        service.render(None, b"unused", "t-shirt", tmp_path)

    assert error.value.code == code
    assert error.value.status_code == status
    if isinstance(failure, PipelineError):
        assert error.value is failure
    render.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def shared_attention():
    import torch

    shared = torch.nn.Linear(2, 3)
    unique = torch.nn.Linear(3, 1)
    module = torch.nn.ModuleList([shared, shared, unique])
    # The safetensors format may retain either registered name for an alias.
    checkpoint = {
        "0.weight": torch.full_like(shared.weight, 0.25),
        "1.bias": torch.full_like(shared.bias, 0.5),
        "2.weight": torch.full_like(unique.weight, 0.75),
        "2.bias": torch.full_like(unique.bias, 1.0),
    }
    return module, checkpoint


def test_deduplicated_checkpoint_restores_all_shared_parameter_aliases(shared_attention):
    import torch

    module, checkpoint = shared_attention
    catvton.load_shared_attention_weights(module, checkpoint)

    assert module[0].weight is module[1].weight
    assert module[0].bias is module[1].bias
    torch.testing.assert_close(module[0](torch.ones(1, 2)), torch.ones(1, 3))
    torch.testing.assert_close(module[2](torch.ones(1, 3)), torch.full((1, 1), 3.25))
    assert set(checkpoint) == {"0.weight", "1.bias", "2.weight", "2.bias"}


def test_attention_checkpoint_must_cover_every_unique_parameter(shared_attention):
    import torch

    module, checkpoint = shared_attention
    original_weight = module[0].weight.detach().clone()
    del checkpoint["2.bias"]

    with pytest.raises(ValueError, match="does not cover attention parameter 2.bias"):
        catvton.load_shared_attention_weights(module, checkpoint)

    torch.testing.assert_close(module[0].weight, original_weight)


def test_attention_checkpoint_rejects_conflicting_alias_values(shared_attention):
    import torch

    module, checkpoint = shared_attention
    checkpoint["1.weight"] = torch.zeros_like(checkpoint["0.weight"])

    with pytest.raises(ValueError, match="Conflicting values for shared attention parameter"):
        catvton.load_shared_attention_weights(module, checkpoint)


def test_attention_checkpoint_rejects_unexpected_weights(shared_attention):
    import torch

    module, checkpoint = shared_attention
    checkpoint["unrecognized.weight"] = torch.zeros(1)

    with pytest.raises(ValueError, match="Unexpected CatVTON attention checkpoint keys"):
        catvton.load_shared_attention_weights(module, checkpoint)


@pytest.mark.parametrize("conditioning", ["official", "reference-anchor"])
@pytest.mark.parametrize("fail", [False, True])
def test_conditioning_is_opt_in_scoped_and_reset_per_prediction(conditioning, fail):
    import torch
    from diffusers import DDIMScheduler

    model, person, mask = bare_adapter()
    model.conditioning = conditioning
    seen = []

    class RecordingUNet(torch.nn.Module):
        def forward(self, sample, timestep, **kwargs):
            seen.append(sample.clone())
            if fail:
                raise RuntimeError("diagnostic failure")
            return (sample[:, :4],)

    class TinyPipeline:
        unet = RecordingUNet()
        noise_scheduler = DDIMScheduler(num_train_timesteps=10)

        def __init__(self):
            self.noise = 0.3

        def __call__(self, **kwargs):
            sample = torch.zeros(2, 9, 8, 4)
            sample[:, :4] = self.noise
            sample[1, 5:9, 4:] = 1
            self.unet(sample, torch.tensor(9), encoder_hidden_states=None, return_dict=False)
            # The hook must not change the official pipeline's tensor in place.
            assert torch.all(sample[:, :4] == self.noise)
            return [person]

    model.pipeline = TinyPipeline()
    model.feature_extractor = Mock(return_value=SimpleNamespace(pixel_values=torch.zeros(1, 3, 2, 2)))
    model.safety_checker = Mock(return_value=(None, [False]))
    for noise in (0.3, 0.7):
        model.pipeline.noise = noise
        if fail:
            with pytest.raises(RuntimeError, match="diagnostic failure"):
                model.predict(person, person, mask)
        else:
            assert model.predict(person, person, mask) is person
        assert not model.pipeline.unet._forward_pre_hooks
        assert not model.pipeline.unet._forward_hooks
        sample = seen[-1]
        assert torch.all(sample[:, :4, :4] == noise)
        if conditioning == "official":
            assert torch.all(sample[:, :4, 4:] == noise)
        else:
            alpha = model.pipeline.noise_scheduler.alphas_cumprod[9]
            expected = alpha.sqrt() + (1 - alpha).sqrt() * noise
            assert torch.count_nonzero(sample[0, :, 4:]) == 0
            torch.testing.assert_close(sample[1, :4, 4:], torch.full((4, 4, 4), expected))

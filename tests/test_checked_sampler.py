"""CPU-only numerical tests; no weights or CUDA initialization required."""

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from ml.errors import PipelineError
from ml.vton.checked_sampler import CheckedSamplerMixin

torch = pytest.importorskip("torch")


@pytest.fixture
def sampler_utils(monkeypatch):
    """Use tiny tensors to exercise the sampler without installing FASHN."""
    utils = types.ModuleType("fashn_vton.utils")
    utils.get_rf_schedule = lambda num_steps, mu: [i / num_steps for i in range(num_steps + 1)]
    converted = []

    def tensor_to_pil(value, *, unnormalize):
        assert unnormalize
        converted.append(value.clone())
        return value.clone()

    utils.tensor_to_pil = tensor_to_pil
    monkeypatch.setitem(sys.modules, "fashn_vton.utils", utils)
    return converted


class TinyModel:
    channels_in = 3
    input_shape = (2, 2)

    def __init__(self, prediction=None):
        self.prediction = prediction
        self.cfg_calls = 0
        self.conditional_calls = 0

    def forward_for_cfg(self, images, times, **kwargs):
        assert images.device.type == "cpu"
        assert not torch.is_grad_enabled()
        self.cfg_calls += 1
        if self.prediction is not None:
            return self.prediction(images, self.cfg_calls)
        return {"v_c": images * .1 + .2, "v_u": images * .05 - .1}

    def forward(self, images, times, **kwargs):
        self.conditional_calls += 1
        return {"x": images * .1 + .2}


def inputs(dtype=torch.float32):
    image = torch.zeros((1, 3, 2, 2), dtype=dtype, device="cpu")
    return {
        "ca_images": image,
        "garment_images": image,
        "person_poses": image,
        "garment_poses": image,
        "garment_categories": torch.ones(1, dtype=torch.long, device="cpu"),
        "num_timesteps": 4,
        "use_tqdm": False,
    }


def sampler(model=None):
    instance = CheckedSamplerMixin()
    instance.tryon_model = model or TinyModel()
    return instance


def test_checked_sampler_matches_original_euler_algorithm(sampler_utils):
    torch.manual_seed(123)
    expected = torch.randn((1, 3, 2, 2), device="cpu")
    for step in range(4):
        v_c, v_u = expected * .1 + .2, expected * .05 - .1
        velocity = v_c if step == 3 else v_u + 1.5 * (v_c - v_u)
        expected = expected + .25 * velocity
    expected = expected.float().clamp(-1, 1)
    torch.manual_seed(123)
    instance = sampler()
    actual = instance._sample(**inputs())
    torch.testing.assert_close(actual[0], expected[0], rtol=0, atol=0)
    assert instance.tryon_model.cfg_calls == 4
    assert instance.tryon_model.conditional_calls == 0
    assert len(sampler_utils) == 1


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_invalid_prediction_never_reaches_image_conversion(sampler_utils, bad_value):
    def predict(images, step):
        return {"v_c": torch.full_like(images, bad_value), "v_u": torch.zeros_like(images)}

    with pytest.raises(PipelineError, match="step 1") as error:
        sampler(TinyModel(predict))._sample(**inputs())
    assert error.value.code == "numerical_instability"
    assert not sampler_utils


def test_finite_fp16_predictions_with_overflowing_guidance_are_rejected(sampler_utils):
    def predict(images, step):
        return {"v_c": torch.full_like(images, 60000), "v_u": torch.full_like(images, -60000)}

    with pytest.raises(PipelineError, match="numerically unstable"):
        sampler(TinyModel(predict))._sample(**inputs(torch.float16))
    assert not sampler_utils


def test_final_euler_state_overflow_is_rejected_before_clamp(sampler_utils, monkeypatch):
    # Both the prediction and guided velocity are finite. Only the update
    # overflows, so checking model output alone would accept a saturated PNG.
    monkeypatch.setattr(torch, "randn", lambda shape, dtype, device: torch.full(shape, 65000, dtype=dtype, device=device))

    def predict(images, step):
        return {"v_c": torch.full_like(images, 65000), "v_u": torch.full_like(images, 65000)}

    arguments = inputs(torch.float16)
    arguments["num_timesteps"] = 1
    with pytest.raises(PipelineError, match="step 1"):
        sampler(TinyModel(predict))._sample(**arguments)
    assert not sampler_utils


def test_opt_in_conditional_final_step_keeps_output(sampler_utils):
    torch.manual_seed(123)
    default = sampler()._sample(**inputs())
    torch.manual_seed(123)
    optimized = sampler()
    optimized.skip_unused_unconditional = True
    actual = optimized._sample(**inputs())
    torch.testing.assert_close(actual[0], default[0], rtol=0, atol=0)
    assert optimized.tryon_model.cfg_calls == 3
    assert optimized.tryon_model.conditional_calls == 1


def test_unit_guidance_skips_only_algebraically_unused_branch(sampler_utils):
    arguments = {**inputs(), "guidance_scale": 1.0}
    torch.manual_seed(123)
    expected = sampler()._sample(**arguments)
    torch.manual_seed(123)
    optimized = sampler()
    optimized.skip_unused_unconditional = True
    actual = optimized._sample(**arguments)
    torch.testing.assert_close(actual[0], expected[0], rtol=1e-6, atol=1e-7)
    assert optimized.tryon_model.cfg_calls == 0
    assert optimized.tryon_model.conditional_calls == 4


def test_import_does_not_load_torch_or_model():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import ml.vton.checked_sampler; assert 'torch' not in sys.modules; assert 'fashn_vton' not in sys.modules"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

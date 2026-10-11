"""Small CPU numerical checks; generated-image quality is validated separately."""

import copy

import pytest
import torch
from torch import nn

from ml.vton.precision import promote_conv2d_math_to_float32


@pytest.mark.parametrize("dtype", [torch.float16, torch.bfloat16])
@pytest.mark.parametrize("bias", [False, True])
@pytest.mark.parametrize("padding_mode", ["zeros", "reflect"])
def test_promoted_convolution_matches_float32_reference(dtype, bias, padding_mode):
    torch.manual_seed(3)
    layer = nn.Conv2d(
        4, 6, kernel_size=3, stride=2, dilation=2, padding=2,
        groups=2, bias=bias, padding_mode=padding_mode,
    ).to(dtype=dtype)
    reference = copy.deepcopy(layer).float()
    inputs = torch.randn(1, 4, 13, 15).to(dtype=dtype)
    expected = reference(inputs.float()).to(dtype=dtype)

    assert promote_conv2d_math_to_float32(layer) == 1
    # An outer autocast context cannot undo the numerical workaround.
    with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
        actual = layer(inputs)

    assert actual.dtype == dtype
    assert layer.weight.dtype == dtype
    if bias:
        assert layer.bias.dtype == dtype
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)


def test_checkpoint_keys_parameters_aliases_and_hooks_survive_in_place_patch():
    shared = nn.Conv2d(2, 2, 3, padding=1).half()
    model = nn.ModuleList([shared, nn.Sequential(shared, nn.Identity())])
    parameters = {name: id(value) for name, value in model.named_parameters(remove_duplicate=False)}
    before = {name: value.clone() for name, value in model.state_dict().items()}
    calls = []
    hook = shared.register_forward_hook(lambda module, inputs, output: calls.append(output.shape))

    assert promote_conv2d_math_to_float32(model) == 1
    assert promote_conv2d_math_to_float32(model) == 0
    assert model[0] is model[1][0] is shared
    assert parameters == {
        name: id(value) for name, value in model.named_parameters(remove_duplicate=False)
    }
    assert before.keys() == model.state_dict().keys()
    for name, value in model.state_dict().items():
        torch.testing.assert_close(value, before[name], rtol=0, atol=0)
    model.load_state_dict(before, strict=True)
    shared(torch.ones(1, 2, 4, 4, dtype=torch.float16))
    hook.remove()
    assert calls == [torch.Size([1, 2, 4, 4])]


def test_unselected_model_and_conv_subclasses_keep_their_forward():
    class SpecialConv(nn.Conv2d):
        def forward(self, inputs):
            return super().forward(inputs) + 1

    selected = nn.Conv2d(1, 1, 1)
    unselected = nn.Conv2d(1, 1, 1)
    specialized = SpecialConv(1, 1, 1)
    original = unselected.forward.__func__
    custom = specialized.forward.__func__

    assert promote_conv2d_math_to_float32(nn.ModuleList([selected, specialized])) == 1
    assert unselected.forward.__func__ is original
    assert specialized.forward.__func__ is custom


def test_custom_instance_forward_is_rejected_before_any_layer_is_changed():
    first = nn.Conv2d(1, 1, 1)
    second = nn.Conv2d(1, 1, 1)
    original = first.forward.__func__
    second.forward = lambda inputs: inputs

    with pytest.raises(ValueError, match="custom forward"):
        promote_conv2d_math_to_float32(nn.ModuleList([first, second]))

    assert first.forward.__func__ is original


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_higher_precision_inputs_keep_existing_numerics(dtype):
    layer = nn.Conv2d(1, 1, 3).to(dtype=dtype)
    inputs = torch.ones(1, 1, 6, 6, dtype=dtype)
    expected = layer(inputs)

    promote_conv2d_math_to_float32(layer)
    actual = layer(inputs)

    assert actual.dtype == dtype
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)

"""Scoped convolution precision workaround for verified GTX 16 FP16 failures.

The installed GTX 1650/cuDNN runtime produces non-finite FP16 Conv2d output
for finite CatVTON inputs. Float32 cuDNN convolution passed the recorded
layer diagnostic and was faster than disabling cuDNN. This helper changes
only explicitly supplied model instances; it does not change global torch
behavior, model parameters, checkpoint keys, or shared parameter aliases.
"""

from types import MethodType

import torch
from torch import Tensor, nn


def _float32_conv2d_forward(layer: nn.Conv2d, inputs: Tensor) -> Tensor:
    if inputs.dtype not in (torch.float16, torch.bfloat16):
        return layer._conv_forward(inputs, layer.weight, layer.bias)

    # An outer mixed-precision context must not silently cast the operation
    # back to the failing FP16 kernel. Casts are temporary, so the model's
    # resident weights remain FP16 and continue to fit the 4 GB device.
    with torch.autocast(device_type=inputs.device.type, enabled=False):
        output = layer._conv_forward(
            inputs.float(),
            layer.weight.float(),
            layer.bias.float() if layer.bias is not None else None,
        )
    return output.to(dtype=inputs.dtype)


def promote_conv2d_math_to_float32(model: nn.Module) -> int:
    """Promote low-precision Conv2d math in this model, retaining stored weights.

    Call after loading weights, and only for a runtime requiring this
    workaround. cuDNN should remain enabled by the caller. Standard Conv2d
    instances are patched in place, including a Conv2d passed as the root.
    Subclasses retain their potentially different forward semantics.

    Return the number of newly patched unique layers. Repeated calls are
    harmless. Existing custom per-instance forwards are rejected rather
    than silently replaced. This helper is intended for eager inference;
    it does not claim torch.compile or exported graph compatibility.
    """
    candidates = [layer for layer in model.modules() if type(layer) is nn.Conv2d]
    for layer in candidates:
        if (
            "forward" in layer.__dict__
            and getattr(layer.forward, "__func__", None) is not _float32_conv2d_forward
        ):
            raise ValueError("Cannot replace a Conv2d instance with a custom forward")

    patched = 0
    for layer in candidates:
        if getattr(layer.forward, "__func__", None) is _float32_conv2d_forward:
            continue
        layer.forward = MethodType(_float32_conv2d_forward, layer)
        patched += 1
    return patched

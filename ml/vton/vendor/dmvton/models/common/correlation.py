"""Portable inference equivalent of the pinned upstream CuPy cost-volume kernel.

The original kernel is retained beside this file as correlation.py.txt. At
stride one it computes mean_c(first[y,x,c] * second[y+dy,x+dx,c]), using zero
padding and row-major offsets dy,dx in [-3,3]. No learned parameters change.
"""

import torch
import torch.nn.functional as F


def FunctionCorrelation(tenFirst, tenSecond, intStride=1):
    if intStride != 1:
        raise ValueError("The portable DM-VTON inference operator supports stride one only")
    if tenFirst.shape != tenSecond.shape or tenFirst.ndim != 4:
        raise ValueError("Correlation inputs must have matching NCHW shapes")
    _, _, h, w = tenFirst.shape
    padded = F.pad(tenSecond, (3, 3, 3, 3))
    return torch.stack([
        (tenFirst * padded[:, :, dy:dy + h, dx:dx + w]).mean(dim=1)
        for dy in range(7) for dx in range(7)
    ], dim=1)

"""Optional inference-only experiment for CatVTON garment conditioning.

This tests two ideas from sections 4.2--4.3 of
https://arxiv.org/html/2511.18775v1: remove the garment from the unconditional
branch and replace its drifting noisy latent with forward-diffused reference
latents. It is NOT the paper's Re-CatVTON implementation or trained checkpoint:
that method also fully fine-tunes the UNet with a different loss. Quality with
the existing CatVTON weights is unvalidated; this helper is not enabled by
default and must be evaluated separately from official inference.

Only the pinned CatVTON DDIM layout is supported: channels [noise:4, mask:1,
clean conditioning:4], person above garment, and CFG batches [uncond, cond].
The caller must invoke reset() before every prediction, then prepare() on the
complete UNet input BEFORE splitting CFG into sequential calls. The first
input must contain initial standard Gaussian noise (DDIM init_noise_sigma=1,
identity scale_model_input). Resumed/partly denoised trajectories are unsupported.
"""

from __future__ import annotations

import math

import torch


class ReferenceAnchor:
    """Keep a fixed reference-noise realization for one inference trajectory.

    Given the clean garment latent g and initial Gaussian noise e, substitute
    sqrt(alpha_bar[t]) * g + sqrt(1-alpha_bar[t]) * e into the conditional
    garment noise channels at every call. The input, person region, clean
    garment condition, scheduler, and model weights are never mutated.

    Passing only alphas_cumprod asserts the documented DDIM assumptions. The
    optional arguments let an integration explicitly verify scheduler values.
    This mutable object is per-prediction and is not safe for concurrent use.
    """

    def __init__(
        self,
        alphas_cumprod: torch.Tensor,
        *,
        init_noise_sigma: float = 1.0,
        scale_model_input_is_identity: bool = True,
    ) -> None:
        if not math.isfinite(init_noise_sigma) or init_noise_sigma != 1.0:
            raise ValueError("ReferenceAnchor requires DDIM init_noise_sigma=1.")
        if scale_model_input_is_identity is not True:
            raise ValueError("ReferenceAnchor requires identity DDIM input scaling.")
        if (
            not isinstance(alphas_cumprod, torch.Tensor)
            or alphas_cumprod.ndim != 1
            or alphas_cumprod.numel() == 0
            or not alphas_cumprod.is_floating_point()
        ):
            raise ValueError("alphas_cumprod must be a nonempty floating-point vector.")
        alphas = alphas_cumprod.detach().to(device="cpu", dtype=torch.float64).clone()
        if not bool(torch.isfinite(alphas).all()) or not bool(((alphas > 0) & (alphas <= 1)).all()):
            raise ValueError("alphas_cumprod must contain finite values in (0, 1].")
        if bool((alphas[1:] > alphas[:-1]).any()):
            raise ValueError("alphas_cumprod must be non-increasing.")
        self._alphas = alphas
        self.reset()

    def reset(self) -> None:
        """Discard trajectory state before starting another prediction."""
        self._reference_noise: torch.Tensor | None = None
        self._clean_garment: torch.Tensor | None = None
        self._signature: tuple | None = None
        self._last_timestep: int | None = None

    def _timestep(self, timestep: int | torch.Tensor) -> int:
        if isinstance(timestep, torch.Tensor):
            if timestep.numel() != 1 or timestep.dtype == torch.bool:
                raise ValueError("timestep must be one integer DDIM index.")
            timestep = timestep.item()
        if isinstance(timestep, bool) or not isinstance(timestep, (int, float)):
            raise ValueError("timestep must be one integer DDIM index.")
        if not math.isfinite(timestep) or int(timestep) != timestep:
            raise ValueError("timestep must be one integer DDIM index.")
        index = int(timestep)
        if not 0 <= index < len(self._alphas):
            raise ValueError("timestep is outside alphas_cumprod.")
        if self._last_timestep is not None and index > self._last_timestep:
            raise ValueError("Timesteps must descend; call reset() before a new prediction.")
        return index

    def prepare(
        self, sample: torch.Tensor, timestep: int | torch.Tensor, has_guidance: bool
    ) -> torch.Tensor:
        """Return a changed clone of the full nine-channel UNet input.

        CFG is ordered [all unconditional examples, all conditional examples],
        as in official CatVTON. Invalid layouts fail instead of conditioning a
        wrong image region or silently reusing another prediction's noise.
        """
        if not isinstance(has_guidance, bool):
            raise ValueError("has_guidance must be a boolean.")
        if (
            not isinstance(sample, torch.Tensor)
            or sample.ndim != 4
            or not sample.is_floating_point()
            or sample.shape[0] < 1
            or sample.shape[1] != 9
            or sample.shape[2] < 2
            or sample.shape[2] % 2
            or sample.shape[3] < 1
        ):
            raise ValueError("Expected floating-point [batch, 9, 2*height, width] input.")
        if has_guidance and sample.shape[0] % 2:
            raise ValueError("CFG requires an even [unconditional, conditional] batch.")
        if not bool(torch.isfinite(sample).all()):
            raise ValueError("UNet input contains non-finite values.")
        index = self._timestep(timestep)
        signature = (tuple(sample.shape), sample.dtype, sample.device, has_guidance)
        if self._signature is not None and signature != self._signature:
            raise ValueError("Input layout changed; call reset() before a new prediction.")
        half = sample.shape[2] // 2
        batch_half = sample.shape[0] // 2 if has_guidance else 0
        conditioned = sample[batch_half:]
        clean = conditioned[:, 5:9, half:, :]
        noisy = conditioned[:, :4, half:, :]
        if bool(torch.count_nonzero(sample[:, 4:5, half:, :])):
            raise ValueError("CatVTON garment-half mask must be zero.")
        if not bool(torch.count_nonzero(clean)):
            raise ValueError("Conditional clean garment latent must not be all zero.")
        if has_guidance:
            unconditional = sample[:batch_half]
            if bool(torch.count_nonzero(unconditional[:, 5:9, half:, :])):
                raise ValueError("CFG must place the zero garment condition before the conditional batch.")
            if not torch.equal(unconditional[:, :, :half, :], conditioned[:, :, :half, :]):
                raise ValueError("CFG person regions must match before UNet inference.")
            if not torch.equal(unconditional[:, :4, half:, :], noisy):
                raise ValueError("Official CFG branches must share the same noisy latent input.")
        if self._clean_garment is not None and not torch.equal(clean, self._clean_garment):
            raise ValueError("Garment condition changed; call reset() before a new prediction.")

        if self._reference_noise is None:
            # Only valid at the first call, before the sampler has denoised it.
            self._reference_noise = noisy.detach().clone()
            self._clean_garment = clean.detach().clone()
            self._signature = signature
        compute_dtype = torch.float64 if sample.dtype == torch.float64 else torch.float32
        alpha = self._alphas[index].to(device=sample.device, dtype=compute_dtype)
        anchored = (
            alpha.sqrt() * clean.to(dtype=compute_dtype)
            + (1 - alpha).sqrt() * self._reference_noise.to(dtype=compute_dtype)
        )
        result = sample.clone()
        result[batch_half:, :4, half:, :] = anchored.to(dtype=sample.dtype)
        if has_guidance:
            result[:batch_half, :, half:, :] = 0
        self._last_timestep = index
        return result

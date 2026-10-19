"""Finite-state checks for the pinned FASHN Euler sampler.

Based on FASHN VTON 1.5 pipeline.py, commit
7c0f10af3f91ad4048fe9729c470a13ef905d25a (Apache-2.0).
No model is imported or initialized until the mixin is actually used by a worker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ml.errors import PipelineError

if TYPE_CHECKING:
    from PIL import Image
    from torch import Tensor


class CheckedSamplerMixin:
    """Place before TryOnPipeline in the worker's inheritance list.

    The numerical algorithm, native model resolution and upstream defaults stay
    unchanged. Optional conditional-only steps avoid an unconditional prediction
    that has zero weight at guidance 1.0 or that upstream discards at the end.
    Changing guidance itself requires separate garment-quality validation.
    """

    skip_unused_unconditional = False

    def _sample(
        self,
        *,
        ca_images: Tensor,
        garment_images: Tensor,
        person_poses: Tensor,
        garment_poses: Tensor,
        garment_categories: Tensor,
        num_timesteps: int = 30,
        time_shift_mu: float = 1.5,
        guidance_scale: float = 1.5,
        skip_cfg_last_n_steps: int = 1,
        use_tqdm: bool = True,
    ) -> list[Image.Image]:
        import torch
        from fashn_vton.utils import get_rf_schedule, tensor_to_pil
        from tqdm.auto import tqdm

        with torch.inference_mode():
            device, dtype = ca_images.device, ca_images.dtype
            batch_size = ca_images.shape[0]
            c, h, w = self.tryon_model.channels_in, *self.tryon_model.input_shape
            images = torch.randn((batch_size, c, h, w), dtype=dtype, device=device)
            timesteps = get_rf_schedule(num_steps=num_timesteps, mu=time_shift_mu)
            model_kwargs = {
                "person_poses": person_poses,
                "garment_poses": garment_poses,
                "ca_images": ca_images,
                "garment_images": garment_images,
                "garment_categories": garment_categories,
            }
            for step_idx, (t_curr, t_prev) in enumerate(
                tqdm(
                    zip(timesteps[:-1], timesteps[1:]),
                    desc="Sampling",
                    total=len(timesteps) - 1,
                    disable=not use_tqdm,
                )
            ):
                dt = t_prev - t_curr
                t_vec = torch.full((batch_size,), t_curr, dtype=dtype, device=device)
                omit_guidance = (
                    skip_cfg_last_n_steps > 0
                    and step_idx >= num_timesteps - skip_cfg_last_n_steps
                )
                if self.skip_unused_unconditional and (omit_guidance or guidance_scale == 1.0):
                    v_c = self.tryon_model.forward(images, t_vec, **model_kwargs)["x"]
                    v_guided = v_c
                    predictions_finite = torch.isfinite(v_c).all()
                else:
                    pred = self.tryon_model.forward_for_cfg(images, t_vec, **model_kwargs)
                    v_c, v_u = pred["v_c"], pred["v_u"]
                    v_guided = v_c if omit_guidance else v_u + guidance_scale * (v_c - v_u)
                    predictions_finite = torch.isfinite(v_c).all() & torch.isfinite(v_u).all()
                images = images + dt * v_guided
                # One scalar synchronization per step, not per model layer.
                # State must be checked before clamp: clamp would hide +/-Inf
                # and uint8/PIL conversion could conceal a failed generation.
                finite = (
                    predictions_finite
                    & torch.isfinite(v_guided).all()
                    & torch.isfinite(images).all()
                )
                if not bool(finite):
                    raise PipelineError(
                        "numerical_instability",
                        "The online model became numerically unstable during sampling "
                        f"(step {step_idx + 1}). No try-on image was returned.",
                    )
            if not bool(torch.isfinite(images).all()):
                raise PipelineError(
                    "numerical_instability",
                    "The online model produced an invalid final image. No try-on image was returned.",
                )
            images = images.to(dtype=torch.float).clamp_(-1.0, 1.0)
            return [tensor_to_pil(img, unnormalize=True) for img in images]

"""Exact query-sliced CatVTON attention for memory-constrained inference.

Adapted from Zheng-Chong/CatVTON ``model/attn_processor.py``, commit
999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e:
https://github.com/Zheng-Chong/CatVTON/blob/999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e/model/attn_processor.py
Upstream and this derivative are licensed CC-BY-NC-SA-4.0; see
``ml/vton/vendor/catvton/LICENSE`` and its disclaimer of warranties.

The sole attention algorithm change is splitting independent query rows before
the SDPA call. Every row still attends to *all* keys and values, including the
garment half of the CatVTON spatial concatenation. This is not windowed attention
and does not alter weights or the softmax normalization domain. Small rounding
differences can occur when PyTorch chooses kernels for different tensor shapes.

Install this processor only on self-attention (``attn1``). CatVTON deliberately
uses its original SkipAttnProcessor for cross-attention (``attn2``).
"""

import torch
from torch.nn import functional as F


def query_sliced_attention(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    attention_mask: torch.Tensor | None = None,
    *,
    query_chunk_size: int = 256,
) -> torch.Tensor:
    """Compute noncausal, dropout-free SDPA with bounded query workspace.

    Inputs use SDPA's ``(batch, heads, sequence, channels)`` layout. The prepared
    mask has either one broadcast query row or a row for each original query.
    On GPU backends that materialize scores, the largest score tensor is bounded
    by ``batch * heads * query_chunk_size * key_length``, not query length squared.
    """
    if (
        not isinstance(query_chunk_size, int)
        or isinstance(query_chunk_size, bool)
        or query_chunk_size < 1
    ):
        raise ValueError("query_chunk_size must be a positive integer")
    query_length = query.shape[-2]
    if attention_mask is not None and attention_mask.shape[-2] not in (1, query_length):
        raise ValueError("Attention mask must broadcast or match the full query length")

    # This Windows build lacks FlashAttention but does provide the fused
    # memory-efficient CUDA kernel on GTX 1650. Avoid hundreds of query launches
    # when that kernel can compute full attention without an N-by-N score buffer.
    if query.device.type == "cuda":
        from torch.backends.cuda import SDPAParams, can_use_efficient_attention
        from torch.nn.attention import SDPBackend, sdpa_kernel

        parameters = SDPAParams(query, key, value, attention_mask, 0.0, False, False)
        if can_use_efficient_attention(parameters):
            with sdpa_kernel(SDPBackend.EFFICIENT_ATTENTION):
                return F.scaled_dot_product_attention(
                    query, key, value, attn_mask=attention_mask, dropout_p=0.0, is_causal=False
                )

    outputs = []
    for start in range(0, query_length, query_chunk_size):
        end = min(start + query_chunk_size, query_length)
        mask_slice = attention_mask
        if attention_mask is not None and attention_mask.shape[-2] != 1:
            mask_slice = attention_mask[..., start:end, :]
        outputs.append(
            F.scaled_dot_product_attention(
                query[..., start:end, :],
                key,
                value,
                attn_mask=mask_slice,
                dropout_p=0.0,
                is_causal=False,
            )
        )
    # Empty queries are legal for SDPA; keep the same shape and autograd contract.
    if not outputs:
        return F.scaled_dot_product_attention(
            query, key, value, attn_mask=attention_mask, dropout_p=0.0, is_causal=False
        )
    return outputs[0] if len(outputs) == 1 else torch.cat(outputs, dim=-2)


class QuerySlicedAttnProcessor2_0(torch.nn.Module):
    """Upstream CatVTON AttnProcessor2_0 with exact query-sliced SDPA."""

    def __init__(self, query_chunk_size: int = 256):
        super().__init__()
        if (
            not isinstance(query_chunk_size, int)
            or isinstance(query_chunk_size, bool)
            or query_chunk_size < 1
        ):
            raise ValueError("query_chunk_size must be a positive integer")
        self.query_chunk_size = query_chunk_size

    def __call__(
        self,
        attn,
        hidden_states,
        encoder_hidden_states=None,
        attention_mask=None,
        temb=None,
        *args,
        **kwargs,
    ):
        residual = hidden_states

        if attn.spatial_norm is not None:
            hidden_states = attn.spatial_norm(hidden_states, temb)

        input_ndim = hidden_states.ndim
        if input_ndim == 4:
            batch_size, channel, height, width = hidden_states.shape
            hidden_states = hidden_states.view(batch_size, channel, height * width).transpose(1, 2)

        batch_size, sequence_length, _ = (
            hidden_states.shape if encoder_hidden_states is None else encoder_hidden_states.shape
        )
        if attention_mask is not None:
            attention_mask = attn.prepare_attention_mask(attention_mask, sequence_length, batch_size)
            attention_mask = attention_mask.view(batch_size, attn.heads, -1, attention_mask.shape[-1])

        if attn.group_norm is not None:
            hidden_states = attn.group_norm(hidden_states.transpose(1, 2)).transpose(1, 2)

        query = attn.to_q(hidden_states)
        if encoder_hidden_states is None:
            encoder_hidden_states = hidden_states
        elif attn.norm_cross:
            encoder_hidden_states = attn.norm_encoder_hidden_states(encoder_hidden_states)

        key = attn.to_k(encoder_hidden_states)
        value = attn.to_v(encoder_hidden_states)
        inner_dim = key.shape[-1]
        head_dim = inner_dim // attn.heads
        query = query.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        key = key.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        value = value.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)

        # The only change to upstream computation: all keys/values remain intact.
        hidden_states = query_sliced_attention(
            query, key, value, attention_mask, query_chunk_size=self.query_chunk_size
        )
        hidden_states = hidden_states.transpose(1, 2).reshape(batch_size, -1, attn.heads * head_dim)
        hidden_states = hidden_states.to(query.dtype)
        hidden_states = attn.to_out[0](hidden_states)
        hidden_states = attn.to_out[1](hidden_states)

        if input_ndim == 4:
            hidden_states = hidden_states.transpose(-1, -2).reshape(batch_size, channel, height, width)
        if attn.residual_connection:
            hidden_states = hidden_states + residual
        hidden_states = hidden_states / attn.rescale_output_factor
        return hidden_states

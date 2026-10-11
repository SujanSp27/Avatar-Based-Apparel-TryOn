"""Numerical equivalence to the actual pinned CatVTON attention implementation."""

import pytest
import torch
from diffusers.models.attention_processor import Attention

from ml.vton.attention import QuerySlicedAttnProcessor2_0, query_sliced_attention
from ml.vton.vendor.catvton.model.attn_processor import AttnProcessor2_0


@pytest.fixture(autouse=True)
def deterministic_cpu():
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(2)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(147)
        yield
    torch.set_num_threads(previous_threads)


@pytest.mark.parametrize("heads", [1, 2, 4])
@pytest.mark.parametrize("sequence_length,chunk_size", [(7, 3), (13, 4), (7, 256), (513, 256)])
@pytest.mark.parametrize("cross", [False, True])
def test_matches_official_sequence_attention(heads, sequence_length, chunk_size, cross):
    # Cross-attention equivalence checks the processor's complete contract; the
    # application must still keep CatVTON's SkipAttnProcessor on its attn2 layers.
    layer = Attention(
        query_dim=16, cross_attention_dim=12 if cross else None,
        heads=heads, dim_head=8, dropout=0, residual_connection=True,
        rescale_output_factor=1.7, norm_num_groups=4,
        cross_attention_norm="layer_norm" if cross else None,
    ).eval()
    hidden = torch.randn(2, sequence_length, 16)
    encoder = torch.randn(2, 5, 12) if cross else None
    with torch.inference_mode():
        expected = AttnProcessor2_0()(layer, hidden, encoder_hidden_states=encoder)
        actual = QuerySlicedAttnProcessor2_0(chunk_size)(
            layer, hidden, encoder_hidden_states=encoder
        )
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


@pytest.mark.parametrize("mask_type", ["bool", "additive"])
@pytest.mark.parametrize("query_mask", [False, True])
@pytest.mark.parametrize("cross", [False, True])
def test_matches_official_masked_attention(mask_type, query_mask, cross):
    query_length, key_length = 11, 5 if cross else 11
    layer = Attention(query_dim=16, heads=2, dim_head=8, dropout=0).eval()
    hidden = torch.randn(2, query_length, 16)
    encoder = torch.randn(2, key_length, 16) if cross else None
    mask = torch.rand(2, query_length if query_mask else 1, key_length) > 0.3
    mask[..., 0] = True  # At least one allowed key in every query row.
    if mask_type == "additive":
        mask = torch.zeros_like(mask, dtype=torch.float32).masked_fill(~mask, float("-inf"))
    with torch.inference_mode():
        expected = AttnProcessor2_0()(layer, hidden, encoder, mask)
        actual = QuerySlicedAttnProcessor2_0(3)(layer, hidden, encoder, mask)
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


@pytest.mark.parametrize("spatial_norm", [False, True])
def test_matches_official_spatial_input_and_normalization(spatial_norm):
    layer = Attention(
        query_dim=32, heads=4, dim_head=8, dropout=0,
        spatial_norm_dim=32 if spatial_norm else None,
        residual_connection=True,
    ).eval()
    hidden = torch.randn(2, 32, 3, 5)
    temb = torch.randn(2, 32, 2, 2) if spatial_norm else None
    with torch.inference_mode():
        expected = AttnProcessor2_0()(layer, hidden, temb=temb)
        actual = QuerySlicedAttnProcessor2_0(4)(layer, hidden, temb=temb)
    assert actual.shape == hidden.shape
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


def test_distant_garment_keys_remain_visible_to_every_query():
    # Uniform logits produce the full reference mean. Windowed/chunked keys
    # would incorrectly return zero for the first part of the person sequence.
    query = torch.zeros(1, 2, 11, 4)
    key = torch.zeros(1, 2, 11, 4)
    value = torch.zeros(1, 2, 11, 4)
    value[..., -1, :] = 11
    actual = query_sliced_attention(query, key, value, query_chunk_size=3)
    torch.testing.assert_close(actual, torch.ones_like(actual))


@pytest.mark.parametrize("chunk_size", [0, -1, True, 1.5])
def test_rejects_invalid_chunk_size(chunk_size):
    with pytest.raises(ValueError, match="positive integer"):
        QuerySlicedAttnProcessor2_0(chunk_size)


def test_processor_has_no_parameters_or_checkpoint_changes():
    layer = Attention(query_dim=16, heads=2, dim_head=8, processor=AttnProcessor2_0())
    original_keys = set(layer.state_dict())
    replacement = QuerySlicedAttnProcessor2_0()
    layer.set_processor(replacement)
    assert set(layer.state_dict()) == original_keys
    assert not list(replacement.parameters())

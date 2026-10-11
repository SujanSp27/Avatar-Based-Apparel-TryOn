"""Tensor-level checks only; these do not establish VTON image quality."""

import pytest
import torch

from ml.vton.conditioning import ReferenceAnchor


def sample_input(*, guided=True, batch=1, dtype=torch.float32):
    generator = torch.Generator().manual_seed(73)
    condition = torch.randn(batch, 9, 8, 3, generator=generator, dtype=dtype)
    condition[:, 4, 4:, :] = 0
    if not guided:
        return condition
    uncondition = condition.clone()
    uncondition[:, 5:9, 4:, :] = 0
    return torch.cat([uncondition, condition])


@pytest.mark.parametrize("guided", [False, True])
@pytest.mark.parametrize("dtype", [torch.float16, torch.float32, torch.float64])
def test_forward_diffusion_formula_and_unchanged_person(guided, dtype):
    source = sample_input(guided=guided, dtype=dtype)
    original = source.clone()
    anchor = ReferenceAnchor(torch.tensor([0.9, 0.64, 0.36]))
    result = anchor.prepare(source, torch.tensor(1), guided)
    start = 1 if guided else 0
    expected = 0.8 * source[start:, 5:9, 4:, :].double() + 0.6 * source[start:, :4, 4:, :].double()
    torch.testing.assert_close(result[start:, :4, 4:, :], expected.to(dtype), rtol=1e-3, atol=1e-3)
    assert torch.equal(source, original)
    assert result.data_ptr() != source.data_ptr()
    assert torch.equal(result[:, :, :4, :], source[:, :, :4, :])
    assert torch.equal(result[start:, 4:, 4:, :], source[start:, 4:, 4:, :])
    assert result.dtype == source.dtype
    assert result.device == source.device
    if guided:
        assert torch.count_nonzero(result[:start, :, 4:, :]) == 0


def test_reuses_initial_noise_not_drifting_sampler_garment():
    source = sample_input()
    anchor = ReferenceAnchor(torch.tensor([1.0, 0.64, 0.25]))
    anchor.prepare(source, 2, True)
    later = source.clone()
    later[:, :4, 4:, :] = 99
    result = anchor.prepare(later, 1, True)
    expected = 0.8 * source[1:, 5:9, 4:, :] + 0.6 * source[1:, :4, 4:, :]
    torch.testing.assert_close(result[1:, :4, 4:, :], expected)
    at_clean = anchor.prepare(later, 0, True)
    assert torch.equal(at_clean[1:, :4, 4:, :], source[1:, 5:9, 4:, :])


def test_cfg_batch_order_with_multiple_examples():
    source = sample_input(batch=2)
    anchor = ReferenceAnchor(torch.tensor([0.5]))
    result = anchor.prepare(source, 0, True)
    expected = (source[2:, :4, 4:, :] + source[2:, 5:9, 4:, :]) * (0.5 ** 0.5)
    torch.testing.assert_close(result[2:, :4, 4:, :], expected)
    assert torch.count_nonzero(result[:2, :, 4:, :]) == 0
    assert torch.equal(result[:, :, :4, :], source[:, :, :4, :])


def test_reset_repeats_without_random_state_changes():
    source = sample_input()
    anchor = ReferenceAnchor(torch.tensor([0.8, 0.4]))
    rng = torch.random.get_rng_state().clone()
    first = anchor.prepare(source, 1, True)
    anchor.prepare(source, 0, True)
    with pytest.raises(ValueError, match="reset"):
        anchor.prepare(source, 1, True)
    anchor.reset()
    repeated = anchor.prepare(source, 1, True)
    assert torch.equal(first, repeated)
    assert torch.equal(rng, torch.random.get_rng_state())


def test_reset_allows_a_new_garment_and_shape():
    anchor = ReferenceAnchor(torch.tensor([0.8]))
    anchor.prepare(sample_input(), 0, True)
    anchor.reset()
    other = sample_input(guided=False, batch=3)
    result = anchor.prepare(other, 0, False)
    assert result.shape == other.shape


@pytest.mark.parametrize("shape", [(2, 8, 8, 3), (2, 9, 7, 3), (2, 9, 8), (0, 9, 8, 3), (2, 9, 8, 0)])
def test_rejects_malformed_shapes(shape):
    with pytest.raises(ValueError, match="Expected"):
        ReferenceAnchor(torch.tensor([0.5])).prepare(torch.zeros(shape), 0, True)


@pytest.mark.parametrize("timestep", [-1, 2, 0.5, float("nan"), True, torch.tensor([0, 1])])
def test_rejects_invalid_timestep(timestep):
    with pytest.raises(ValueError, match="timestep"):
        ReferenceAnchor(torch.tensor([0.8, 0.4])).prepare(sample_input(), timestep, True)


@pytest.mark.parametrize("alphas", [torch.tensor([]), torch.tensor([0.2, 0.3]), torch.tensor([float("nan")]), torch.tensor([0.0]), torch.tensor([1.01]), torch.tensor([[0.4]]), torch.tensor([1])])
def test_rejects_invalid_schedules(alphas):
    with pytest.raises(ValueError, match="alphas_cumprod"):
        ReferenceAnchor(alphas)


@pytest.mark.parametrize("options", [{"init_noise_sigma": 2}, {"init_noise_sigma": float("nan")}, {"scale_model_input_is_identity": False}])
def test_rejects_non_ddim_assumptions(options):
    with pytest.raises(ValueError, match="DDIM"):
        ReferenceAnchor(torch.tensor([0.5]), **options)


@pytest.mark.parametrize("issue", ["order", "mask", "person", "noise", "finite", "empty_condition", "odd_batch", "integer"])
def test_rejects_incompatible_input_layout(issue):
    source = sample_input()
    if issue == "order":
        source = source.flip(0)
    elif issue == "mask":
        source[:, 4, 4:, :] = 1
    elif issue == "person":
        source[0, 0, 0, 0] += 1
    elif issue == "noise":
        source[0, 0, 4, 0] += 1
    elif issue == "finite":
        source[0, 0, 0, 0] = float("inf")
    elif issue == "empty_condition":
        source[:, 5:9, 4:, :] = 0
    elif issue == "odd_batch":
        source = source[1:]
    else:
        source = source.long()
    with pytest.raises(ValueError):
        ReferenceAnchor(torch.tensor([0.5])).prepare(source, 0, True)


def test_requires_reset_if_garment_or_dtype_changes():
    source = sample_input()
    anchor = ReferenceAnchor(torch.tensor([0.8, 0.4]))
    anchor.prepare(source, 1, True)
    changed = source.clone()
    changed[1, 5, 4, 0] += 1
    with pytest.raises(ValueError, match="reset"):
        anchor.prepare(changed, 0, True)
    with pytest.raises(ValueError, match="reset"):
        anchor.prepare(source.double(), 0, True)


def test_schedule_is_snapshot_not_an_external_mutable_reference():
    alphas = torch.tensor([1.0])
    anchor = ReferenceAnchor(alphas)
    alphas[0] = 0.5
    source = sample_input(guided=False)
    result = anchor.prepare(source, 0, False)
    assert torch.equal(result[:, :4, 4:, :], source[:, 5:9, 4:, :])

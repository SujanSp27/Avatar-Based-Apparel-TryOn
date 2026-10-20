"""Environment configuration must load before the API can start."""

import pytest
from pydantic import ValidationError

from backend.app.config import Settings


@pytest.mark.parametrize("steps", (10, 15, 20, 30, 50))
def test_steps_parse_from_environment(monkeypatch, steps):
    monkeypatch.setenv("ONLINE_VTON_STEPS", str(steps))
    assert Settings(_env_file=None).online_vton_steps == steps


@pytest.mark.parametrize("steps", ("11", "0", "51", "10.5", "fast"))
def test_unsupported_steps_fail_at_startup(monkeypatch, steps):
    monkeypatch.setenv("ONLINE_VTON_STEPS", steps)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

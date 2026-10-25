"""Production guardrails and race/retention checks independent of GPU inference."""

import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from backend.app.accounts.locks import _active, account_operation
from backend.app.accounts.security import access_token, now, signing_key
from backend.app.config import Settings, settings
from scripts.cleanup_private_data import expired


def test_production_requires_secrets_https_verification_and_delivery():
    valid = dict(
        _env_file=None,
        environment="production",
        auth_secret="secure-example-" * 8,
        auth_cookie_secure=True,
        auth_require_verification=True,
        app_public_url="https://studio.example.com",
        cors_origins=["https://studio.example.com"],
        smtp_host="smtp.example.com",
        smtp_from="studio@example.com",
    )
    assert Settings(**valid).environment == "production"
    for field, invalid in (
        ("auth_secret", ""),
        ("auth_cookie_secure", False),
        ("auth_require_verification", False),
        ("smtp_host", ""),
        ("app_public_url", "http://example.com"),
        ("cors_origins", ["*"]),
    ):
        with pytest.raises(ValidationError):
            Settings(**{**valid, field: invalid})


def test_retention_preserves_recent_and_unowned_data():
    at = now()
    assert expired("guest:example", at - timedelta(hours=settings.guest_retention_hours + 1), at)
    assert not expired("guest:example", at - timedelta(minutes=1), at)
    assert expired("account", at - timedelta(days=settings.private_retention_days + 1), at)
    assert not expired(None, at - timedelta(days=1000), at)
    assert not expired("account", None, at)


def test_account_mutations_wait_for_deletion_lock_and_release_entries(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "test-operation-key-" * 4)
    signing_key.cache_clear()
    token = access_token("owner", "session")
    request = Request(
        {
            "type": "http",
            "method": "DELETE",
            "path": "/api/v1/profile",
            "headers": [(b"authorization", ("Bearer " + token).encode())],
        }
    )

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        order = []

        async def first():
            async with account_operation(request):
                order.append("start")
                started.set()
                await release.wait()
                order.append("deleted")

        async def second():
            await started.wait()
            async with account_operation(request):
                order.append("next-request-authentication")

        a, b = asyncio.create_task(first()), asyncio.create_task(second())
        await started.wait()
        await asyncio.sleep(0)
        assert order == ["start"]
        release.set()
        await asyncio.gather(a, b)
        assert order == ["start", "deleted", "next-request-authentication"]
        assert not _active

    asyncio.run(scenario())
    signing_key.cache_clear()

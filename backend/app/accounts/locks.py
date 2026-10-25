"""Serialize account mutations with deletion in the supported single API process."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import HTTPException

from backend.app.accounts.security import ACCESS_COOKIE, read_token

_active: dict[str, tuple[asyncio.Lock, int]] = {}


@asynccontextmanager
async def account_operation(request):
    token = request.headers.get("authorization", "").removeprefix("Bearer ") or request.cookies.get(
        ACCESS_COOKIE
    )
    owner = None
    if token and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            owner = read_token(token)["sub"]
        except HTTPException:
            pass  # The endpoint still performs normal authentication and rejects it.
    if owner is None:
        yield
        return
    lock, count = _active.get(owner, (asyncio.Lock(), 0))
    _active[owner] = (lock, count + 1)
    try:
        async with lock:
            yield
    finally:
        _, count = _active[owner]
        if count == 1:
            del _active[owner]
        else:
            _active[owner] = (lock, count - 1)

"""Optional per-request progress; standalone model calls need no web dependency."""

from contextlib import contextmanager
from contextvars import ContextVar

_callback = ContextVar("tryon_progress", default=None)


def report_progress(stage: str, completed: int | None = None, total: int | None = None):
    callback = _callback.get()
    if callback is not None:
        callback({"stage": stage, "completed": completed, "total": total})


@contextmanager
def observe_progress(callback):
    token = _callback.set(callback)
    try:
        yield
    finally:
        _callback.reset(token)

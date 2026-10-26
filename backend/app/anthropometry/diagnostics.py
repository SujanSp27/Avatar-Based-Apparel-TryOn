"""Bounded numeric diagnostics only: never image bytes, paths, identities or tokens."""

import json
import logging

logger = logging.getLogger("vastraview.measurements")


def diagnostic(event: str, **fields):
    logger.info(json.dumps({"event": event, **fields}, allow_nan=False))

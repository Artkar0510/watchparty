"""Shared utilities for together-service."""
from datetime import datetime, timezone


def utc_now() -> str:
    """ISO-8601 UTC timestamp with timezone (e.g. '2026-05-16T07:44:01.234567+00:00')."""
    return datetime.now(timezone.utc).isoformat()

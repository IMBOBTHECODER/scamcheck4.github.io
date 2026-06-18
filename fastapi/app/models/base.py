"""Shared declarative Base and helpers for the ORM models."""
from datetime import datetime, timezone

from core.db import Base  # re-exported so model modules import Base from one place

__all__ = ["Base", "utcnow"]


def utcnow() -> datetime:
    """Naive UTC timestamp — non-deprecated replacement for datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

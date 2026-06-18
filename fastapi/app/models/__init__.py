"""ORM models package.

Importing `models` registers every table on Base (needed before create_all).
"""
from models.base import Base, utcnow
from models.scan import Scan

__all__ = ["Base", "utcnow", "Scan"]

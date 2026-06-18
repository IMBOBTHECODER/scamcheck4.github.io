"""Scan history model — one row per check, keyed by device id."""
from sqlalchemy import Column, DateTime, Integer, String, Text

from models.base import Base, utcnow


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True)
    # Anonymous per-device identifier (from the session cookie); not an account.
    device_id = Column(String(36), index=True, nullable=False)

    message = Column(Text, nullable=False)
    level = Column(Integer, nullable=False)
    label = Column(String(32), nullable=False)
    # The verdict's lists are stored as JSON strings (portable across engines).
    signals_json = Column(Text, nullable=False, default="[]")
    actions_json = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime, default=utcnow)

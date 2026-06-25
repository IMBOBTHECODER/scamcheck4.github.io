"""Scan history model — one row per check, keyed by device id."""
import secrets

from sqlalchemy import Column, DateTime, Integer, String, Text

from models.base import Base, utcnow


def _public_id() -> str:
    """Unguessable URL token (~128 bits) used in result links."""
    return secrets.token_urlsafe(16)


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True)
    # Opaque, random id used in URLs (/result/{public_id}) so scans can't be
    # enumerated by incrementing the integer primary key.
    public_id = Column(
        String(24), unique=True, index=True, nullable=False, default=_public_id
    )
    # Anonymous per-device identifier (from the session cookie); not an account.
    device_id = Column(String(36), index=True, nullable=False)

    message = Column(Text, nullable=False)
    level = Column(Integer, nullable=False)
    label = Column(String(32), nullable=False)
    # "Cô tâm lý" note — gentle explanation of the manipulation tactic (may be "").
    psych_note = Column(Text, nullable=False, default="")
    # "Người ứng cứu" guidance (JSON), generated on demand if the user says they
    # already acted on the scam. Empty until then.
    rescue_json = Column(Text, nullable=False, default="")
    # The verdict's lists are stored as JSON strings (portable across engines).
    signals_json = Column(Text, nullable=False, default="[]")
    actions_json = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime, default=utcnow)

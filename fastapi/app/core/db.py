"""Database engine, session factory, and table creation.

MySQL via SQLAlchemy; the connection URL comes from config (DATABASE_URL).
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

logger = logging.getLogger("scamcheck.db")

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # recycle stale MySQL connections transparently
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> bool:
    """Create tables if they don't exist (simple bootstrap; no migrations).

    Returns True on success. If the database is unreachable (e.g. MySQL down
    or out of connections) this logs a warning and returns False instead of
    raising, so the app can still boot and serve DB-independent pages.
    """
    import models  # noqa: F401 — register models on Base before create_all
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except SQLAlchemyError as exc:
        logger.warning("init_db skipped — database unavailable: %s", exc)
        return False

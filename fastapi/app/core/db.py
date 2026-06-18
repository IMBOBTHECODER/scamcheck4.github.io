"""Database engine, session factory, and table creation.

MySQL via SQLAlchemy; the connection URL comes from config (DATABASE_URL).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

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


def init_db() -> None:
    """Create tables if they don't exist (simple bootstrap; no migrations)."""
    import models  # noqa: F401 — register models on Base before create_all
    Base.metadata.create_all(bind=engine)

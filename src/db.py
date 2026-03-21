"""SQLAlchemy engine, session factory, and context manager."""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_db() -> Session:
    """Yield a database session that auto-closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

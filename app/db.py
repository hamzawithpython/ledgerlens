"""Database engine, session factory, and FastAPI dependency."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
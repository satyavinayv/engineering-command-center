"""
SQLAlchemy engine/session setup. SQLite by default; switching to
Postgres later is just a DATABASE_URL change (plus installing a
Postgres driver) — the ORM models don't change.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables that don't exist yet. Phase 1 uses this directly;
    once the schema stabilizes (Phase 2+) we should move to Alembic
    migrations instead of create_all."""
    from app import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)

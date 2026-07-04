from __future__ import annotations

import time
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database(retries: int = 30, delay_seconds: float = 1.0) -> None:
    from app import models  # noqa: F401
    from app.migrations import run_lightweight_migrations

    last_error: Exception | None = None
    for _ in range(retries):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            Base.metadata.create_all(bind=engine)
            run_lightweight_migrations(engine)
            return
        except Exception as exc:  # pragma: no cover - startup retry path
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError("Database is not available") from last_error

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Кабинет прогресса"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://tutoring:tutoring@localhost:5433/tutoring_progress",
    )
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    teacher_password: str = os.getenv("TEACHER_PASSWORD", "change-me")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    seed_demo_data: bool = _bool_env("SEED_DEMO_DATA", True)
    tutor_name: str = os.getenv("TUTOR_NAME", "Ваш преподаватель")
    telegram_url: str = os.getenv("TELEGRAM_URL", "https://t.me/")
    whatsapp_url: str = os.getenv("WHATSAPP_URL", "https://wa.me/")
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "uploads"))


settings = Settings()

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    value = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://tutoring:tutoring@localhost:5433/tutoring_progress",
    )
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


def _public_base_url() -> str:
    value = os.getenv("PUBLIC_BASE_URL")
    if value:
        return value.rstrip("/")
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_domain:
        return f"https://{railway_domain.strip('/')}"
    return "http://localhost:8000"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Вектор решений"
    database_url: str = _database_url()
    public_base_url: str = _public_base_url()
    teacher_password: str = os.getenv("TEACHER_PASSWORD", "change-me")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    seed_demo_data: bool = _bool_env("SEED_DEMO_DATA", True)
    tutor_name: str = os.getenv("TUTOR_NAME", "Ваш преподаватель")
    telegram_url: str = os.getenv("TELEGRAM_URL", "https://t.me/")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    whatsapp_url: str = os.getenv("WHATSAPP_URL", "https://wa.me/")
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "uploads"))


settings = Settings()

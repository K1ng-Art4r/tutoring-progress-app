from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models import (
    DIAGNOSTIC_ATTEMPT_STATUS_LABELS,
    LEAD_STATUS_LABELS,
    STUDENT_STATUS_LABELS,
    TOPIC_STATUS_LABELS,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")


def nl2br(value: str | None) -> str:
    if not value:
        return ""
    return "<br>".join(line for line in value.splitlines())


def status_label(value: str) -> str:
    return (
        TOPIC_STATUS_LABELS.get(value)
        or STUDENT_STATUS_LABELS.get(value)
        or LEAD_STATUS_LABELS.get(value)
        or DIAGNOSTIC_ATTEMPT_STATUS_LABELS.get(value)
        or value
    )


def status_class(value: str) -> str:
    return value.replace("_", "-")


def cabinet_url(access_token: str) -> str:
    return f"/cabinet/{access_token}"


templates.env.filters["date"] = format_date
templates.env.filters["nl2br"] = nl2br
templates.env.filters["status_label"] = status_label
templates.env.filters["status_class"] = status_class
templates.env.globals["settings"] = settings
templates.env.globals["cabinet_url"] = cabinet_url

from __future__ import annotations

import hashlib
import html
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

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


def _bold_inline(value: str) -> str:
    escaped = html.escape(value, quote=True)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _normalize_parent_message(value: str) -> str:
    if "**" in value or "\n- " in value or value.lstrip().startswith("###"):
        return value

    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("Ученик прошел диагностику"):
        return value

    by_prefix = {}
    for line in lines[1:]:
        key, separator, rest = line.partition(":")
        if separator:
            by_prefix[key] = rest.strip()

    result = [
        "Здравствуйте!",
        "",
        "### Итог диагностики",
        f"- **Результат:** {lines[0]}",
    ]
    if by_prefix.get("Текущий уровень"):
        result.append(f"- **Текущий уровень:** {by_prefix['Текущий уровень']}")

    result.extend(["", "### Короткий вывод"])
    if by_prefix.get("Вывод"):
        result.append(f"- **Что это значит:** {by_prefix['Вывод']}")
    if by_prefix.get("Что получилось хорошо"):
        result.append(f"- **Получилось уверенно:** {by_prefix['Что получилось хорошо']}")
    if by_prefix.get("Частично получилось"):
        result.append(f"- **Частично получилось:** {by_prefix['Частично получилось']}")
    if by_prefix.get("Основные зоны роста"):
        result.append(f"- **Основные зоны роста:** {by_prefix['Основные зоны роста']}")

    result.extend(["", "### План на ближайшие занятия"])
    if by_prefix.get("Первый фокус подготовки"):
        result.append(f"- **Первый фокус:** {by_prefix['Первый фокус подготовки']}")
    if by_prefix.get("Ориентир"):
        result.append(f"- **Ориентир:** {by_prefix['Ориентир']}")
    if lines[-1] and not lines[-1].partition(":")[1]:
        result.append(f"- **Как будем двигаться:** {lines[-1]}")
    return "\n".join(result)


def rich_text(value: str | None) -> Markup:
    if not value:
        return Markup("")

    text = _normalize_parent_message(value)
    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        if not list_items:
            return
        blocks.append("<ul>" + "".join(list_items) + "</ul>")
        list_items.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue
        if line.startswith("### "):
            flush_list()
            blocks.append(f"<h3>{_bold_inline(line[4:].strip())}</h3>")
            continue
        if line.startswith("- "):
            list_items.append(f"<li>{_bold_inline(line[2:].strip())}</li>")
            continue
        flush_list()
        blocks.append(f"<p>{_bold_inline(line)}</p>")

    flush_list()
    return Markup("".join(blocks))


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


@lru_cache(maxsize=64)
def static_asset(url: str) -> str:
    if not url.startswith("/static/"):
        return url
    path = BASE_DIR / "static" / url.removeprefix("/static/")
    if not path.is_file():
        return url
    version = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"{url}?v={version}"


templates.env.filters["date"] = format_date
templates.env.filters["nl2br"] = nl2br
templates.env.filters["rich_text"] = rich_text
templates.env.filters["status_label"] = status_label
templates.env.filters["status_class"] = status_class
templates.env.globals["settings"] = settings
templates.env.globals["cabinet_url"] = cabinet_url
templates.env.globals["static_asset"] = static_asset

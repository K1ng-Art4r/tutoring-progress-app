from __future__ import annotations

import html
import json
import logging
from urllib import request

from app.config import settings
from app.models import Lead

logger = logging.getLogger(__name__)


def _format_value(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return "не указано"
    return html.escape(cleaned)


def _lead_message(lead: Lead) -> str:
    admin_url = html.escape(f"{settings.public_base_url}/admin", quote=True)
    return "\n".join(
        [
            "<b>Новая заявка с сайта</b>",
            "",
            f"<b>Контактное лицо:</b> {_format_value(lead.parent_name)}",
            f"<b>Класс:</b> {_format_value(lead.student_class)}",
            f"<b>Направление:</b> {_format_value(lead.subject)}",
            f"<b>Цель:</b> {_format_value(lead.goal)}",
            f"<b>Контакт:</b> {_format_value(lead.contact)}",
            "",
            f'<a href="{admin_url}">Открыть заявки в админке</a>',
        ]
    )


def notify_new_lead(lead: Lead) -> None:
    bot_token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    if not bot_token or not chat_id:
        return

    payload = {
        "chat_id": chat_id,
        "text": _lead_message(lead),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    body = json.dumps(payload).encode("utf-8")
    telegram_request = request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(telegram_request, timeout=5) as response:
            if response.status >= 400:
                logger.warning("Telegram notification failed with status %s", response.status)
    except Exception as exc:
        logger.warning("Telegram notification failed: %s", exc)

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.config import settings

COOKIE_NAME = "teacher_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 7


def _sign(payload: str) -> str:
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def create_session_cookie() -> str:
    payload = f"teacher:{int(time.time())}"
    return f"{payload}.{_sign(payload)}"


def is_admin(request: Request) -> bool:
    value = request.cookies.get(COOKIE_NAME)
    if not value or "." not in value:
        return False
    payload, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload), signature):
        return False
    parts = payload.split(":")
    if len(parts) != 2 or parts[0] != "teacher":
        return False
    try:
        issued_at = int(parts[1])
    except ValueError:
        return False
    return time.time() - issued_at <= MAX_AGE_SECONDS


def admin_redirect() -> RedirectResponse:
    return RedirectResponse("/admin/login", status_code=303)


def attach_login_cookie(response: RedirectResponse) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_session_cookie(),
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


def clear_login_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(COOKIE_NAME)

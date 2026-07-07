from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from app.config import settings

COOKIE_NAME = "teacher_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 7
STUDENT_COOKIE_NAME = "student_session"
STUDENT_MAX_AGE_SECONDS = 60 * 60 * 24 * 60


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


def create_student_session_cookie(access_token: str) -> str:
    payload = f"student:{access_token}:{int(time.time())}"
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


def student_access_token_from_cookie(request: Request) -> str | None:
    value = request.cookies.get(STUDENT_COOKIE_NAME)
    if not value or "." not in value:
        return None
    payload, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "student" or not parts[1]:
        return None
    try:
        issued_at = int(parts[2])
    except ValueError:
        return None
    if time.time() - issued_at > STUDENT_MAX_AGE_SECONDS:
        return None
    return parts[1]


def admin_redirect() -> RedirectResponse:
    return RedirectResponse("/admin/login", status_code=303)


def attach_login_cookie(response: Response) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_session_cookie(),
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


def clear_login_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def attach_student_login_cookie(response: Response, access_token: str) -> None:
    response.set_cookie(
        STUDENT_COOKIE_NAME,
        create_student_session_cookie(access_token),
        max_age=STUDENT_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


def clear_student_login_cookie(response: Response) -> None:
    response.delete_cookie(STUDENT_COOKIE_NAME)

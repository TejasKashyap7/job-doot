"""Cookie-session auth for the dashboard.

Single hardcoded password (DASHBOARD_PASSWORD env var). On successful login
we set a signed cookie containing just a marker; verification uses
itsdangerous so the cookie can't be forged.

Stays logged in until the user clears their cookies — no expiry.
"""
from __future__ import annotations

import os

from fastapi import Cookie, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

COOKIE_NAME = "jh_session"
SESSION_VALUE = "ok"

_SECRET = os.getenv("SESSION_SECRET", "")
_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")


def _serializer() -> URLSafeSerializer:
    if not _SECRET:
        raise RuntimeError("SESSION_SECRET not set")
    return URLSafeSerializer(_SECRET, salt="jh-session")


def check_password(submitted: str) -> bool:
    if not _PASSWORD:
        raise RuntimeError("DASHBOARD_PASSWORD not set")
    return submitted == _PASSWORD


def make_cookie_value() -> str:
    return _serializer().dumps(SESSION_VALUE)


def is_valid_cookie(value: str | None) -> bool:
    if not value:
        return False
    try:
        return _serializer().loads(value) == SESSION_VALUE
    except BadSignature:
        return False


def require_login(request: Request, jh_session: str | None = Cookie(default=None)):
    """FastAPI dependency: redirect to /login if not authenticated."""
    if not is_valid_cookie(jh_session):
        # 303 is correct for redirecting after a method that wasn't GET,
        # and works fine for GET too.
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )

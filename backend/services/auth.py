"""Cookie-session auth for the dashboard — per-user (see .claude/specs/multi-user).

Session cookie carries a signed {"uid": <user id>} payload (itsdangerous, can't be
forged). Passwords are bcrypt-hashed, never stored or logged in plaintext.

Stays logged in until the user clears their cookies — no expiry.
"""
from __future__ import annotations

import os

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import User

COOKIE_NAME = "jh_session"

_SECRET = os.getenv("SESSION_SECRET", "")


def _serializer() -> URLSafeSerializer:
    if not _SECRET:
        raise RuntimeError("SESSION_SECRET not set")
    return URLSafeSerializer(_SECRET, salt="jh-session")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def make_cookie_value(user_id: int) -> str:
    return _serializer().dumps({"uid": user_id})


def _decode_cookie(value: str | None) -> int | None:
    if not value:
        return None
    try:
        data = _serializer().loads(value)
    except BadSignature:
        return None
    uid = data.get("uid") if isinstance(data, dict) else None
    return uid if isinstance(uid, int) else None


def require_login(
    request: Request,
    db: Session = Depends(get_db),
    jh_session: str | None = Cookie(default=None),
) -> User:
    """FastAPI dependency: redirect to /login if not authenticated, else return
    the logged-in User row so routes can scope queries to it."""
    uid = _decode_cookie(jh_session)
    user = db.get(User, uid) if uid is not None else None
    if not user:
        # 303 works for redirecting after a non-GET and is fine for GET too.
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )
    return user


def require_admin(user: User = Depends(require_login)) -> User:
    """Stacks on require_login — 403s non-admins rather than redirecting, since
    reaching an admin route while logged in as a normal user is a real error,
    not a missing-session case."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user

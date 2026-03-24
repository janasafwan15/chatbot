from __future__ import annotations
from datetime import datetime, timedelta, timezone
import secrets
import os

from passlib.context import CryptContext
from fastapi import HTTPException, Request

from .db import connect

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SESSION_HOURS        = int(os.getenv("SESSION_HOURS", "24"))
REFRESH_TOKEN_DAYS   = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
now_utc = now_utc_iso          # alias
now_utc_sqlite = now_utc_iso   # backward-compat alias (kept for existing imports)


def make_token() -> str:
    return secrets.token_urlsafe(32)


def create_session(user_id: int, request: Request) -> tuple[str, str]:
    """يرجع (access_token, refresh_token)"""
    access_token  = make_token()
    refresh_token = make_token()

    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    ).strftime("%Y-%m-%d %H:%M:%S")

    refresh_expires_at = (
        datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS)
    ).strftime("%Y-%m-%d %H:%M:%S")

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    con = connect()
    try:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO user_session (
                user_id, session_token, refresh_token,
                ip_address, user_agent,
                expires_at, refresh_expires_at,
                last_activity, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (user_id, access_token, refresh_token,
             ip, ua, expires_at, refresh_expires_at,
             now_utc_iso()),
        )
        con.commit()
    finally:
        con.close()

    return access_token, refresh_token


def refresh_session(refresh_token: str) -> str | None:
    """
    يتحقق من الـ refresh token، ينشئ access token جديد،
    ويرجعه — أو None إذا كان منتهياً أو غير صالح.
    """
    if not refresh_token:
        return None

    con = connect()
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT s.session_id, s.user_id, u.status
            FROM user_session s
            JOIN app_user u ON u.user_id = s.user_id
            WHERE s.refresh_token = %s
              AND s.is_active = 1
              AND u.status = 'active'
              AND s.refresh_expires_at > NOW()
            LIMIT 1
            """,
            (refresh_token,),
        )
        row = cur.fetchone()
        if not row:
            return None

        new_access = make_token()
        new_expires = (
            datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
        ).strftime("%Y-%m-%d %H:%M:%S")

        cur.execute(
            """
            UPDATE user_session
            SET session_token = %s,
                expires_at    = %s,
                last_activity = %s
            WHERE session_id = %s
            """,
            (new_access, new_expires, now_utc_iso(), row["session_id"]),
        )
        con.commit()
        return new_access
    finally:
        con.close()


def get_user_by_token(token: str):
    if not token:
        return None

    con = connect()
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT
              s.session_id,
              s.user_id,
              s.expires_at,
              s.is_active,
              u.username,
              u.role,
              u.full_name,
              u.status,
              u.department_id
            FROM user_session s
            JOIN app_user u ON u.user_id = s.user_id
            WHERE s.session_token = %s
              AND s.is_active = 1
              AND u.status = 'active'
              AND s.expires_at > NOW()
            LIMIT 1
            """,
            (token,),
        )
        row = cur.fetchone()

        if row:
            cur.execute(
                "UPDATE user_session SET last_activity=%s WHERE session_id=%s",
                (now_utc_iso(), row["session_id"]),
            )
            con.commit()

        return dict(row) if row else None
    finally:
        con.close()


def require_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth.split(" ", 1)[1].strip()
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid/expired session")

    return user


def logout_token(token: str) -> None:
    if not token:
        return

    con = connect()
    try:
        cur = con.cursor()
        cur.execute(
            """
            UPDATE user_session
            SET is_active=0, last_activity=%s
            WHERE session_token=%s
            """,
            (now_utc_iso(), token),
        )
        con.commit()
    finally:
        con.close()
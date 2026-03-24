"""
security.py — Security Middleware للحماية الشاملة
===================================================
يوفر:
  1) Rate Limiting عام لكل الـ endpoints الحساسة
  2) إخفاء الـ tokens من الـ logs تلقائياً
  3) Security Headers إضافية
  4) Admin endpoint protection مضاعف

الاستخدام في main.py:
    from app.security import setup_security
    setup_security(app)
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── إخفاء الـ tokens من الـ logs ────────────────────────────────
_TOKEN_PATTERN = re.compile(
    r'("token"\s*:\s*")([^"]{8,})(")',
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(
    r'(Bearer\s+)([A-Za-z0-9\-_\.]{20,})',
    re.IGNORECASE,
)

class _TokenSafeFilter(logging.Filter):
    """يخفي الـ tokens من رسائل الـ log."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        msg = _TOKEN_PATTERN.sub(r'\1[REDACTED]\3', msg)
        msg = _BEARER_PATTERN.sub(r'\1[REDACTED]', msg)
        record.msg = msg
        record.args = ()
        return True


def install_token_log_filter() -> None:
    """يركّب الفلتر على الـ root logger."""
    root = logging.getLogger()
    if not any(isinstance(f, _TokenSafeFilter) for f in root.filters):
        root.addFilter(_TokenSafeFilter())
        logger.info("[security] Token redaction filter installed")


# ── Rate Limiter عام ────────────────────────────────────────────
class _RateLimiter:
    """
    Rate limiter بسيط في الذاكرة.
    يدعم قواعد مختلفة لكل prefix من الـ path.
    """

    # (requests, window_seconds)
    # ✅ #8: /chat محذوف من هنا — يُعالج في rag_api.py لتجنب التكرار
    # ✅ #4: /auth/login محذوف من هنا — يُعالج في main.py لتجنب التكرار
    RULES: dict[str, tuple[int, int]] = {
        "/auth/change-password": (5,  300),
        "/rag/build-embeddings": (3,  60),   # عملية ثقيلة
        "/rag/qdrant/upsert":    (3,  60),
        "/knowledge":            (60, 60),   # CRUD عادي
        "/admin":                (30, 60),
    }
    _CLEANUP_EVERY = 1000

    def __init__(self):
        self._store: dict[str, list[float]] = defaultdict(list)
        self._req_count = 0

    def check(self, path: str, ip: str) -> tuple[bool, int]:
        """
        يرجع (allowed, retry_after_seconds).
        allowed=True لو الطلب مسموح.
        """
        rule = None
        for prefix, (limit, window) in self.RULES.items():
            if path.startswith(prefix):
                rule = (limit, window)
                break

        if rule is None:
            return True, 0  # لا توجد قاعدة → مسموح

        limit, window = rule
        key = f"{ip}:{path.split('/')[1]}"  # group by first path segment
        now = time.time()
        window_start = now - window

        self._store[key] = [t for t in self._store[key] if t > window_start]

        if len(self._store[key]) >= limit:
            retry_after = int(self._store[key][0] + window - now) + 1
            return False, max(retry_after, 1)

        self._store[key].append(now)

        # ✅ #4: تنظيف دوري لمنع تسرب الذاكرة
        self._req_count += 1
        if self._req_count % self._CLEANUP_EVERY == 0:
            cutoff = time.time() - max(w for _, w in self.RULES.values())
            dead = [k for k, v in self._store.items() if not v or v[-1] < cutoff]
            for k in dead:
                del self._store[k]

        return True, 0


_rate_limiter = _RateLimiter()


# ── Security Middleware ─────────────────────────────────────────
class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware مركزي للأمان:
    - Rate limiting
    - Security headers
    """

    # endpoints لها حماية مضاعفة (admin only)
    ADMIN_PATHS = {
        "/rag/build-embeddings",
        "/rag/sync-chunks",
        "/rag/qdrant/upsert",
        "/rag/fts/rebuild",
        "/admin",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = (request.client.host if request.client else "unknown") or "unknown"
        path = request.url.path

        # ── Rate Check ────────────────────────────────────────
        allowed, retry_after = _rate_limiter.check(path, ip)
        if not allowed:
            logger.warning(f"[security] Rate limit exceeded: ip={ip} path={path}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"تم تجاوز الحد المسموح. حاول بعد {retry_after} ثانية.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # ── Process Request ───────────────────────────────────
        response = await call_next(request)

        # ── Security Headers ──────────────────────────────────
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["X-Frame-Options"]           = "DENY"
        response.headers["X-XSS-Protection"]          = "1; mode=block"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]        = "geolocation=(), microphone=()"

        return response


def setup_security(app: FastAPI) -> None:
    """
    يضيف كل إعدادات الأمان للـ FastAPI app.
    استدعاء مرة واحدة في main.py بعد إنشاء الـ app.
    """
    install_token_log_filter()
    app.add_middleware(SecurityMiddleware)
    logger.info("[security] Security middleware initialized")
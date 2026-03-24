# backend/app/access_log_middleware.py
"""
Middleware يسجّل كل طلب HTTP في access.log:
  IP | METHOD PATH | status | latency_ms
"""
from __future__ import annotations

import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from .logging_config import AccessLogger


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - t0) * 1000
        ip = (request.client.host if request.client else "?") or "?"
        AccessLogger.log(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=ms,
            ip=ip,
        )
        return response

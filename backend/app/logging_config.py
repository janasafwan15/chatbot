# backend/app/logging_config.py
"""
نظام Logging احترافي مع 4 ملفات منفصلة:
  - logs/server.log     → كل الأحداث العامة
  - logs/error.log      → الأخطاء فقط (ERROR + CRITICAL)
  - logs/access.log     → كل طلبات HTTP
  - logs/ai.log         → أحداث الـ RAG / LLM / Embeddings
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

# ── مجلد اللوغز ──────────────────────────────────────────────
LOGS_DIR = Path(os.getenv("LOGS_DIR", "/app/logs" if os.path.isdir("/app") else "logs"))
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL    = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_MB   = int(os.getenv("LOG_MAX_MB", "20"))          # حجم كل ملف
LOG_BACKUPS  = int(os.getenv("LOG_BACKUPS", "5"))          # عدد نسخ الأرشيف
LOG_FORMAT   = os.getenv("LOG_FORMAT", "plain")            # plain | json


# ── Formatters ───────────────────────────────────────────────
PLAIN_FMT = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

JSON_FMT = logging.Formatter(
    fmt='{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)

def _fmt() -> logging.Formatter:
    return JSON_FMT if LOG_FORMAT == "json" else PLAIN_FMT


def _rotating(filename: str, level: int) -> logging.handlers.RotatingFileHandler:
    h = logging.handlers.RotatingFileHandler(
        LOGS_DIR / filename,
        maxBytes=LOG_MAX_MB * 1024 * 1024,
        backupCount=LOG_BACKUPS,
        encoding="utf-8",
    )
    h.setLevel(level)
    h.setFormatter(_fmt())
    return h


# ── Filter: Error-only ───────────────────────────────────────
class _ErrorsOnly(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


# ── Filter: Access log ───────────────────────────────────────
class _AccessOnly(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "access", False)


# ── Filter: AI/RAG log ───────────────────────────────────────
class _AiOnly(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "ai", False)


# ── Setup (يُستدعى مرة واحدة عند البدء) ─────────────────────
def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # Console
    console = logging.StreamHandler()
    console.setLevel(LOG_LEVEL)
    console.setFormatter(_fmt())
    root.addHandler(console)

    # server.log — كل الأحداث
    root.addHandler(_rotating("server.log", logging.DEBUG))

    # error.log — أخطاء فقط
    err_h = _rotating("error.log", logging.ERROR)
    err_h.addFilter(_ErrorsOnly())
    root.addHandler(err_h)

    # access.log — طلبات HTTP
    access_h = _rotating("access.log", logging.INFO)
    access_h.addFilter(_AccessOnly())
    root.addHandler(access_h)

    # ai.log — أحداث RAG/LLM
    ai_h = _rotating("ai.log", logging.DEBUG)
    ai_h.addFilter(_AiOnly())
    root.addHandler(ai_h)

    logging.getLogger("uvicorn.access").propagate = False   # لا تكرر في root
    logging.info(f"[logging] Logs dir: {LOGS_DIR}  format={LOG_FORMAT}")


# ── Helper loggers ───────────────────────────────────────────
class AccessLogger:
    """يُستخدم من AccessLogMiddleware"""
    _log = logging.getLogger("access")

    @classmethod
    def log(cls, method: str, path: str, status: int, ms: float, ip: str) -> None:
        record = logging.LogRecord(
            name="access", level=logging.INFO,
            pathname="", lineno=0,
            msg=f'{ip} "{method} {path}" {status} {ms:.1f}ms',
            args=(), exc_info=None,
        )
        record.access = True  # type: ignore[attr-defined]
        cls._log.handle(record)


class AiLogger:
    """يُستخدم من rag_engine وollama_client"""
    _log = logging.getLogger("ai")

    @classmethod
    def log(cls, event: str, **kwargs) -> None:
        extra = "  ".join(f"{k}={v}" for k, v in kwargs.items())
        record = logging.LogRecord(
            name="ai", level=logging.INFO,
            pathname="", lineno=0,
            msg=f"[{event}] {extra}",
            args=(), exc_info=None,
        )
        record.ai = True  # type: ignore[attr-defined]
        cls._log.handle(record)

    @classmethod
    def error(cls, event: str, err: Exception, **kwargs) -> None:
        extra = "  ".join(f"{k}={v}" for k, v in kwargs.items())
        record = logging.LogRecord(
            name="ai", level=logging.ERROR,
            pathname="", lineno=0,
            msg=f"[{event}] ERROR: {err}  {extra}",
            args=(), exc_info=None,
        )
        record.ai = True  # type: ignore[attr-defined]
        cls._log.handle(record)

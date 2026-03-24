"""
conftest.py — إعدادات الاختبار المشتركة
=========================================
يستخدم قاعدة بيانات PostgreSQL مخصصة للاختبارات (hepco_test).
كل test function تبدأ بـ DB نظيفة + rate-limit مُصفَّى.
"""
from __future__ import annotations

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── بيئة الاختبار ──────────────────────────────────────────────────────────
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv(
        "DATABASE_URL",
        "postgresql://hepco:hepco_secret@127.0.0.1:5432/hepco_test",
    ),
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"]   = "test-secret-key-for-testing-only"
os.environ["OLLAMA_BASE"]  = "http://localhost:11434"
os.environ["EMBED_BASE"]   = "http://localhost:11434"
os.environ["LOGS_DIR"]     = "/tmp/hepco_test_logs"

from fastapi.testclient import TestClient


# ── جداول تُفرَّغ بين الاختبارات (ترتيب يحترم FK) ────────────────────────
_TRUNCATE_ORDER = [
    "rag_eval_log",
    "feedback",
    "message",
    "conversation_state",
    "conversation",
    "user_session",
    "kb_changelog",
    "rag_embedding",
    "rag_chunk_fts",
    "rag_chunk",
    "knowledge_base",
    "user_specialization",
    "employee_specialization",
    "app_user",
    "intent",
    "department",
    "audit_trail",
    "system_log",
    "configuration",
]


def _truncate_all(con) -> None:
    cur = con.cursor()
    for tbl in _TRUNCATE_ORDER:
        try:
            cur.execute(f'TRUNCATE TABLE "{tbl}" RESTART IDENTITY CASCADE;')
        except Exception:
            con.rollback()
    con.commit()


def _seed_admin(con) -> None:
    from app.auth import hash_password
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO app_user (username, password_hash, role, full_name,
                              status, must_change_password)
        VALUES (%s, %s, 'admin', 'مدير النظام', 'active', 0)
        ON CONFLICT (username) DO NOTHING;
        """,
        ("admin", hash_password("Admin@123")),
    )
    con.commit()


def _reset_rate_limits() -> None:
    """يمسح جدول rate-limit الخاص بـ brute-force protection بين الاختبارات."""
    try:
        import app.main as _main
        _main._login_attempts.clear()
    except Exception:
        pass


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _init_schema():
    """ينشئ الـ schema مرة واحدة لكل جلسة."""
    from app.db import init_db
    from app.rag_metrics import ensure_eval_table
    init_db()
    ensure_eval_table()


@pytest.fixture(scope="function")
def db_con():
    """اتصال مباشر بـ DB — يُفرَّغ + يُبذر قبل كل اختبار."""
    from app.db import connect
    con = connect()
    _truncate_all(con)
    _seed_admin(con)
    _reset_rate_limits()
    yield con
    con.close()


@pytest.fixture(scope="function")
def client(db_con):
    """TestClient مع DB نظيفة وrate-limit مُصفَّى."""
    from app.main import app
    _reset_rate_limits()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def admin_token(client) -> str:
    resp = client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="function")
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="function")
def employee_headers(client, db_con) -> dict:
    """يضيف موظف اختبار ويعيد headers."""
    from app.auth import hash_password
    cur = db_con.cursor()
    cur.execute(
        """
        INSERT INTO app_user (username, password_hash, role, full_name,
                              status, must_change_password)
        VALUES (%s, %s, 'employee', 'موظف اختبار', 'active', 0)
        ON CONFLICT (username) DO NOTHING;
        """,
        ("test_emp", hash_password("Emp@12345")),
    )
    db_con.commit()
    resp = client.post("/auth/login", json={"username": "test_emp", "password": "Emp@12345"})
    assert resp.status_code == 200, f"Employee login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['token']}"}

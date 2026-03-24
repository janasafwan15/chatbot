"""
run_migration.py
================
يشغّل migration الجداول الجديدة بدون الحاجة لـ psql.

كيف تشغّله:
    cd C:\\Users\\user\\Downloads\\chatbot\\backend
    python run_migration.py

متطلبات: psycopg2 (مثبّت أصلاً في المشروع)
"""

import os
import sys

# ── قراءة DATABASE_URL من .env ──────────────────────────────
def load_env(path=".env"):
    env = {}
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        print(f"⚠️  ما لقيت ملف {path} — سأستخدم DATABASE_URL من environment variables")
    return env

env = load_env()
DATABASE_URL = env.get("DATABASE_URL") or os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ما لقيت DATABASE_URL في .env أو environment variables")
    sys.exit(1)

print(f"🔗 قاعدة البيانات: {DATABASE_URL.split('@')[-1]}")  # يطبع الـ host بدون كلمة المرور

# ── SQL الجديد ───────────────────────────────────────────────
MIGRATION_SQL = """
-- ============================================================
-- Migration: نظام رفع الملفات + الأسئلة غير المجابة
-- ============================================================

-- 1. جدول الملفات المرفوعة
CREATE TABLE IF NOT EXISTS uploaded_file (
    file_id         SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    content         TEXT NOT NULL,
    file_type       TEXT NOT NULL DEFAULT 'text/plain',
    size_bytes      INT  NOT NULL DEFAULT 0,
    uploaded_by     INT  REFERENCES app_user(user_id) ON DELETE SET NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected')),
    rejection_reason TEXT,
    reviewed_by     INT  REFERENCES app_user(user_id) ON DELETE SET NULL,
    reviewed_at     TIMESTAMPTZ,
    kb_id           INT  REFERENCES knowledge_base(kb_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_uploaded_file_status
    ON uploaded_file(status);

CREATE INDEX IF NOT EXISTS idx_uploaded_file_uploaded_by
    ON uploaded_file(uploaded_by);


-- 2. جدول الأسئلة غير المجابة
CREATE TABLE IF NOT EXISTS unanswered_question (
    question_id     SERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    asked_by        TEXT NOT NULL DEFAULT 'مواطن',
    asked_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','answered')),
    answer          TEXT,
    answered_by     INT  REFERENCES app_user(user_id) ON DELETE SET NULL,
    answered_at     TIMESTAMPTZ,
    conversation_id INT  REFERENCES conversation(conversation_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_unanswered_q_status
    ON unanswered_question(status);
"""

# ── تشغيل ───────────────────────────────────────────────────
try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 مش مثبّت. شغّل: pip install psycopg2-binary")
    sys.exit(1)

try:
    print("⏳ جاري الاتصال بقاعدة البيانات...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    print("⏳ جاري تنفيذ الـ migration...")
    cur.execute(MIGRATION_SQL)
    conn.commit()

    # تحقق من إنشاء الجداول
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('uploaded_file', 'unanswered_question')
        ORDER BY table_name
    """)
    tables = [r[0] for r in cur.fetchall()]

    cur.close()
    conn.close()

    print()
    print("✅ تم تشغيل الـ migration بنجاح!")
    print()
    for t in tables:
        print(f"   📋 جدول '{t}' جاهز")

    if len(tables) < 2:
        missing = {"uploaded_file", "unanswered_question"} - set(tables)
        for t in missing:
            print(f"   ⚠️  جدول '{t}' ما اتأكدنا منه — راجع الأخطاء")

    print()
    print("🚀 الباك إيند جاهز. أعد تشغيل السيرفر وجرّب الميزات الجديدة!")

except psycopg2.OperationalError as e:
    print(f"❌ فشل الاتصال بقاعدة البيانات:\n   {e}")
    print()
    print("تأكد من:")
    print("  1. السيرفر شغّال (PostgreSQL)")
    print("  2. DATABASE_URL في .env صحيح")
    sys.exit(1)

except Exception as e:
    print(f"❌ خطأ أثناء تنفيذ الـ migration:\n   {e}")
    if 'conn' in dir() and conn:
        conn.rollback()
        conn.close()
    sys.exit(1)

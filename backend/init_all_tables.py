"""
init_all_tables.py
==================
يشغّل init_db() لإنشاء كل الجداول + migration الملفات والأسئلة.
شغّله من مجلد backend:
    python init_all_tables.py
"""
import os, sys

# اقرأ .env يدوياً
def load_env(path=".env"):
    env = {}
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

env = load_env()
for k, v in env.items():
    os.environ.setdefault(k, v)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://hepco:hepco_secret@localhost:5432/hepco_db")
print(f"🔗 DB: {DATABASE_URL.split('@')[-1]}")

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
except ImportError:
    print("❌ psycopg2 غير مثبت")
    sys.exit(1)

# أضف مجلد app لـ path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

print("⏳ إنشاء كل الجداول الأساسية (init_db)...")
try:
    from app.db import init_db
    init_db()
    print("✅ init_db — كل الجداول الأساسية جاهزة")
except Exception as e:
    print(f"❌ فشل init_db: {e}")
    sys.exit(1)

print("⏳ تشغيل migration الملفات والأسئلة...")
try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("""
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
        CREATE INDEX IF NOT EXISTS idx_uploaded_file_status ON uploaded_file(status);
        CREATE INDEX IF NOT EXISTS idx_uploaded_file_uploaded_by ON uploaded_file(uploaded_by);

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
        CREATE INDEX IF NOT EXISTS idx_unanswered_q_status ON unanswered_question(status);
    """)
    conn.commit()
    conn.close()
    print("✅ migration — uploaded_file و unanswered_question جاهزة")
except Exception as e:
    print(f"❌ فشل migration: {e}")
    sys.exit(1)

# تحقق نهائي
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema='public'
    ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
conn.close()

print()
print(f"📋 الجداول الموجودة الآن ({len(tables)}):")
for t in tables:
    print(f"   ✓ {t}")

print()
print("🚀 الـ DB جاهز! أعد تشغيل السيرفر.")
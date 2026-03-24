# backend/app/db.py
# ✅ PostgreSQL — psycopg2 + connection pool (بديل SQLite)
from __future__ import annotations

import logging
import os
from dotenv import load_dotenv

import psycopg2
import psycopg2.extras
import psycopg2.pool

load_dotenv()

logger = logging.getLogger(__name__)

# =========================
# Connection string
# =========================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://hepco:hepco_secret@localhost:5432/hepco_db",
)

# =========================
# Connection pool
# =========================
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=20,
            dsn=DATABASE_URL,
        )
        logger.info("[db] PostgreSQL connection pool created")
    return _pool


# =========================
# _PgConnection — wrapper يحاكي sqlite3.Connection
# =========================
class _PgConnection:
    def __init__(self):
        self._pool = _get_pool()
        self._conn = self._pool.getconn()
        self._conn.autocommit = False

    def cursor(self) -> psycopg2.extras.RealDictCursor:
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, sql: str, params=()):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._pool.putconn(self._conn)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect() -> _PgConnection:
    return _PgConnection()


# =========================
# lastrowid helper
# PostgreSQL ما عنده lastrowid — يلزم RETURNING
# استخدم: execute_returning(cur, "INSERT ... RETURNING id", params)
# =========================
def execute_returning(cur, sql: str, params=()) -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return 0
    # RealDictRow → نأخذ القيمة الأولى
    return int(list(row.values())[0])


# =========================
# init_db
# =========================
def init_db() -> None:
    con = connect()
    try:
        cur = con.cursor()

        # pgvector — اختياري، لو ما كان مثبتاً يكمل بدونه
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        except Exception:
            logger.warning("[db] pgvector not installed — vector columns disabled")
            con.rollback()  # ✅ مهم — نصفي الـ failed transaction قبل نكمل

        # department
        cur.execute("""
        CREATE TABLE IF NOT EXISTS department (
            department_id     SERIAL PRIMARY KEY,
            department_code   TEXT NOT NULL UNIQUE,
            name_ar           TEXT NOT NULL,
            name_en           TEXT,
            description_ar    TEXT,
            description_en    TEXT,
            manager_id        INTEGER,
            is_active         INTEGER NOT NULL DEFAULT 1,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # system_user
        cur.execute("""
        CREATE TABLE IF NOT EXISTS app_user (
            user_id                 SERIAL PRIMARY KEY,
            username                TEXT NOT NULL UNIQUE,
            password_hash           TEXT NOT NULL,
            role                    TEXT NOT NULL,
            full_name               TEXT NOT NULL,
            email                   TEXT,
            phone                   TEXT,
            department_id           INTEGER REFERENCES department(department_id),
            status                  TEXT NOT NULL DEFAULT 'active',
            last_login              TIMESTAMPTZ,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            must_change_password    INTEGER NOT NULL DEFAULT 1,
            password_changed_at     TIMESTAMPTZ
        );""")

        # user_session
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_session (
            session_id          SERIAL PRIMARY KEY,
            user_id             INTEGER NOT NULL REFERENCES app_user(user_id),
            session_token       TEXT NOT NULL UNIQUE,
            refresh_token       TEXT UNIQUE,
            ip_address          TEXT,
            user_agent          TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at          TIMESTAMPTZ NOT NULL,
            refresh_expires_at  TIMESTAMPTZ,
            last_activity       TIMESTAMPTZ,
            is_active           INTEGER NOT NULL DEFAULT 1
        );""")
        # ✅ أضف الأعمدة لو الجدول موجود قبل هاد التعديل (للـ DB القديمة)
        cur.execute("ALTER TABLE user_session ADD COLUMN IF NOT EXISTS refresh_token TEXT UNIQUE")
        cur.execute("ALTER TABLE user_session ADD COLUMN IF NOT EXISTS refresh_expires_at TIMESTAMPTZ")

        # employee_specialization
        cur.execute("""
        CREATE TABLE IF NOT EXISTS employee_specialization (
            specialization_id        SERIAL PRIMARY KEY,
            specialization_code      TEXT NOT NULL UNIQUE,
            name_ar                  TEXT NOT NULL,
            name_en                  TEXT,
            related_intent_category  TEXT,
            description_ar           TEXT,
            is_active                INTEGER NOT NULL DEFAULT 1,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # user_specialization
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_specialization (
            user_id            INTEGER NOT NULL REFERENCES app_user(user_id),
            specialization_id  INTEGER NOT NULL REFERENCES employee_specialization(specialization_id),
            assigned_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY(user_id, specialization_id)
        );""")

        # intent
        cur.execute("""
        CREATE TABLE IF NOT EXISTS intent (
            intent_id        SERIAL PRIMARY KEY,
            intent_code      TEXT NOT NULL UNIQUE,
            language         TEXT NOT NULL DEFAULT 'ar',
            category         TEXT,
            name_ar          TEXT NOT NULL,
            name_en          TEXT,
            description_ar   TEXT,
            is_active        INTEGER NOT NULL DEFAULT 1,
            priority         INTEGER NOT NULL DEFAULT 0,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # knowledge_base
        cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            kb_id              SERIAL PRIMARY KEY,
            intent_id          INTEGER REFERENCES intent(intent_id),
            language           TEXT NOT NULL DEFAULT 'ar',
            title_ar           TEXT NOT NULL,
            content_ar         TEXT NOT NULL,
            external_links     TEXT,
            category           TEXT,
            is_active          INTEGER NOT NULL DEFAULT 1,
            view_count         INTEGER NOT NULL DEFAULT 0,
            helpful_count      INTEGER NOT NULL DEFAULT 0,
            not_helpful_count  INTEGER NOT NULL DEFAULT 0,
            created_by_user_id INTEGER REFERENCES app_user(user_id),
            created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_reviewed_at   TIMESTAMPTZ
        );""")

        # conversation
        cur.execute("""
        CREATE TABLE IF NOT EXISTS conversation (
            conversation_id       SERIAL PRIMARY KEY,
            user_id               INTEGER REFERENCES app_user(user_id),
            session_id            INTEGER REFERENCES user_session(session_id),
            channel               TEXT,
            language              TEXT NOT NULL DEFAULT 'ar',
            started_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at              TIMESTAMPTZ,
            message_count         INTEGER NOT NULL DEFAULT 0,
            status                TEXT NOT NULL DEFAULT 'open',
            user_rating           INTEGER,
            avg_response_time_ms  INTEGER,
            tags                  TEXT
        );""")

        # message
        cur.execute("""
        CREATE TABLE IF NOT EXISTS message (
            message_id        SERIAL PRIMARY KEY,
            conversation_id   INTEGER NOT NULL REFERENCES conversation(conversation_id),
            intent_id         INTEGER REFERENCES intent(intent_id),
            message_type      TEXT NOT NULL,
            message_text      TEXT NOT NULL,
            response_text     TEXT,
            confidence_score  REAL,
            response_time_ms  INTEGER,
            is_auto_response  INTEGER NOT NULL DEFAULT 0,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            intent_pred       TEXT,
            intent_conf       REAL,
            response_mode     TEXT,
            best_score        REAL,
            answer_found      INTEGER,
            source_file       TEXT,
            source_chunk_id   TEXT,
            category          TEXT
        );""")

        # conversation_state
        cur.execute("""
        CREATE TABLE IF NOT EXISTS conversation_state (
            conversation_id INTEGER PRIMARY KEY REFERENCES conversation(conversation_id),
            state_json      TEXT NOT NULL,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # feedback
        cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id     SERIAL PRIMARY KEY,
            message_id      INTEGER REFERENCES message(message_id),
            conversation_id INTEGER REFERENCES conversation(conversation_id),
            user_id         INTEGER REFERENCES app_user(user_id),
            rating          INTEGER,
            feedback_type   TEXT,
            comments        TEXT,
            submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # audit_trail
        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            audit_id       SERIAL PRIMARY KEY,
            table_name     TEXT NOT NULL,
            record_id      INTEGER NOT NULL,
            action         TEXT NOT NULL,
            user_id        INTEGER REFERENCES app_user(user_id),
            old_values     TEXT,
            new_values     TEXT,
            changed_fields TEXT,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # system_log
        cur.execute("""
        CREATE TABLE IF NOT EXISTS system_log (
            log_id       SERIAL PRIMARY KEY,
            user_id      INTEGER REFERENCES app_user(user_id),
            action_type  TEXT,
            module       TEXT NOT NULL,
            severity     TEXT NOT NULL DEFAULT 'INFO',
            ip_address   TEXT,
            user_agent   TEXT,
            details      TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # configuration
        cur.execute("""
        CREATE TABLE IF NOT EXISTS configuration (
            config_id          SERIAL PRIMARY KEY,
            config_key         TEXT NOT NULL UNIQUE,
            config_value       TEXT NOT NULL,
            data_type          TEXT,
            category           TEXT,
            description_ar     TEXT,
            is_editable        INTEGER NOT NULL DEFAULT 1,
            is_encrypted       INTEGER NOT NULL DEFAULT 0,
            updated_by_user_id INTEGER REFERENCES app_user(user_id),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # kb_changelog
        cur.execute("""
        CREATE TABLE IF NOT EXISTS kb_changelog (
            change_id    SERIAL PRIMARY KEY,
            kb_id        INTEGER NOT NULL,
            action       TEXT NOT NULL,
            user_id      INTEGER NOT NULL,
            old_question TEXT,
            old_answer   TEXT,
            new_question TEXT,
            new_answer   TEXT,
            changed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # RAG tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_chunk (
            chunk_id      TEXT PRIMARY KEY,
            source_file   TEXT,
            text          TEXT NOT NULL,
            metadata_json TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_embedding (
            chunk_id    TEXT PRIMARY KEY REFERENCES rag_chunk(chunk_id),
            model       TEXT NOT NULL,
            dims        INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""")

        # FTS table — tsvector بدل FTS5
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_chunk_fts (
            chunk_id TEXT PRIMARY KEY REFERENCES rag_chunk(chunk_id),
            tsv      TSVECTOR
        );""")

        # =========================
        # Indexes
        # =========================
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_session_user ON user_session(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_session_refresh ON user_session(refresh_token) WHERE refresh_token IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS idx_kb_intent ON knowledge_base(intent_id);",
            "CREATE INDEX IF NOT EXISTS idx_msg_conv ON message(conversation_id);",
            "CREATE INDEX IF NOT EXISTS idx_msg_conv_created ON message(conversation_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_feedback_msg ON feedback(message_id);",
            "CREATE INDEX IF NOT EXISTS idx_feedback_conv ON feedback(conversation_id);",
            "CREATE INDEX IF NOT EXISTS idx_feedback_type_date ON feedback(feedback_type, submitted_at);",
            "CREATE INDEX IF NOT EXISTS idx_feedback_conv_date ON feedback(conversation_id, submitted_at);",
            "CREATE INDEX IF NOT EXISTS idx_state_conv ON conversation_state(conversation_id);",
            "CREATE INDEX IF NOT EXISTS idx_kb_changelog_kb ON kb_changelog(kb_id);",
            "CREATE INDEX IF NOT EXISTS idx_rag_embedding_model ON rag_embedding(model);",
            "CREATE INDEX IF NOT EXISTS idx_rag_fts_tsv ON rag_chunk_fts USING GIN(tsv);",
        ]
        for idx_sql in indexes:
            try:
                cur.execute(idx_sql)
            except Exception as e:
                logger.warning(f"[db] index warning: {e}")

        con.commit()
        logger.info("[db] init_db completed ✅")

    except Exception as e:
        con.rollback()
        logger.error(f"[db] init_db failed: {e}")
        raise
    finally:
        con.close()
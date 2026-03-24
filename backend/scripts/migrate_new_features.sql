-- ============================================================
-- Migration: نظام رفع الملفات + الأسئلة غير المجابة
-- ============================================================

-- 1. جدول الملفات المرفوعة
CREATE TABLE IF NOT EXISTS uploaded_file (
    file_id         SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    content         TEXT NOT NULL,               -- محتوى الملف (نص)
    file_type       TEXT NOT NULL DEFAULT 'text/plain',
    size_bytes      INT  NOT NULL DEFAULT 0,
    uploaded_by     INT  REFERENCES app_user(user_id) ON DELETE SET NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected')),
    rejection_reason TEXT,
    reviewed_by     INT  REFERENCES app_user(user_id) ON DELETE SET NULL,
    reviewed_at     TIMESTAMPTZ,
    kb_id           INT  REFERENCES knowledge_base(kb_id) ON DELETE SET NULL  -- الـ KB entry لما يتوافق
);

CREATE INDEX IF NOT EXISTS idx_uploaded_file_status      ON uploaded_file(status);
CREATE INDEX IF NOT EXISTS idx_uploaded_file_uploaded_by ON uploaded_file(uploaded_by);


-- 2. جدول الأسئلة غير المجابة
CREATE TABLE IF NOT EXISTS unanswered_question (
    question_id     SERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    asked_by        TEXT NOT NULL DEFAULT 'مواطن',  -- مؤقتاً نص، لأن المواطن مش مسجل
    asked_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','answered')),
    answer          TEXT,
    answered_by     INT  REFERENCES app_user(user_id) ON DELETE SET NULL,
    answered_at     TIMESTAMPTZ,
    conversation_id INT  REFERENCES conversation(conversation_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_unanswered_q_status ON unanswered_question(status);

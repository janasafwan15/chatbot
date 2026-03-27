# backend/app/routers/unanswered_routes.py
"""
نظام الأسئلة غير المجابة
- POST /unanswered              - مواطن يُسجّل سؤال لم يجب عليه AI
- GET  /unanswered              - موظف/إدارة يشوفون القائمة
- POST /unanswered/{q_id}/answer - موظف يجيب → يُضاف لـ KB تلقائياً
- DELETE /unanswered/{q_id}     - إدارة تحذف
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import connect
from ..auth import require_auth, now_utc_sqlite
from ..rbac import require_roles

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unanswered", tags=["unanswered"])

# ── Schemas ─────────────────────────────────────────────────

class UnansweredQuestionIn(BaseModel):
    question:        str          = Field(..., min_length=3, max_length=1000)
    conversation_id: Optional[int] = None

class AnswerIn(BaseModel):
    answer: str = Field(..., min_length=3, max_length=3000)

class QuestionOut(BaseModel):
    question_id:     int
    question:        str
    asked_by:        str
    asked_at:        str
    status:          str
    answer:          Optional[str] = None
    answered_by:     Optional[int] = None
    answered_by_name: Optional[str] = None
    answered_at:     Optional[str] = None
    conversation_id: Optional[int] = None


# ── Helpers ─────────────────────────────────────────────────

def _row_to_out(row: dict) -> dict:
    return {
        "question_id":      row["question_id"],
        "question":         row["question"],
        "asked_by":         row.get("asked_by") or "مواطن",
        "asked_at":         str(row["asked_at"]),
        "status":           row["status"],
        "answer":           row.get("answer"),
        "answered_by":      row.get("answered_by"),
        "answered_by_name": row.get("answered_by_name"),
        "answered_at":      str(row["answered_at"]) if row.get("answered_at") else None,
        "conversation_id":  row.get("conversation_id"),
    }


def _add_qa_to_kb(question: str, answer: str, answered_by_id: int) -> int:
    """يضيف زوج سؤال/جواب لـ knowledge_base ويعيد kb_id."""
    from ..main import sync_kb_to_rag
    con = connect()
    cur = con.cursor()
    title   = f"[سؤال مواطن] {question[:80]}"
    content = f"السؤال: {question}\nالإجابة: {answer}"
    cur.execute(
        """INSERT INTO knowledge_base
             (intent_id, language, title_ar, content_ar, external_links,
              category, is_active, created_by_user_id, updated_at)
           VALUES (NULL, 'ar', %s, %s, NULL, 'أسئلة_مواطنين', 1, %s, NOW())
           RETURNING kb_id""",
        (title, content, answered_by_id),
    )
    kb_id = cur.fetchone()["kb_id"]
    con.commit()
    con.close()

    try:
        sync_kb_to_rag(
            kb_id=kb_id,
            title=title,
            content=content,
            category="أسئلة_مواطنين",
            intent_code=None,
            is_active=True,
        )
    except Exception as e:
        logger.warning(f"[unanswered] RAG sync failed for kb_{kb_id}: {e}")

    return kb_id


# ── Routes ──────────────────────────────────────────────────

@router.post("", status_code=201)
def submit_unanswered(body: UnansweredQuestionIn, request: Request):
    """
    يُسجّل سؤالاً لم يستطع AI الإجابة عليه.
    لا يحتاج مصادقة — المواطن يرسله مباشرة.
    """
    con = connect()
    cur = con.cursor()

    # تجنب تسجيل نفس السؤال مرتين خلال 10 دقائق
    cur.execute(
        """SELECT question_id FROM unanswered_question
           WHERE question = %s AND status = 'pending'
             AND asked_at > NOW() - INTERVAL '10 minutes'
           LIMIT 1""",
        (body.question.strip(),),
    )
    if cur.fetchone():
        con.close()
        return {"ok": True, "duplicate": True}

    cur.execute(
        """INSERT INTO unanswered_question
             (question, asked_by, asked_at, status, conversation_id)
           VALUES (%s, 'مواطن', NOW(), 'pending', %s)
           RETURNING question_id""",
        (body.question.strip(), body.conversation_id),
    )
    q_id = cur.fetchone()["question_id"]
    con.commit()
    con.close()

    logger.info(f"[unanswered] new question_id={q_id}")
    return {"ok": True, "question_id": q_id}


@router.get("", response_model=list[QuestionOut])
def list_questions(request: Request, status: Optional[str] = None):
    """موظف/إدارة يشوفون قائمة الأسئلة"""
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])

    where = ""
    params: list = []
    if status and status in ("pending", "answered"):
        where = "WHERE uq.status = %s"
        params.append(status)

    con = connect()
    cur = con.cursor()
    cur.execute(
        f"""SELECT uq.question_id, uq.question, uq.asked_by, uq.asked_at,
                   uq.status, uq.answer, uq.answered_by, uq.answered_at,
                   uq.conversation_id,
                   u.full_name AS answered_by_name
            FROM unanswered_question uq
            LEFT JOIN app_user u ON u.user_id = uq.answered_by
            {where}
            ORDER BY uq.asked_at DESC""",
        tuple(params),
    )
    rows = cur.fetchall()
    con.close()
    return [QuestionOut(**_row_to_out(dict(r))) for r in rows]


@router.post("/{question_id}/answer")
def answer_question(question_id: int, body: AnswerIn, request: Request):
    """موظف يجيب على السؤال → يُضاف لـ KB + RAG تلقائياً"""
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute(
        "SELECT * FROM unanswered_question WHERE question_id = %s LIMIT 1",
        (question_id,),
    )
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="السؤال غير موجود")

    row = dict(row)
    if row["status"] != "pending":
        con.close()
        raise HTTPException(status_code=400, detail="السؤال تمت الإجابة عليه مسبقاً")

    # إضافة لـ KB
    kb_id = _add_qa_to_kb(
        question=row["question"],
        answer=body.answer.strip(),
        answered_by_id=int(me["user_id"]),
    )

    cur.execute(
        """UPDATE unanswered_question
           SET status='answered', answer=%s, answered_by=%s, answered_at=NOW()
           WHERE question_id=%s""",
        (body.answer.strip(), int(me["user_id"]), question_id),
    )
    con.commit()
    con.close()

    logger.info(f"[unanswered] answered question_id={question_id} → kb_id={kb_id} by user_id={me['user_id']}")
    return {"ok": True, "kb_id": kb_id}


@router.delete("/{question_id}")
def delete_question(question_id: int, request: Request):
    """إدارة تحذف سؤالاً"""
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute("SELECT 1 FROM unanswered_question WHERE question_id = %s", (question_id,))
    if not cur.fetchone():
        con.close()
        raise HTTPException(status_code=404, detail="السؤال غير موجود")

    cur.execute("DELETE FROM unanswered_question WHERE question_id = %s", (question_id,))
    con.commit()
    con.close()
    return {"ok": True}


# ── Citizen: تحقق من إجابات أسئلتك ────────────────────────

@router.get("/my-answers")
def get_my_answers(conversation_id: int):
    """
    المواطن يتحقق من إجابات أسئلته بناءً على conversation_id.
    لا يحتاج مصادقة — المواطن يرسله مباشرة.
    يرجع فقط الأسئلة التي تم الإجابة عليها.
    """
    con = connect()
    cur = con.cursor()
    cur.execute(
        """SELECT uq.question_id, uq.question, uq.asked_at,
                  uq.status, uq.answer, uq.answered_at,
                  u.full_name AS answered_by_name
           FROM unanswered_question uq
           LEFT JOIN app_user u ON u.user_id = uq.answered_by
           WHERE uq.conversation_id = %s
           ORDER BY uq.asked_at DESC""",
        (conversation_id,),
    )
    rows = cur.fetchall()
    con.close()

    result = []
    for r in rows:
        row = dict(r)
        result.append({
            "question_id":      row["question_id"],
            "question":         row["question"],
            "asked_at":         str(row["asked_at"]),
            "status":           row["status"],
            "answer":           row.get("answer"),
            "answered_at":      str(row["answered_at"]) if row.get("answered_at") else None,
            "answered_by_name": row.get("answered_by_name"),
        })
    return result


# ── Stats ─────────────────────────────────────────────────

@router.get("/stats/summary")
def questions_stats(request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status='pending')  AS pending_count,
            COUNT(*) FILTER (WHERE status='answered') AS answered_count,
            COUNT(*)                                   AS total_count
        FROM unanswered_question
    """)
    row = dict(cur.fetchone())
    con.close()
    return row
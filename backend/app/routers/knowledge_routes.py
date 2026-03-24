# routers/knowledge_routes.py
# Improvements:
#   1) Cache invalidation ذكي عند كل تعديل على الـ KB
#   2) KB Versioning بسيط — سجل تاريخ التعديلات (مين عدّل ومتى وماذا)

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import logging

from ..auth import require_auth, now_utc_sqlite
from ..rbac import require_roles
from ..db import connect, execute_returning
from ..answer_cache import get_answer_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeCreate(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None
    is_active: bool = True


class KnowledgeUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


# ─── Cache Invalidation Helper ─────────────────────────────────
def _invalidate_kb_cache(question: Optional[str] = None) -> int:
    """
    يمسح الـ Answer Cache عند تعديل الـ KB.
    دايماً يمسح الكل لضمان consistency مع الـ fuzzy matches.
    """
    cache = get_answer_cache()
    if question:
        cache.invalidate(question)  # partial invalidation أولاً
    n = cache.clear()               # ثم full clear للسلامة
    logger.info(f"[cache] KB change → cleared {n} cached answers")
    return n


# ─── KB Versioning Helper ──────────────────────────────────────
# ✅ اقتراح أ: kb_changelog جدوله في init_db() — مش هنا
def _record_kb_version(
    kb_id: int, action: str, user_id: int,
    old_question: Optional[str] = None, old_answer: Optional[str] = None,
    new_question: Optional[str] = None, new_answer: Optional[str] = None,
) -> None:
    """يسجل نسخة في جدول kb_changelog — مين عدّل ومتى وماذا غيّر."""
    try:
        con = connect()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO kb_changelog
                (kb_id, action, user_id, old_question, old_answer, new_question, new_answer, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (kb_id, action, user_id, old_question, old_answer, new_question, new_answer, now_utc_sqlite()))
        con.commit()
        con.close()
    except Exception as e:
        logger.warning(f"[kb_version] failed: {e}")


# ─── Endpoints ─────────────────────────────────────────────────

@router.get("")
def list_items(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    offset = (page - 1) * page_size
    con = connect()
    try:
        cur = con.cursor()
        cur.execute("""
            SELECT kb_id, title_ar, content_ar, category, is_active, updated_at
            FROM knowledge_base ORDER BY updated_at DESC LIMIT %s OFFSET %s
        """, (page_size, offset))
        rows = cur.fetchall()
        total = con.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()[0]
    finally:
        con.close()
    return {
        "items": [{"id": r["kb_id"], "question": r["title_ar"],
                   "answer": r["content_ar"], "category": r["category"] or "",
                   "is_active": bool(r["is_active"]), "updatedAt": r["updated_at"]}
                  for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/changelog/{item_id}")
def get_kb_changelog(item_id: int, request: Request):
    """تاريخ تعديلات عنصر KB — للـ supervisor والـ admin فقط"""
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])
    try:
        con = connect()
        cur = con.cursor()
        cur.execute("""
            SELECT c.change_id, c.action, c.user_id,
                   COALESCE(u.username, 'unknown') as username,
                   c.old_question, c.new_question,
                   c.old_answer, c.new_answer, c.changed_at
            FROM kb_changelog c
            LEFT JOIN app_user u ON u.user_id = c.user_id
            WHERE c.kb_id = %s
            ORDER BY c.changed_at DESC LIMIT 50
        """, (item_id,))
        rows = cur.fetchall()
        con.close()
        return {"kb_id": item_id, "changelog": [dict(r) for r in rows]}
    except Exception as e:
        return {"kb_id": item_id, "changelog": [], "error": str(e)}


@router.post("")
def create_item(payload: KnowledgeCreate, request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    con = connect()
    try:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO knowledge_base (title_ar, content_ar, category, is_active, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (payload.question.strip(), payload.answer.strip(), payload.category,
              1 if payload.is_active else 0, int(me["user_id"])))
        con.commit()
        kb_id = execute_returning(cur, "SELECT lastval()")
    finally:
        con.close()

    try:
        from ..main import sync_kb_to_rag
        sync_kb_to_rag(kb_id=kb_id, title=payload.question.strip(),
                       content=payload.answer.strip(), category=payload.category,
                       intent_code=None, is_active=payload.is_active)
    except Exception as e:
        logger.warning(f"[kb] RAG sync failed on create: {e}")

    _invalidate_kb_cache(payload.question)
    _record_kb_version(kb_id=kb_id, action="create", user_id=int(me["user_id"]),
                       new_question=payload.question.strip(), new_answer=payload.answer.strip())
    return {"ok": True, "kb_id": kb_id}


@router.put("/{item_id}")
def update_item(item_id: int, payload: KnowledgeUpdate, request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    con = connect()
    try:
        cur = con.cursor()
        old_row = cur.execute(
            "SELECT title_ar, content_ar FROM knowledge_base WHERE kb_id=%s", (item_id,)
        ).fetchone()
        if not old_row:
            raise HTTPException(status_code=404, detail="Not found")

        old_question, old_answer = old_row["title_ar"], old_row["content_ar"]

        fields, values = [], []
        if payload.question is not None:
            fields.append("title_ar=%s"); values.append(payload.question.strip())
        if payload.answer is not None:
            fields.append("content_ar=%s"); values.append(payload.answer.strip())
        if payload.category is not None:
            fields.append("category=%s"); values.append(payload.category)
        if payload.is_active is not None:
            fields.append("is_active=%s"); values.append(1 if payload.is_active else 0)
        if not fields:
            return {"ok": True}
        fields.append("updated_at=NOW()")
        cur.execute(f"UPDATE knowledge_base SET {', '.join(fields)} WHERE kb_id=%s",
                    tuple(values + [item_id]))
        con.commit()
        updated = cur.execute(
            "SELECT title_ar, content_ar, category, is_active FROM knowledge_base WHERE kb_id=%s",
            (item_id,)).fetchone()
    finally:
        con.close()

    if updated:
        try:
            from ..main import sync_kb_to_rag
            sync_kb_to_rag(kb_id=item_id, title=updated["title_ar"],
                           content=updated["content_ar"], category=updated["category"],
                           intent_code=None, is_active=bool(updated["is_active"]))
        except Exception as e:
            logger.warning(f"[kb] RAG sync failed on update: {e}")

        _invalidate_kb_cache(old_question)
        _record_kb_version(kb_id=item_id, action="update", user_id=int(me["user_id"]),
                           old_question=old_question, old_answer=old_answer,
                           new_question=updated["title_ar"], new_answer=updated["content_ar"])
    return {"ok": True}


@router.delete("/{item_id}")
def delete_item(item_id: int, request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    con = connect()
    try:
        cur = con.cursor()
        old_row = cur.execute(
            "SELECT title_ar, content_ar FROM knowledge_base WHERE kb_id=%s", (item_id,)
        ).fetchone()
        if not old_row:
            raise HTTPException(status_code=404, detail="Not found")
        old_question, old_answer = old_row["title_ar"], old_row["content_ar"]
        cur.execute("DELETE FROM knowledge_base WHERE kb_id=%s", (item_id,))
        con.commit()
    finally:
        con.close()

    try:
        from ..main import delete_kb_from_rag
        delete_kb_from_rag(item_id)
    except Exception as e:
        logger.warning(f"[kb] RAG delete sync failed: {e}")

    _invalidate_kb_cache(old_question)
    _record_kb_version(kb_id=item_id, action="delete", user_id=int(me["user_id"]),
                       old_question=old_question, old_answer=old_answer)
    return {"ok": True}
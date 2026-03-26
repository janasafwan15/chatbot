from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from .db import connect, execute_returning
from .auth import require_auth, now_utc_iso
from .rbac import require_roles

from .rag_engine import (
    RagResult,
    answer_with_rag,
    ping_ollama,
    upsert_chunks_into_db,
    build_embeddings,
)

def _audit(user_id: int, action: str, details: str = "") -> None:
    try:
        con = connect()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO audit_trail (table_name, record_id, action, user_id, new_values, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            ("rag_system", 0, action, user_id, details, now_utc_iso()),
        )
        con.commit()
        con.close()
    except Exception:
        pass

try:
    from .qdrant_sync import upsert_qdrant_from_db
except ImportError:
    from .qdrant_sync import upsert_qdrant_from_sqlite as upsert_qdrant_from_db  # legacy name
from .hybrid_retrieve import rebuild_fts_from_rag_chunk

router = APIRouter()

# ─── Rate Limiter بسيط ──────────────────────────────────────
# ✅ #4: حماية /chat من الاستنزاف مع إصلاح تسرب الذاكرة
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = int(os.getenv("CHAT_RATE_LIMIT", "20"))
RATE_LIMIT_WINDOW   = int(os.getenv("CHAT_RATE_WINDOW", "60"))
_RATE_CLEANUP_EVERY = 500   # كل 500 طلب نمسح الـ IPs الخاملة
_rate_request_count = 0

def _check_rate_limit(request: Request) -> None:
    global _rate_request_count
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # احذف الطلبات القديمة لهذا الـ IP
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]

    if len(_rate_store[ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"تم تجاوز الحد المسموح ({RATE_LIMIT_REQUESTS} رسالة/{RATE_LIMIT_WINDOW}ث). يرجى الانتظار قليلاً."
        )

    _rate_store[ip].append(now)

    # ✅ #4: تنظيف دوري للـ IPs الخاملة لمنع تسرب الذاكرة
    _rate_request_count += 1
    if _rate_request_count % _RATE_CLEANUP_EVERY == 0:
        cutoff = now - RATE_LIMIT_WINDOW
        dead_keys = [k for k, v in _rate_store.items() if not v or v[-1] < cutoff]
        for k in dead_keys:
            del _rate_store[k]


def _auth_admin(request: Request):
    user = require_auth(request)
    require_roles(user, ["admin"])
    return user


MAX_QUESTION_LEN = int(os.getenv("MAX_QUESTION_LEN", "1000"))

class ChatRequest(BaseModel):
    # ✅ #5: حد أقصى لطول السؤال لمنع استنزاف الموارد
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LEN)
    conversation_id: Optional[int] = None

    @field_validator("question")
    @classmethod
    def _strip_question(cls, v: str) -> str:
        return v.strip()


def create_conversation() -> int:
    con = connect()
    cur = con.cursor()
    from .db import execute_returning
    cid = execute_returning(cur, "INSERT INTO conversation (status) VALUES ('open') RETURNING conversation_id")
    con.commit()
    con.close()
    return cid


def save_user_message(conversation_id: int, text: str) -> int:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO message (conversation_id, message_type, message_text, is_auto_response)
        VALUES (%s, 'user', %s, 0)
        """,
        (conversation_id, text),
    )
    con.commit()
    mid = execute_returning(cur, "SELECT lastval()")
    con.close()
    return mid


def save_assistant_message(
    conversation_id: int,
    question_text: str,
    answer_text: str,
    response_mode: str,
    best_score: Optional[float] = None,
    answer_found: int = 1,
    source_file: Optional[str] = None,
    source_chunk_id: Optional[str] = None,
    intent_pred: Optional[str] = None,
    intent_conf: Optional[float] = None,
    category: Optional[str] = None,
) -> int:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO message (
            conversation_id, message_type, message_text, response_text,
            confidence_score, is_auto_response,
            response_mode, best_score, answer_found,
            source_file, source_chunk_id,
            intent_pred, intent_conf, category
        )
        VALUES (%s, 'assistant', %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            conversation_id,
            question_text,
            answer_text,
            1.0,
            response_mode,
            float(best_score) if best_score is not None else None,
            int(answer_found),
            source_file,
            source_chunk_id,
            intent_pred,
            intent_conf,
            category,
        ),
    )
    con.commit()
    mid = execute_returning(cur, "SELECT lastval()")
    con.close()
    return mid


@router.get("/health-rag")
def health_rag() -> Dict[str, Any]:
    import time as _t
    from .qdrant_client import qdrant_enabled, get_collection_info, QDRANT_COLLECTION
    from .rag_engine import ping_ollama, ping_embeddings, get_embed_cache_stats

    # Ollama LLM
    t0 = _t.perf_counter()
    ollama_ok = ping_ollama()
    ollama_ms = round((_t.perf_counter() - t0) * 1000)

    # Embeddings
    t0 = _t.perf_counter()
    embed_ok = ping_embeddings()
    embed_ms = round((_t.perf_counter() - t0) * 1000)

    # Qdrant
    qdrant_ok = False
    qdrant_points = 0
    qdrant_status = "disabled"
    if qdrant_enabled():
        try:
            t0 = _t.perf_counter()
            info = get_collection_info(QDRANT_COLLECTION)
            qdrant_ms = round((_t.perf_counter() - t0) * 1000)
            if info:
                result = info.get("result") or {}
                qdrant_ok = result.get("status") == "green"
                qdrant_points = result.get("points_count", 0)
                qdrant_status = result.get("status", "unknown")
            else:
                qdrant_status = "collection_not_found"
        except Exception as e:
            qdrant_status = f"error: {e}"
            qdrant_ms = 0
    else:
        qdrant_ms = 0

    # PostgreSQL DB
    db_ok = False
    db_ms = 0
    db_error = None
    chunk_count = 0
    embed_count = 0
    import os as _os
    db_name = (_os.getenv("DATABASE_URL", "").split("/")[-1].split("?")[0] or "hepco_db")
    try:
        import time as _t2
        t0 = _t2.perf_counter()
        con = connect()
        row = con.execute("SELECT COUNT(*) AS cnt FROM rag_chunk").fetchone()
        chunk_count = int(row["cnt"]) if row else 0
        row = con.execute("SELECT COUNT(*) AS cnt FROM rag_embedding").fetchone()
        embed_count = int(row["cnt"]) if row else 0
        con.close()
        db_ok = True
        db_ms = round((_t2.perf_counter() - t0) * 1000)
    except Exception as e:
        db_error = str(e)[:120]

    overall_ok = ollama_ok and embed_ok and db_ok

    postgres_info: dict = {
        "ok": db_ok,
        "latency_ms": db_ms,
        "db_name": db_name,
        "chunks": chunk_count,
        "embeddings": embed_count,
    }
    if db_error:
        postgres_info["error"] = db_error

    return {
        "ok": overall_ok,
        "services": {
            "ollama_llm":  {"ok": ollama_ok, "latency_ms": ollama_ms},
            "embeddings":  {"ok": embed_ok,  "latency_ms": embed_ms},
            "qdrant":      {"ok": qdrant_ok, "latency_ms": qdrant_ms,
                            "status": qdrant_status, "points": qdrant_points},
            "postgres_db": postgres_info,
        },
        "embed_cache": get_embed_cache_stats(),
    }


@router.post("/rag/sync-chunks")
def rag_sync_chunks(_user=Depends(_auth_admin)) -> Dict[str, Any]:
    n = upsert_chunks_into_db()
    return {"ok": True, "chunks_upserted": n}


@router.post("/rag/build-embeddings")
def rag_build_embeddings(
    limit: Optional[int] = None,
    overwrite: bool = False,
    _user=Depends(_auth_admin),
) -> Dict[str, Any]:
    result = build_embeddings(limit=limit, overwrite=overwrite)
    _audit(int(_user["user_id"]), "build_embeddings",
           f"built={result.get('embeddings_built')} skipped={result.get('skipped')} errors={len(result.get('errors', []))}")
    return result


@router.post("/chat")
def chat(req: ChatRequest, request: Request):
    # FIX 6: Rate limit — 20 رسالة/دقيقة لكل IP
    _check_rate_limit(request)

    question_raw = (req.question or "").strip()
    if not question_raw:
        return {
            "answer": "اكتبي سؤالك لو سمحتي.",
            "sources": [],
            "conversation_id": req.conversation_id,
            "mode": "empty",
        }

    # ✅ #3: التحقق من conversation_id قبل الاستخدام
    if req.conversation_id:
        cid = int(req.conversation_id)
        con = connect()
        cur = con.cursor()
        cur.execute("SELECT 1 FROM conversation WHERE conversation_id=%s LIMIT 1", (cid,))
        exists = cur.fetchone()
        con.close()
        if not exists:
            raise HTTPException(status_code=404, detail="conversation_id غير موجود")
    else:
        cid = create_conversation()

    user_mid = save_user_message(conversation_id=cid, text=question_raw)

    res: RagResult = answer_with_rag(question_raw, conversation_id=cid)

    best_chunk = res.sources[0] if res.sources else None
    assistant_mid = save_assistant_message(
        conversation_id=cid,
        question_text=question_raw,
        answer_text=res.answer,
        response_mode=res.mode,
        best_score=res.best_score,
        answer_found=1 if res.sources else 0,
        source_file=(best_chunk or {}).get("file"),
        source_chunk_id=(best_chunk or {}).get("chunk_id"),
        intent_pred=getattr(res, "intent", None),
        intent_conf=getattr(res, "confidence", None),
        category=getattr(res, "category", None),
    )

    # ✅ حفظ السؤال تلقائياً في unanswered_question لو ما لقى جواب
    if not res.sources:
        try:
            con2 = connect()
            cur2 = con2.cursor()
            # تجنب التكرار خلال 10 دقائق
            cur2.execute(
                """SELECT question_id FROM unanswered_question
                   WHERE question = %s AND status = 'pending'
                     AND asked_at > NOW() - INTERVAL '10 minutes'
                   LIMIT 1""",
                (question_raw,),
            )
            if not cur2.fetchone():
                cur2.execute(
                    """INSERT INTO unanswered_question
                         (question, asked_by, asked_at, status, conversation_id)
                       VALUES (%s, 'مواطن', NOW(), 'pending', %s)""",
                    (question_raw, cid),
                )
                con2.commit()
                logger.info(f"[unanswered] auto-saved question from chat: conv={cid}")
            con2.close()
        except Exception as e:
            logger.warning(f"[unanswered] failed to auto-save: {e}")

    # ✅ RAG Evaluation Metrics (Precision / Recall / F1) — يحفظ في rag_eval_log
    try:
        from .rag_metrics import eval_from_rag_result, save_eval_to_db
        retrieved_ids = [s.get("chunk_id") for s in (res.sources or []) if s.get("chunk_id")]
        if retrieved_ids:
            ev = eval_from_rag_result(
                question=question_raw,
                retrieved_chunk_ids=retrieved_ids,
                best_score=res.best_score,
                answer_found=bool(res.sources),
                k=5,
            )
            save_eval_to_db(ev, conversation_id=cid, message_id=assistant_mid)
    except Exception:
        pass

    return {
        "answer": res.answer,
        "sources": res.sources,
        "conversation_id": cid,
        "mode": res.mode,
        "best_score": res.best_score,
        "confidence": getattr(res, "confidence", 0.0),
        "retrieval_mode": getattr(res, "retrieval_mode", "unknown"),
        "latency_ms": getattr(res, "latency_ms", 0),
        "intent": getattr(res, "intent", None),
        "category": getattr(res, "category", None),
        "message_id": assistant_mid,
        "user_message_id": user_mid,
    }
    
@router.post("/rag/fts/rebuild")
def rag_fts_rebuild(_user=Depends(_auth_admin)) -> Dict[str, Any]:
    n = rebuild_fts_from_rag_chunk()
    return {"ok": True, "fts_rows": n}


@router.post("/rag/qdrant/upsert")
def rag_qdrant_upsert(
    batch_size: int = 64,
    limit: Optional[int] = None,
    _user=Depends(_auth_admin),
) -> Dict[str, Any]:
    result = upsert_qdrant_from_db(model=os.getenv("EMBED_MODEL", "bge-m3"), batch_size=batch_size, limit=limit)
    _audit(int(_user["user_id"]), "qdrant_upsert",
           f"upserted={result.get('points_upserted')} errors={len(result.get('errors', []))}")
    return result
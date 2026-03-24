from __future__ import annotations
import time
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from datetime import datetime, timezone
from .db import connect, execute_returning
from .schemas import FeedbackIn

router = APIRouter(prefix="/feedback", tags=["feedback"])
_feedback_store: dict = defaultdict(list)
_FEEDBACK_CLEANUP_EVERY = 300  # كل 300 طلب نمسح الـ IPs الخاملة
_feedback_req_count = 0


def _check_rate(request: Request) -> None:
    global _feedback_req_count
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.time()
    _feedback_store[ip] = [t for t in _feedback_store[ip] if t > now - 60]
    if len(_feedback_store[ip]) >= 10:
        raise HTTPException(
            status_code=429,
            detail="تم تجاوز الحد المسموح (10 طلبات/دقيقة). يرجى الانتظار."
        )
    _feedback_store[ip].append(now)

    # ✅ #4: تنظيف دوري لمنع تسرب الذاكرة
    _feedback_req_count += 1
    if _feedback_req_count % _FEEDBACK_CLEANUP_EVERY == 0:
        cutoff = now - 60
        dead = [k for k, v in _feedback_store.items() if not v or v[-1] < cutoff]
        for k in dead:
            del _feedback_store[k]


@router.post("")
def create_feedback(payload: FeedbackIn, request: Request):
    _check_rate(request)
    con = connect()
    try:
        cur = con.cursor()
        cid = payload.conversation_id
        mid = payload.message_id

        if cid is None and mid is None:
            raise HTTPException(status_code=422, detail="Provide conversation_id or message_id")

        if mid is not None and cid is None:
            r = cur.execute(
                "SELECT conversation_id FROM message WHERE message_id=%s", (mid,)
            ).fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="message_id not found")
            cid = int(r["conversation_id"])

        if cid is not None and mid is None:
            if not cur.execute(
                "SELECT 1 FROM conversation WHERE conversation_id=%s", (cid,)
            ).fetchone():
                raise HTTPException(status_code=404, detail="conversation_id not found")

        if cid is not None and mid is not None:
            r = cur.execute(
                "SELECT conversation_id FROM message WHERE message_id=%s", (mid,)
            ).fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="message_id not found")
            if int(r["conversation_id"]) != int(cid):
                raise HTTPException(
                    status_code=409, detail="message does not belong to conversation"
                )

        cur.execute(
            """
            INSERT INTO feedback
                (message_id, conversation_id, user_id, rating, feedback_type, comments, submitted_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                mid, cid, None,
                1 if payload.is_positive else 0,
                "helpful" if payload.is_positive else "not_helpful",
                payload.comment,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        con.commit()
        fid = execute_returning(cur, "SELECT lastval()")
        return {"ok": True, "feedback_id": fid}
    finally:
        con.close()
# backend/app/routers/files_routes.py
"""
نظام رفع الملفات ومراجعتها وإضافتها لـ RAG
- POST   /files/upload          - موظف يرفع ملف
- GET    /files                  - موظف يشوف ملفاته / إدارة تشوف الكل
- GET    /files/{file_id}        - تفاصيل ملف
- POST   /files/{file_id}/approve - إدارة توافق
- POST   /files/{file_id}/reject  - إدارة ترفض
- DELETE /files/{file_id}        - موظف يحذف ملفاته المعلقة
"""
from __future__ import annotations

import logging
from datetime import timezone, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import connect
from ..auth import require_auth, now_utc_sqlite
from ..rbac import require_roles

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

# ── Schemas ─────────────────────────────────────────────────

class FileUploadIn(BaseModel):
    name:      str  = Field(..., max_length=255)
    content:   str  = Field(..., description="محتوى الملف كنص")
    file_type: str  = Field(default="text/plain", max_length=100)
    size_bytes: int = Field(default=0, ge=0)

class FileOut(BaseModel):
    file_id:          int
    name:             str
    file_type:        str
    size_bytes:       int
    uploaded_by:      Optional[int]
    uploaded_by_name: Optional[str]
    uploaded_at:      str
    status:           str
    rejection_reason: Optional[str] = None
    reviewed_by:      Optional[int] = None
    reviewed_at:      Optional[str] = None
    kb_id:            Optional[int] = None

class FileDetailOut(FileOut):
    content: str

class RejectIn(BaseModel):
    rejection_reason: str = Field(..., min_length=5, max_length=500)


# ── Helpers ─────────────────────────────────────────────────

def _row_to_out(row: dict, include_content: bool = False) -> dict:
    data = {
        "file_id":          row["file_id"],
        "name":             row["name"],
        "file_type":        row["file_type"] or "text/plain",
        "size_bytes":       row["size_bytes"] or 0,
        "uploaded_by":      row.get("uploaded_by"),
        "uploaded_by_name": row.get("uploaded_by_name"),
        "uploaded_at":      str(row["uploaded_at"]),
        "status":           row["status"],
        "rejection_reason": row.get("rejection_reason"),
        "reviewed_by":      row.get("reviewed_by"),
        "reviewed_at":      str(row["reviewed_at"]) if row.get("reviewed_at") else None,
        "kb_id":            row.get("kb_id"),
    }
    if include_content:
        data["content"] = row.get("content", "")
    return data


def _add_to_kb(file_id: int, name: str, content: str, user_id: int) -> int:
    """يضيف محتوى الملف لـ knowledge_base ويعيد kb_id."""
    from ..main import sync_kb_to_rag  # import هنا لتجنب circular
    con = connect()
    cur = con.cursor()
    title = f"[ملف] {name}"
    cur.execute(
        """INSERT INTO knowledge_base
             (intent_id, language, title_ar, content_ar, external_links,
              category, is_active, created_by_user_id, updated_at)
           VALUES (NULL, 'ar', %s, %s, NULL, 'ملفات_مرفوعة', 1, %s, NOW())
           RETURNING kb_id""",
        (title, content, user_id),
    )
    kb_id = cur.fetchone()["kb_id"]
    con.commit()
    con.close()

    # تزامن مع RAG بشكل async-safe
    try:
        sync_kb_to_rag(
            kb_id=kb_id,
            title=title,
            content=content,
            category="ملفات_مرفوعة",
            intent_code=None,
            is_active=True,
        )
    except Exception as e:
        logger.warning(f"[files] RAG sync failed for kb_{kb_id}: {e}")

    return kb_id


# ── Routes ──────────────────────────────────────────────────

@router.post("", response_model=FileDetailOut, status_code=201)
def upload_file(body: FileUploadIn, request: Request):
    """موظف يرفع ملف — يصير حالته pending"""
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])

    # حد أقصى 5 MB
    if body.size_bytes > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد الأقصى 5 ميجابايت")

    allowed_types = {
        "text/plain", "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if body.file_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"نوع الملف غير مدعوم: {body.file_type}")

    # Strip NUL bytes (0x00) — PostgreSQL text columns reject them.
    # Binary files sent as raw text may contain NUL characters.
    safe_content = body.content.replace("\x00", "")

    con = connect()
    cur = con.cursor()
    cur.execute(
        """INSERT INTO uploaded_file
             (name, content, file_type, size_bytes, uploaded_by, uploaded_at, status)
           VALUES (%s, %s, %s, %s, %s, NOW(), 'pending')
           RETURNING file_id, name, file_type, size_bytes, uploaded_by,
                     uploaded_at, status, rejection_reason, reviewed_by, reviewed_at, kb_id, content""",
        (body.name.strip(), safe_content, body.file_type, body.size_bytes, int(me["user_id"])),
    )
    row = dict(cur.fetchone())
    row["uploaded_by_name"] = me.get("full_name")
    con.commit()
    con.close()

    logger.info(f"[files] uploaded file_id={row['file_id']} by user_id={me['user_id']}")
    return FileDetailOut(**_row_to_out(row, include_content=True))


@router.get("", response_model=list[FileOut])
def list_files(request: Request, status: Optional[str] = None):
    """
    موظف يشوف ملفاته فقط.
    supervisor/admin يشوفون الكل، مع فلتر اختياري على status.
    """
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])

    con = connect()
    cur = con.cursor()

    where_clauses = []
    params: list = []

    # موظف عادي يشوف ملفاته بس
    if me["role"] == "employee":
        where_clauses.append("uf.uploaded_by = %s")
        params.append(int(me["user_id"]))

    if status and status in ("pending", "approved", "rejected"):
        where_clauses.append("uf.status = %s")
        params.append(status)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    cur.execute(
        f"""SELECT uf.file_id, uf.name, uf.file_type, uf.size_bytes,
                   uf.uploaded_by, u.full_name AS uploaded_by_name,
                   uf.uploaded_at, uf.status, uf.rejection_reason,
                   uf.reviewed_by, uf.reviewed_at, uf.kb_id
            FROM uploaded_file uf
            LEFT JOIN app_user u ON u.user_id = uf.uploaded_by
            {where_sql}
            ORDER BY uf.uploaded_at DESC""",
        tuple(params),
    )
    rows = cur.fetchall()
    con.close()
    return [FileOut(**_row_to_out(dict(r))) for r in rows]


@router.get("/{file_id}", response_model=FileDetailOut)
def get_file(file_id: int, request: Request):
    """موظف يشوف ملفه، إدارة تشوف أي ملف"""
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute(
        """SELECT uf.*, u.full_name AS uploaded_by_name
           FROM uploaded_file uf
           LEFT JOIN app_user u ON u.user_id = uf.uploaded_by
           WHERE uf.file_id = %s LIMIT 1""",
        (file_id,),
    )
    row = cur.fetchone()
    con.close()

    if not row:
        raise HTTPException(status_code=404, detail="الملف غير موجود")

    row = dict(row)
    # موظف عادي يشوف ملفاته فقط
    if me["role"] == "employee" and row.get("uploaded_by") != int(me["user_id"]):
        raise HTTPException(status_code=403, detail="غير مسموح")

    return FileDetailOut(**_row_to_out(row, include_content=True))


@router.post("/{file_id}/approve")
def approve_file(file_id: int, request: Request):
    """إدارة/supervisor توافق على ملف → يُضاف لـ RAG تلقائياً"""
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM uploaded_file WHERE file_id = %s LIMIT 1", (file_id,))
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="الملف غير موجود")

    row = dict(row)
    if row["status"] != "pending":
        con.close()
        raise HTTPException(status_code=400, detail=f"الملف حالته {row['status']} وليس pending")

    # إضافة لـ knowledge_base + RAG
    kb_id = _add_to_kb(
        file_id=file_id,
        name=row["name"],
        content=row["content"],
        user_id=int(me["user_id"]),
    )

    cur.execute(
        """UPDATE uploaded_file
           SET status='approved', reviewed_by=%s, reviewed_at=NOW(), kb_id=%s
           WHERE file_id=%s""",
        (int(me["user_id"]), kb_id, file_id),
    )
    con.commit()
    con.close()

    logger.info(f"[files] approved file_id={file_id} → kb_id={kb_id} by user_id={me['user_id']}")
    return {"ok": True, "kb_id": kb_id}


@router.post("/{file_id}/reject")
def reject_file(file_id: int, body: RejectIn, request: Request):
    """إدارة/supervisor ترفض ملف مع ذكر السبب"""
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute("SELECT status FROM uploaded_file WHERE file_id = %s LIMIT 1", (file_id,))
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    if dict(row)["status"] != "pending":
        con.close()
        raise HTTPException(status_code=400, detail="الملف ليس في حالة pending")

    cur.execute(
        """UPDATE uploaded_file
           SET status='rejected', rejection_reason=%s, reviewed_by=%s, reviewed_at=NOW()
           WHERE file_id=%s""",
        (body.rejection_reason, int(me["user_id"]), file_id),
    )
    con.commit()
    con.close()

    logger.info(f"[files] rejected file_id={file_id} by user_id={me['user_id']}")
    return {"ok": True}


@router.delete("/{file_id}")
def delete_file(file_id: int, request: Request):
    """موظف يحذف ملفه المعلق فقط — إدارة تحذف أي ملف"""
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM uploaded_file WHERE file_id = %s LIMIT 1", (file_id,))
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="الملف غير موجود")

    row = dict(row)

    # موظف عادي يحذف ملفاته المعلقة فقط
    if me["role"] == "employee":
        if row.get("uploaded_by") != int(me["user_id"]):
            con.close()
            raise HTTPException(status_code=403, detail="غير مسموح")
        if row["status"] != "pending":
            con.close()
            raise HTTPException(status_code=400, detail="لا يمكن حذف ملف تمت مراجعته")

    cur.execute("DELETE FROM uploaded_file WHERE file_id = %s", (file_id,))
    con.commit()
    con.close()

    logger.info(f"[files] deleted file_id={file_id} by user_id={me['user_id']}")
    return {"ok": True}


# ── Stats endpoint (للإدارة) ─────────────────────────────────

@router.get("/stats/summary")
def files_stats(request: Request):
    """إحصائيات الملفات للإدارة"""
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])

    con = connect()
    cur = con.cursor()
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status='pending')  AS pending_count,
            COUNT(*) FILTER (WHERE status='approved') AS approved_count,
            COUNT(*) FILTER (WHERE status='rejected') AS rejected_count,
            COUNT(*)                                   AS total_count
        FROM uploaded_file
    """)
    row = dict(cur.fetchone())
    con.close()
    return row
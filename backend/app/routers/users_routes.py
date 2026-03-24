# routers/users_routes.py
# ─────────────────────────────────────────────────────────────
# هذا الـ router غير مُدرج في app — الـ frontend يستخدم /admin/users
# ─────────────────────────────────────────────────────────────
# User management endpoints الفعلية في app/main.py:
#   GET    /admin/users
#   POST   /admin/users
#   PUT    /admin/users/{id}
#   DELETE /admin/users/{id}
#   POST   /admin/users/{id}/reset-password
#
# لا تعمل include_router لهذا الملف — يسبب تعارض مع /admin/users
# ─────────────────────────────────────────────────────────────

from fastapi import APIRouter, Request
from typing import List

from ..auth import require_auth
from ..rbac import require_roles
from ..db import connect
from ..schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(request: Request):
    me = require_auth(request)
    require_roles(me, ["admin", "supervisor"])

    con = connect()
    cur = con.cursor()
    cur.execute("""
        SELECT user_id, username, role, full_name, email, phone, status
        FROM app_user
        WHERE role IN ('employee', 'supervisor', 'admin')
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    con.close()

    return [UserOut(**dict(r)) for r in rows]
# backend/app/main.py
from __future__ import annotations

from datetime import datetime
from typing import Any
from collections import defaultdict
import logging
import secrets
import string
import threading
import time
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

# ✅ تفعيل نظام Logging الاحترافي (4 ملفات منفصلة)
from .logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# ── Login Brute-Force Protection ─────────────────────────────
_login_attempts: dict[str, list[float]] = defaultdict(list)
LOGIN_RATE_LIMIT   = int(os.getenv("LOGIN_RATE_LIMIT", "5"))    # محاولات مسموح بها
LOGIN_RATE_WINDOW  = int(os.getenv("LOGIN_RATE_WINDOW", "300")) # خلال 5 دقائق
LOGIN_LOCKOUT_SEC  = int(os.getenv("LOGIN_LOCKOUT_SEC", "600")) # حظر 10 دقائق بعد التجاوز
_LOGIN_CLEANUP_EVERY = 200  # كل 200 محاولة نمسح المفاتيح المنتهية
_login_attempt_count = 0

def _check_login_rate(ip: str, username: str) -> None:
    """يحظر IP+username لو تجاوز المحاولات المسموح بها."""
    global _login_attempt_count
    key = f"{ip}:{username}"
    now = time.time()
    _login_attempts[key] = [t for t in _login_attempts[key] if t > now - LOGIN_RATE_WINDOW]
    if len(_login_attempts[key]) >= LOGIN_RATE_LIMIT:
        remaining = int(_login_attempts[key][0] + LOGIN_LOCKOUT_SEC - now)
        raise HTTPException(
            status_code=429,
            detail=f"تم تجاوز الحد المسموح لمحاولات تسجيل الدخول. حاول مرة أخرى بعد {max(remaining, 60)} ثانية."
        )
    _login_attempts[key].append(now)

    # ✅ #4: تنظيف دوري لمنع تسرب الذاكرة
    _login_attempt_count += 1
    if _login_attempt_count % _LOGIN_CLEANUP_EVERY == 0:
        cutoff = now - LOGIN_RATE_WINDOW
        dead = [k for k, v in _login_attempts.items() if not v or v[-1] < cutoff]
        for k in dead:
            del _login_attempts[k]

def _reset_login_rate(ip: str, username: str) -> None:
    """يمسح محاولات الـ IP بعد تسجيل دخول ناجح."""
    _login_attempts.pop(f"{ip}:{username}", None)

from .db import init_db, connect
from .auth import (
    verify_password, create_session, require_auth,
    logout_token, now_utc_sqlite, hash_password,
    refresh_session,
)
from .rbac import require_roles
from .schemas import (
    LoginRequest, LoginResponse, CreateUserRequest, UserOut,
    KBCreate, KBItemOut, UpdateUserRequest, ConversationRatingIn, ChangePasswordRequest,
    RefreshRequest,
)
from .rag_api import router as rag_router
from .rag_engine import embed_text, upsert_embedding, EMBED_MODEL
from .stats_api import router as stats_router
from .feedback_api import router as feedback_router
from .security import setup_security
from .chat_analysis_api import router as chat_analysis_router
from .admin_controls_api import router as admin_controls_router
from .access_log_middleware import AccessLogMiddleware
from .rag_metrics import ensure_eval_table
from .routers.knowledge_routes import router as knowledge_router

# =============================
# App bootstrap
# =============================

init_db()
ensure_eval_table()  # ✅ ينشئ جدول rag_eval_log إذا لم يكن موجوداً

app = FastAPI(title="Hebron Electricity Support API (RBAC + KB + RAG)")

_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_router)
app.include_router(stats_router)
app.include_router(feedback_router)
app.include_router(chat_analysis_router)   # ✅ تحليل المحادثات (أكثر المشاكل، الأحياء)
app.include_router(admin_controls_router)  # ✅ Admin Controls (rebuild embeddings, LLM usage)
app.include_router(knowledge_router)       # ✅ Knowledge Base مع pagination وchangelog

# ✅ Access Log Middleware — يسجّل كل طلب في access.log
app.add_middleware(AccessLogMiddleware)

# ✅ #2: تفعيل Security Middleware (rate limiting + security headers + token redaction)
setup_security(app)

# =============================
# Helpers
# =============================

def audit(user_id, table, record_id, action, old_values=None, new_values=None):
    con = connect()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO audit_trail (table_name, record_id, action, user_id, old_values, new_values, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (table, record_id, action, user_id, old_values, new_values, now_utc_sqlite()),
    )
    con.commit()
    con.close()


def sync_kb_to_rag(kb_id, title, content, category, intent_code, is_active):
    import json
    chunk_id = f"kb_{kb_id}"
    con = connect()
    cur = con.cursor()
    if not is_active:
        cur.execute("DELETE FROM rag_embedding WHERE chunk_id=%s", (chunk_id,))
        cur.execute("DELETE FROM rag_chunk WHERE chunk_id=%s", (chunk_id,))
        con.commit()
        con.close()
        return
    text = f"{title.strip()}\n{content.strip()}"
    metadata = json.dumps({"intent": intent_code or "", "category": category or "",
                           "source": "knowledge_base", "kb_id": kb_id}, ensure_ascii=False)
    cur.execute(
        "INSERT INTO rag_chunk (chunk_id, source_file, text, metadata_json) VALUES (%s, 'knowledge_base', %s, %s) "
        "ON CONFLICT (chunk_id) DO UPDATE SET source_file='knowledge_base', text=EXCLUDED.text, metadata_json=EXCLUDED.metadata_json",
        (chunk_id, text, metadata),
    )
    con.commit()
    con.close()
    try:
        vec = embed_text(text)
        upsert_embedding(chunk_id, vec, EMBED_MODEL)
    except Exception as e:
        # ✅ #6: لا نخفي أخطاء الـ embeddings — نسجلها حتى يعرف المسؤول
        logger.warning(f"[kb] فشل إنشاء embeddings لـ kb_{kb_id}: {e}")


def delete_kb_from_rag(kb_id):
    chunk_id = f"kb_{kb_id}"
    con = connect()
    cur = con.cursor()
    cur.execute("DELETE FROM rag_embedding WHERE chunk_id=%s", (chunk_id,))
    cur.execute("DELETE FROM rag_chunk WHERE chunk_id=%s", (chunk_id,))
    con.commit()
    con.close()


def get_department_id_by_code(code):
    if not code:
        return None
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT department_id FROM department WHERE department_code=%s LIMIT 1", (code,))
    r = cur.fetchone()
    con.close()
    return int(r["department_id"]) if r else None


def get_intent_id_by_code(intent_code):
    if not intent_code:
        return None
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT intent_id FROM intent WHERE intent_code=%s LIMIT 1", (intent_code,))
    r = cur.fetchone()
    con.close()
    return int(r["intent_id"]) if r else None


def get_intent_code_by_id(intent_id):
    if not intent_id:
        return None
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT intent_code FROM intent WHERE intent_id=%s LIMIT 1", (intent_id,))
    r = cur.fetchone()
    con.close()
    return str(r["intent_code"]) if r else None


# ✅ كلمة مرور مؤقتة عشوائية قوية
def _gen_temp_password(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$"
    while True:
        pwd = "".join(secrets.choice(chars) for _ in range(length))
        if (any(c.isupper() for c in pwd) and
                any(c.isdigit() for c in pwd) and
                any(c in "!@#$" for c in pwd)):
            return pwd


# =============================
# Health
# =============================

@app.get("/health")
def health():
    try:
        con = connect()
        con.execute("SELECT 1")
        con.close()
        db_ok = True
    except Exception as e:
        logger.error(f"[health] DB check failed: {e}")
        db_ok = False
    return {"ok": db_ok, "db": db_ok}


def _cleanup_expired_sessions():
    while True:
        try:
            time.sleep(6 * 3600)
            con = connect()
            cur = con.cursor()
            cur.execute("""
                DELETE FROM user_session
                WHERE is_active = 0
                   OR expires_at < NOW() - INTERVAL '7 days'
            """)
            deleted = cur.rowcount
            con.commit()
            con.close()
            if deleted:
                logger.info(f"[cleanup] removed {deleted} expired sessions")
        except Exception as e:
            logger.error(f"[cleanup] session cleanup failed: {e}")


threading.Thread(target=_cleanup_expired_sessions, daemon=True).start()
logger.info("✅ Hebron Electricity API started")

# =============================
# Auth
# =============================

@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request):
    username = req.username.strip()
    ip = (request.client.host if request.client else "unknown") or "unknown"

    # ── Brute-force protection ──
    _check_login_rate(ip, username)

    con = connect()
    cur = con.cursor()
    cur.execute(
        "SELECT user_id, username, password_hash, role, full_name, status, must_change_password FROM app_user WHERE username=%s LIMIT 1",
        (username,),
    )
    user = cur.fetchone()
    con.close()
    if (not user) or (user["status"] != "active"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # ── تسجيل دخول ناجح → امسح المحاولات ──
    _reset_login_rate(ip, username)

    access_token, ref_token = create_session(int(user["user_id"]), request)
    con = connect()
    cur = con.cursor()
    cur.execute("UPDATE app_user SET last_login=%s, updated_at=%s WHERE user_id=%s",
                (now_utc_sqlite(), now_utc_sqlite(), int(user["user_id"])))
    con.commit()
    con.close()
    audit(int(user["user_id"]), "app_user", int(user["user_id"]), "login")
    return LoginResponse(token=access_token, refresh_token=ref_token,
                         role=str(user["role"]),
                         full_name=str(user["full_name"]),
                         must_change_password=bool(user["must_change_password"]))


@app.post("/auth/logout")
def logout(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth.split(" ", 1)[1].strip()
    user = None
    try:
        user = require_auth(request)
    except Exception:
        pass
    logout_token(token)
    if user:
        audit(int(user["user_id"]), "user_session", int(user["session_id"]), "logout")
    return {"ok": True}


@app.post("/auth/refresh")
def refresh_token(body: RefreshRequest):
    """يجدد الـ access token باستخدام الـ refresh token."""
    new_token = refresh_session(body.refresh_token)
    if not new_token:
        raise HTTPException(status_code=401, detail="Refresh token منتهي أو غير صالح")
    return {"token": new_token}


@app.post("/auth/change-password")
def change_password(body: ChangePasswordRequest, request: Request):
    me = require_auth(request)
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT password_hash FROM app_user WHERE user_id=%s LIMIT 1", (int(me["user_id"]),))
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(body.old_password, row["password_hash"]):
        con.close()
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    cur.execute(
        "UPDATE app_user SET password_hash=%s, must_change_password=0, password_changed_at=%s, updated_at=%s WHERE user_id=%s",
        (hash_password(body.new_password), now_utc_sqlite(), now_utc_sqlite(), int(me["user_id"])),
    )
    con.commit()
    con.close()
    audit(int(me["user_id"]), "app_user", int(me["user_id"]), "change_password")
    return {"ok": True}

# =============================
# Admin: Users
# =============================

@app.get("/admin/users", response_model=list[UserOut])
def list_users(request: Request):
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])  # FIX: employee لا يرى المستخدمين
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT user_id, username, role, full_name, email, phone, status, last_login FROM app_user WHERE role IN ('employee','supervisor','admin') ORDER BY created_at DESC")
    rows = cur.fetchall()
    con.close()
    return [UserOut(**dict(r)) for r in rows]


@app.post("/admin/users", response_model=UserOut)
def create_user(req: CreateUserRequest, request: Request):
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])  # FIX: employee لا يضيف مستخدمين
    if req.role not in ("employee", "supervisor", "admin"):
        raise HTTPException(status_code=400, detail="role must be employee, supervisor or admin")
    dept_id = get_department_id_by_code(req.department_code)
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT 1 FROM app_user WHERE username=%s LIMIT 1", (req.username.strip(),))
    if cur.fetchone():
        con.close()
        raise HTTPException(status_code=409, detail="username already exists")
    cur.execute(
        "INSERT INTO app_user (username, password_hash, role, full_name, email, phone, department_id, status, must_change_password) VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s) RETURNING user_id",
        (req.username.strip(), hash_password(req.password), req.role, req.full_name.strip(),
         req.email.strip() if req.email else None, req.phone.strip() if req.phone else None,
         dept_id, 1 if req.role in ("employee", "supervisor") else 0),
    )
    user_id = cur.fetchone()["user_id"]
    con.commit()
    cur.execute("SELECT user_id, username, role, full_name, email, phone, status FROM app_user WHERE user_id=%s", (user_id,))
    created = cur.fetchone()
    con.close()
    audit(int(me["user_id"]), "app_user", user_id, "insert", new_values=str(dict(created)))
    return UserOut(**dict(created))


@app.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(request: Request, user_id: int = Path(..., ge=1), req: UpdateUserRequest = None):
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])  # FIX: employee لا يعدل المستخدمين
    if req is None:
        raise HTTPException(status_code=400, detail="Missing body")
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM app_user WHERE user_id=%s LIMIT 1", (user_id,))
    old = cur.fetchone()
    if not old:
        con.close()
        raise HTTPException(status_code=404, detail="User not found")
    updates: list[str] = []
    params: list[Any] = []
    if req.role is not None:
        if req.role not in ("employee", "supervisor", "admin"):
            con.close()
            raise HTTPException(status_code=400, detail="role must be employee, supervisor or admin")
        updates.append("role=%s"); params.append(req.role)
    if req.status is not None:
        if req.status not in ("active", "inactive"):
            con.close()
            raise HTTPException(status_code=400, detail="status must be active or inactive")
        updates.append("status=%s"); params.append(req.status)
    if req.full_name is not None:
        updates.append("full_name=%s"); params.append(req.full_name.strip())
    if req.email is not None:
        updates.append("email=%s"); params.append(req.email.strip() if req.email else None)
    if req.phone is not None:
        updates.append("phone=%s"); params.append(req.phone.strip() if req.phone else None)
    if req.department_code is not None:
        updates.append("department_id=%s"); params.append(get_department_id_by_code(req.department_code))
    if req.password:
        updates.append("password_hash=%s"); params.append(hash_password(req.password))
    if not updates:
        con.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at=%s"); params.append(now_utc_sqlite()); params.append(user_id)
    cur.execute(f"UPDATE app_user SET {', '.join(updates)} WHERE user_id=%s", tuple(params))
    con.commit()
    cur.execute("SELECT user_id, username, role, full_name, email, phone, status FROM app_user WHERE user_id=%s", (user_id,))
    updated = cur.fetchone()
    con.close()
    audit(int(me["user_id"]), "app_user", user_id, "update", old_values=str(dict(old)), new_values=str(dict(updated)))
    return UserOut(**dict(updated))


@app.delete("/admin/users/{user_id}")
def delete_user(request: Request, user_id: int = Path(..., ge=1)):
    me = require_auth(request)
    require_roles(me, ["supervisor", "admin"])  # FIX: employee لا يحذف مستخدمين
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM app_user WHERE user_id=%s LIMIT 1", (user_id,))
    old = cur.fetchone()
    if not old:
        con.close()
        raise HTTPException(status_code=404, detail="User not found")
    cur.execute("UPDATE app_user SET status='inactive', updated_at=%s WHERE user_id=%s", (now_utc_sqlite(), user_id))
    con.commit()
    con.close()
    audit(int(me["user_id"]), "app_user", user_id, "deactivate", old_values=str(dict(old)))
    return {"ok": True}

# =============================
# Admin: Reset Password  ✅ FIXED
# =============================

@app.post("/admin/users/{user_id}/reset-password")
def reset_user_password(request: Request, user_id: int = Path(..., ge=1)):
    me = require_auth(request)
    require_roles(me, ["admin"])  # ✅ admin فقط
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM app_user WHERE user_id=%s AND status='active' LIMIT 1", (user_id,))
    if not cur.fetchone():
        con.close()
        raise HTTPException(status_code=404, detail="User not found")
    temp_password = _gen_temp_password()  # ✅ عشوائية كل مرة
    cur.execute(
        "UPDATE app_user SET password_hash=%s, must_change_password=1, updated_at=%s WHERE user_id=%s",
        (hash_password(temp_password), now_utc_sqlite(), user_id),
    )
    con.commit()
    con.close()
    audit(int(me["user_id"]), "app_user", user_id, "reset_password")
    logger.info(f"[admin] reset_password for user_id={user_id} by admin={me['user_id']}")
    return {"ok": True, "temp_password": temp_password}  # ✅ الأدمن يشوفها ويبلّغها

# =============================
# KB
# =============================

@app.get("/kb", response_model=list[KBItemOut])
def list_kb(request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT kb_id, intent_id, title_ar, content_ar, category, is_active FROM knowledge_base ORDER BY updated_at DESC")
    rows = cur.fetchall()
    con.close()
    return [KBItemOut(kb_id=d["kb_id"], title_ar=d["title_ar"], content_ar=d["content_ar"],
                      category=d.get("category"), intent_code=get_intent_code_by_id(d.get("intent_id")),
                      is_active=bool(d["is_active"])) for d in [dict(r) for r in rows]]


@app.post("/kb", response_model=KBItemOut)
def create_kb(req: KBCreate, request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    intent_id = get_intent_id_by_code(req.intent_code)
    con = connect()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO knowledge_base (intent_id, language, title_ar, content_ar, external_links, category, is_active, created_by_user_id, updated_at) VALUES (%s, 'ar', %s, %s, %s, %s, %s, %s, NOW()) RETURNING kb_id",
        (intent_id, req.title_ar.strip(), req.content_ar.strip(), req.external_links,
         req.category, 1 if req.is_active else 0, int(me["user_id"])),
    )
    kb_id = cur.fetchone()["kb_id"]
    con.commit()
    cur.execute("SELECT kb_id, intent_id, title_ar, content_ar, category, is_active FROM knowledge_base WHERE kb_id=%s", (kb_id,))
    row = cur.fetchone()
    con.close()
    audit(int(me["user_id"]), "knowledge_base", kb_id, "insert", new_values=str(dict(row)))
    sync_kb_to_rag(kb_id=kb_id, title=req.title_ar.strip(), content=req.content_ar.strip(),
                   category=req.category, intent_code=req.intent_code, is_active=req.is_active)
    return KBItemOut(kb_id=kb_id, title_ar=row["title_ar"], content_ar=row["content_ar"],
                     category=row["category"], intent_code=get_intent_code_by_id(row["intent_id"]),
                     is_active=bool(row["is_active"]))


@app.put("/kb/{kb_id}", response_model=KBItemOut)
def update_kb(kb_id: int, req: KBCreate, request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    intent_id = get_intent_id_by_code(req.intent_code)
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM knowledge_base WHERE kb_id=%s LIMIT 1", (kb_id,))
    old = cur.fetchone()
    if not old:
        con.close()
        raise HTTPException(status_code=404, detail="Not found")
    cur.execute(
        "UPDATE knowledge_base SET intent_id=%s, title_ar=%s, content_ar=%s, external_links=%s, category=%s, is_active=%s, updated_at=NOW() WHERE kb_id=%s",
        (intent_id, req.title_ar.strip(), req.content_ar.strip(), req.external_links,
         req.category, 1 if req.is_active else 0, kb_id),
    )
    con.commit()
    cur.execute("SELECT kb_id, intent_id, title_ar, content_ar, category, is_active FROM knowledge_base WHERE kb_id=%s", (kb_id,))
    row = cur.fetchone()
    con.close()
    audit(int(me["user_id"]), "knowledge_base", kb_id, "update", old_values=str(dict(old)), new_values=str(dict(row)))
    sync_kb_to_rag(kb_id=kb_id, title=req.title_ar.strip(), content=req.content_ar.strip(),
                   category=req.category, intent_code=req.intent_code, is_active=req.is_active)
    return KBItemOut(kb_id=kb_id, title_ar=row["title_ar"], content_ar=row["content_ar"],
                     category=row["category"], intent_code=get_intent_code_by_id(row["intent_id"]),
                     is_active=bool(row["is_active"]))


@app.delete("/kb/{kb_id}")
def delete_kb(kb_id: int, request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM knowledge_base WHERE kb_id=%s LIMIT 1", (kb_id,))
    old = cur.fetchone()
    if not old:
        con.close()
        raise HTTPException(status_code=404, detail="Not found")
    cur.execute("DELETE FROM knowledge_base WHERE kb_id=%s", (kb_id,))
    con.commit()
    con.close()
    audit(int(me["user_id"]), "knowledge_base", kb_id, "delete", old_values=str(dict(old)))
    delete_kb_from_rag(kb_id)
    return {"ok": True}

# =============================
# Conversation Rating
# =============================

@app.post("/conversation-rating")
def create_conversation_rating(body: ConversationRatingIn):
    con = connect()
    cur = con.cursor()
    conv_id = int(body.conversation_id)
    cur.execute("SELECT 1 FROM conversation WHERE conversation_id=%s LIMIT 1", (conv_id,))
    if cur.fetchone() is None:
        con.close()
        raise HTTPException(status_code=404, detail="conversation_id not found")
    cur.execute(
        "INSERT INTO feedback (message_id, conversation_id, user_id, rating, feedback_type, comments, submitted_at) VALUES (NULL, %s, NULL, %s, 'stars', %s, %s)",
        (conv_id, int(body.stars), body.comment, datetime.utcnow().isoformat()),
    )
    con.commit()
    con.close()
    return {"ok": True}

# =============================
# KB Sync to RAG
# =============================

@app.post("/kb/sync-to-rag")
def sync_all_kb_to_rag(request: Request):
    me = require_auth(request)
    require_roles(me, ["employee", "supervisor", "admin"])
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT kb_id, title_ar, content_ar, category, intent_id, is_active FROM knowledge_base")
    rows = cur.fetchall()
    con.close()
    synced = removed = 0
    errors = []
    for row in rows:
        kb_id = int(row["kb_id"])
        is_active = bool(row["is_active"])
        try:
            sync_kb_to_rag(kb_id=kb_id, title=row["title_ar"] or "",
                           content=row["content_ar"] or "", category=row["category"],
                           intent_code=get_intent_code_by_id(row["intent_id"]), is_active=is_active)
            if is_active: synced += 1
            else: removed += 1
        except Exception as e:
            errors.append(f"kb_{kb_id}: {e}")
    audit(int(me["user_id"]), "knowledge_base", 0, "sync_to_rag",
          new_values=f"synced={synced} removed={removed} errors={len(errors)}")
    return {"ok": True, "synced": synced, "removed": removed, "errors": errors[:10]}
# backend/app/admin_controls_api.py
"""
Admin Controls أقوى:
  1. إعادة بناء الـ Embeddings من الـ Dashboard (مع تتبع التقدم)
  2. مراقبة LLM Usage — عدد الطلبات، زمن الاستجابة، الأخطاء
  3. تقرير صحة النظام الشامل
  4. إدارة سجل الـ Audit Trail
"""
from __future__ import annotations

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, BackgroundTasks
from fastapi import HTTPException

from .db import connect
from .auth import require_auth, now_utc_sqlite
from .rbac import require_roles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-controls"])


def _auth_admin(request: Request):
    user = require_auth(request)
    require_roles(user, ["admin"])
    return user


def _q_rows(sql: str, params: tuple = ()) -> list[dict]:
    con = connect()
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def _q_scalar(sql: str, params: tuple = ()):
    con = connect()
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return next(iter(row.values())) if row else None
    finally:
        con.close()


# ── LLM Usage Tracker (in-memory, resets on restart) ─────────
class _LLMUsageTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._calls: list[dict] = []

    def record(self, model: str, latency_ms: float, tokens_in: int, tokens_out: int,
               success: bool, error: str = "") -> None:
        with self._lock:
            self._calls.append({
                "ts": datetime.utcnow().isoformat(),
                "model": model,
                "latency_ms": round(latency_ms, 1),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "success": success,
                "error": error[:200] if error else "",
            })
            # احتفظ بآخر 5000 طلب فقط
            if len(self._calls) > 5000:
                self._calls = self._calls[-5000:]

    def stats(self, hours: int = 24) -> dict:
        with self._lock:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            recent = [c for c in self._calls if c["ts"] >= cutoff]

            if not recent:
                return {
                    "hours": hours, "total_calls": 0, "success_rate": 0,
                    "avg_latency_ms": 0, "total_tokens_in": 0, "total_tokens_out": 0,
                    "errors": [], "calls_per_model": {},
                }

            total = len(recent)
            success = sum(1 for c in recent if c["success"])
            errors = [c for c in recent if not c["success"]][-10:]
            avg_lat = sum(c["latency_ms"] for c in recent) / total
            tokens_in = sum(c["tokens_in"] for c in recent)
            tokens_out = sum(c["tokens_out"] for c in recent)

            by_model: dict = {}
            for c in recent:
                m = c["model"]
                if m not in by_model:
                    by_model[m] = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
                by_model[m]["calls"] += 1
                by_model[m]["tokens_in"] += c["tokens_in"]
                by_model[m]["tokens_out"] += c["tokens_out"]

            return {
                "hours": hours,
                "total_calls": total,
                "success_rate": round(success / total * 100, 1),
                "avg_latency_ms": round(avg_lat, 1),
                "total_tokens_in": tokens_in,
                "total_tokens_out": tokens_out,
                "recent_errors": errors,
                "calls_per_model": by_model,
            }

    def hourly_breakdown(self, hours: int = 24) -> list[dict]:
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            by_hour: dict = {}
            for c in self._calls:
                try:
                    ts = datetime.fromisoformat(c["ts"])
                    if ts < cutoff:
                        continue
                    h = ts.strftime("%Y-%m-%d %H:00")
                    if h not in by_hour:
                        by_hour[h] = {"hour": h, "calls": 0, "errors": 0, "avg_latency_ms": 0, "_lats": []}
                    by_hour[h]["calls"] += 1
                    if not c["success"]:
                        by_hour[h]["errors"] += 1
                    by_hour[h]["_lats"].append(c["latency_ms"])
                except Exception:
                    pass
            result = []
            for h in sorted(by_hour.keys()):
                entry = by_hour[h]
                lats = entry.pop("_lats", [])
                entry["avg_latency_ms"] = round(sum(lats)/len(lats), 1) if lats else 0
                result.append(entry)
            return result


llm_tracker = _LLMUsageTracker()


# ── Embeddings Rebuild Progress ───────────────────────────────
_rebuild_status: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "total": 0,
    "done": 0,
    "errors": 0,
    "last_error": "",
    "progress_pct": 0,
}
_rebuild_lock = threading.Lock()


def _do_rebuild(overwrite: bool, limit: Optional[int], user_id: int) -> None:
    global _rebuild_status
    with _rebuild_lock:
        _rebuild_status.update({
            "running": True, "started_at": datetime.utcnow().isoformat(),
            "finished_at": None, "done": 0, "errors": 0,
            "last_error": "", "progress_pct": 0,
        })

    try:
        from .rag_engine import build_embeddings
        t0 = time.time()

        # حساب العدد الكلي
        con = connect()
        cur = con.cursor()
        if overwrite:
            cur.execute("SELECT COUNT(*) AS cnt FROM rag_chunk")
        else:
            cur.execute(
                """SELECT COUNT(*) AS cnt FROM rag_chunk rc
                   WHERE NOT EXISTS (SELECT 1 FROM rag_embedding re WHERE re.chunk_id=rc.chunk_id)"""
            )
        row = cur.fetchone()
        total = int(row["cnt"]) if row else 0
        con.close()

        with _rebuild_lock:
            _rebuild_status["total"] = total

        # تشغيل البناء
        result = build_embeddings(limit=limit, overwrite=overwrite)
        built = result.get("embeddings_built", 0)
        errors = len(result.get("errors", []))

        with _rebuild_lock:
            _rebuild_status.update({
                "running": False,
                "finished_at": datetime.utcnow().isoformat(),
                "done": built,
                "errors": errors,
                "last_error": (result.get("errors") or [""])[0] if errors else "",
                "progress_pct": 100,
            })

        # audit
        _audit(user_id, "rebuild_embeddings",
               f"built={built} errors={errors} elapsed={round(time.time()-t0)}s")
        logger.info(f"[admin] rebuild_embeddings done: built={built} errors={errors}")

    except Exception as e:
        with _rebuild_lock:
            _rebuild_status.update({
                "running": False,
                "finished_at": datetime.utcnow().isoformat(),
                "last_error": str(e)[:300],
            })
        logger.error(f"[admin] rebuild_embeddings failed: {e}")


def _audit(user_id: int, action: str, details: str = "") -> None:
    try:
        con = connect()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO audit_trail (table_name, record_id, action, user_id, new_values, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            ("admin_control", 0, action, user_id, details, now_utc_sqlite()),
        )
        con.commit()
        con.close()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════

# ── 1. إعادة بناء Embeddings ─────────────────────────────────
@router.post("/rebuild-embeddings")
def rebuild_embeddings(
    background_tasks: BackgroundTasks,
    overwrite: bool = False,
    limit: Optional[int] = None,
    _user=Depends(_auth_admin),
):
    """
    يُعيد بناء الـ Embeddings لكل الـ chunks في الـ DB.
    overwrite=True → يُعيد حتى المبنية
    يعمل في الخلفية — استخدم /admin/rebuild-embeddings/status لمتابعة التقدم.
    """
    with _rebuild_lock:
        if _rebuild_status["running"]:
            raise HTTPException(status_code=409, detail="إعادة البناء جارية بالفعل. انتظر حتى تنتهي.")

    background_tasks.add_task(_do_rebuild, overwrite, limit, int(_user["user_id"]))
    return {"ok": True, "message": "بدأت عملية إعادة البناء في الخلفية.", "check_status": "/admin/rebuild-embeddings/status"}


@router.get("/rebuild-embeddings/status")
def rebuild_embeddings_status(_user=Depends(_auth_admin)):
    """حالة عملية إعادة البناء الجارية أو الأخيرة"""
    with _rebuild_lock:
        status = dict(_rebuild_status)
    if status["total"] and not status["running"]:
        status["progress_pct"] = 100
    elif status["total"] and status["running"]:
        status["progress_pct"] = round(status["done"] / status["total"] * 100, 1)
    return status


# ── 2. مراقبة LLM Usage ──────────────────────────────────────
@router.get("/llm-usage")
def llm_usage(
    hours: int = Query(24, ge=1, le=168),
    _user=Depends(_auth_admin),
):
    """
    إحصائيات استهلاك الـ LLM:
    - عدد الطلبات، معدل النجاح، متوسط الزمن
    - عدد الـ tokens المستهلكة
    - توزيع حسب الساعة
    """
    stats = llm_tracker.stats(hours=hours)
    hourly = llm_tracker.hourly_breakdown(hours=hours)
    return {**stats, "hourly": hourly}


# ── 3. تقرير صحة النظام الشامل ───────────────────────────────
@router.get("/system-health")
def system_health(_user=Depends(_auth_admin)):
    """تقرير صحة شامل: DB, Qdrant, Ollama, Embeddings, Logs"""
    health: dict = {"checked_at": datetime.utcnow().isoformat(), "services": {}}

    # DB
    try:
        t0 = time.perf_counter()
        _q_scalar("SELECT 1")
        db_ms = round((time.perf_counter() - t0) * 1000, 1)
        chunks = _q_scalar("SELECT COUNT(*) FROM rag_chunk") or 0
        embeds = _q_scalar("SELECT COUNT(*) FROM rag_embedding") or 0
        health["services"]["database"] = {"ok": True, "latency_ms": db_ms, "chunks": chunks, "embeddings": embeds}
    except Exception as e:
        health["services"]["database"] = {"ok": False, "error": str(e)[:100]}

    # Ollama LLM
    try:
        from .rag_engine import ping_ollama
        t0 = time.perf_counter()
        ok = ping_ollama()
        ms = round((time.perf_counter() - t0) * 1000, 1)
        health["services"]["ollama_llm"] = {"ok": ok, "latency_ms": ms}
    except Exception as e:
        health["services"]["ollama_llm"] = {"ok": False, "error": str(e)[:100]}

    # Embeddings
    try:
        from .rag_engine import ping_embeddings
        t0 = time.perf_counter()
        ok = ping_embeddings()
        ms = round((time.perf_counter() - t0) * 1000, 1)
        health["services"]["embeddings"] = {"ok": ok, "latency_ms": ms}
    except Exception as e:
        health["services"]["embeddings"] = {"ok": False, "error": str(e)[:100]}

    # Qdrant
    try:
        from .qdrant_client import qdrant_enabled, get_collection_info, QDRANT_COLLECTION
        if qdrant_enabled():
            t0 = time.perf_counter()
            info = get_collection_info(QDRANT_COLLECTION)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            result = (info or {}).get("result") or {}
            health["services"]["qdrant"] = {
                "ok": result.get("status") == "green",
                "latency_ms": ms,
                "status": result.get("status", "unknown"),
                "points": result.get("points_count", 0),
            }
        else:
            health["services"]["qdrant"] = {"ok": True, "status": "disabled"}
    except Exception as e:
        health["services"]["qdrant"] = {"ok": False, "error": str(e)[:100]}

    # Embed Cache
    try:
        from .rag_engine import get_embed_cache_stats
        health["embed_cache"] = get_embed_cache_stats()
    except Exception:
        pass

    # Dialect Normalizer Cache
    try:
        from .dialect_normalizer import get_cache_stats as _dialect_stats
        health["dialect_normalizer"] = _dialect_stats()
    except Exception:
        pass

    # LLM usage summary
    health["llm_usage_24h"] = llm_tracker.stats(hours=24)

    # overall
    health["ok"] = all(
        s.get("ok", False)
        for s in health["services"].values()
        if s.get("status") != "disabled"
    )
    return health


# ── 4. Audit Trail ───────────────────────────────────────────
@router.get("/audit-trail")
def audit_trail(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
    action_filter: Optional[str] = Query(None),
    _user=Depends(_auth_admin),
):
    """سجل التغييرات — من فعل ماذا ومتى"""
    params: list = [days, limit]
    action_clause = ""
    if action_filter:
        action_clause = "AND action LIKE %s"
        params.insert(1, f"%{action_filter}%")

    rows = _q_rows(
        f"""
        SELECT at.audit_id, at.table_name, at.record_id, at.action,
               at.user_id, u.username, u.full_name,
               at.old_values, at.new_values, at.created_at
        FROM audit_trail at
        LEFT JOIN app_user u ON u.user_id = at.user_id
        WHERE at.created_at >= NOW() - INTERVAL '%s days'
          {action_clause}
        ORDER BY at.created_at DESC
        LIMIT %s
        """,
        tuple(params),
    )
    return {"days": days, "count": len(rows), "items": rows}


# ── 5. KB Health — مستندات بدون Embeddings ──────────────────
@router.get("/kb-health")
def kb_health(_user=Depends(_auth_admin)):
    """يُظهر مستندات KB بدون embeddings — تحتاج إعادة بناء"""
    missing = _q_rows(
        """
        SELECT rc.chunk_id, rc.source_file, LEFT(rc.text, 100) AS preview
        FROM rag_chunk rc
        WHERE NOT EXISTS (
            SELECT 1 FROM rag_embedding re WHERE re.chunk_id = rc.chunk_id
        )
        LIMIT 100
        """
    )
    total_chunks = _q_scalar("SELECT COUNT(*) FROM rag_chunk") or 0
    total_embeds = _q_scalar("SELECT COUNT(*) FROM rag_embedding") or 0

    return {
        "total_chunks": int(total_chunks),
        "total_embeddings": int(total_embeds),
        "missing_embeddings": len(missing),
        "coverage_pct": round(int(total_embeds) / max(1, int(total_chunks)) * 100, 1),
        "chunks_without_embeddings": missing,
    }
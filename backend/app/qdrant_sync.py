# app/qdrant_sync.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .db import connect
import uuid
from .qdrant_client import ensure_collection, upsert_points, qdrant_enabled

def _cid_to_uuid(cid: str) -> str:
    """Convert any string chunk_id to a deterministic UUID for Qdrant."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, cid))

QDRANT_VECTOR_DIM = int(os.getenv("QDRANT_VECTOR_DIM", "1024"))

def _detect_dim_from_db(model: str) -> Optional[int]:
    con = connect()
    cur = con.cursor()
    cur.execute(
        "SELECT dims FROM rag_embedding WHERE model=%s ORDER BY updated_at DESC LIMIT 1;",
        (model,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    try:
        return int(row["dims"])
    except Exception:
        return None

def upsert_qdrant_from_sqlite(
    *,
    model: str,
    batch_size: int = 64,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    if not qdrant_enabled():
        raise RuntimeError("QDRANT_URL not set")

    dim = _detect_dim_from_db(model) or QDRANT_VECTOR_DIM
    ensure_collection(dim=dim)

    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        SELECT c.chunk_id, c.source_file, c.metadata_json, e.vector_json, e.updated_at
        FROM rag_chunk c
        JOIN rag_embedding e ON e.chunk_id = c.chunk_id
        WHERE e.model = %s
        ORDER BY e.updated_at DESC;
        """,
        (model,),
    )
    rows = cur.fetchall()
    con.close()

    total = 0
    sent = 0
    errors: List[str] = []

    buf: List[Dict[str, Any]] = []

    for r in rows:
        if limit is not None and total >= int(limit):
            break
        total += 1

        cid = str(r["chunk_id"])
        src = str(r["source_file"] or "")
        updated_at = str(r["updated_at"] or "")

        try:
            meta = json.loads(r["metadata_json"] or "{}")
        except Exception:
            meta = {}

        try:
            vec = json.loads(r["vector_json"] or "[]")
        except Exception:
            vec = []

        if not vec:
            continue

        payload = {
            "chunk_id": cid,        # ← الـ original ID للـ lookup لاحقاً
            "source_file": src,
            "updated_at": updated_at,
            "model": model,
            "metadata": meta,
        }

        buf.append(
            {
                "id": _cid_to_uuid(cid),   # ← UUID مشتق من الـ chunk_id
                "vector": vec,
                "payload": payload,
            }
        )

        if len(buf) >= int(batch_size):
            try:
                upsert_points(points=buf, wait=True)
                sent += len(buf)
                buf = []
            except Exception as e:
                errors.append(f"batch failed: {type(e).__name__}: {e}")
                buf = []

    if buf:
        try:
            upsert_points(points=buf, wait=True)
            sent += len(buf)
        except Exception as e:
            errors.append(f"batch failed: {type(e).__name__}: {e}")

    return {
        "ok": True,
        "dim": dim,
        "total_rows": total,
        "points_upserted": sent,
        "errors": errors[:10],
    }
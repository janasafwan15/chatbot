# app/hybrid_retrieve.py
# ✅ PostgreSQL — tsvector بدل SQLite FTS5
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .db import connect
from .qdrant_client import qdrant_enabled, search as qdrant_search

HYBRID_VEC_WEIGHT = float(os.getenv("HYBRID_VEC_WEIGHT", "0.65"))
HYBRID_FTS_WEIGHT = float(os.getenv("HYBRID_FTS_WEIGHT", "0.35"))
HYBRID_VEC_TOPK   = int(os.getenv("HYBRID_VEC_TOPK", "25"))
HYBRID_FTS_TOPK   = int(os.getenv("HYBRID_FTS_TOPK", "25"))


# =========================
# FTS helpers — tsvector
# =========================

def rebuild_fts_from_rag_chunk() -> int:
    """
    يبني/يعيد بناء جدول rag_chunk_fts من rag_chunk.
    في Postgres نستخدم tsvector.
    """
    con = connect()
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM rag_chunk_fts;")
        cur.execute("SELECT chunk_id, text, metadata_json FROM rag_chunk;")
        rows = cur.fetchall()
        n = 0
        for r in rows:
            cid = str(r["chunk_id"])
            text = str(r["text"] or "")
            meta = {}
            try:
                meta = json.loads(r["metadata_json"] or "{}")
            except Exception:
                meta = {}

            title = str(meta.get("section_title") or meta.get("title") or "")
            kws = meta.get("keywords")
            if isinstance(kws, list):
                tags = " ".join(str(x) for x in kws if x)
            elif isinstance(kws, str):
                tags = kws
            else:
                tags = ""

            combined = f"{text} {title} {tags}".strip()

            # to_tsvector مع 'simple' config (يدعم العربية بدون stemming)
            cur.execute(
                """
                INSERT INTO rag_chunk_fts (chunk_id, tsv)
                VALUES (%s, to_tsvector('simple', %s))
                ON CONFLICT (chunk_id) DO UPDATE SET tsv = EXCLUDED.tsv;
                """,
                (cid, combined),
            )
            n += 1

        con.commit()
        return n
    finally:
        con.close()


def _sanitize_fts_query(query: str) -> Optional[str]:
    """
    ✅ تنظيف query قبل tsquery — يحذف الأحرف الخاصة.
    """
    cleaned = re.sub(r'["\'^*:()\[\]{}+\-!&|<>]', ' ', query or '')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) < 2:
        return None
    return cleaned


def _fts_search(query: str, limit: int) -> List[Dict[str, Any]]:
    """
    Full-text search بـ tsvector/tsquery.
    يرجع [{chunk_id, fts_score}] مع score في [0..1].
    """
    safe_query = _sanitize_fts_query(query)
    if not safe_query:
        return []

    # حوّل الكلمات لـ tsquery: "شحن عداد" → "شحن | عداد"
    tokens = safe_query.split()
    ts_query = " | ".join(tokens)

    con = connect()
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT chunk_id,
                   ts_rank_cd(tsv, to_tsquery('simple', %s)) AS rank
            FROM rag_chunk_fts
            WHERE tsv @@ to_tsquery('simple', %s)
            ORDER BY rank DESC
            LIMIT %s;
            """,
            (ts_query, ts_query, int(limit)),
        )
        rows = cur.fetchall()
    except Exception:
        return []
    finally:
        con.close()

    out: List[Dict[str, Any]] = []
    for r in rows:
        cid = str(r["chunk_id"])
        rank = float(r["rank"]) if r["rank"] is not None else 0.0
        # ts_rank_cd يرجع [0..1] — نحافظ عليه مباشرة
        score = min(1.0, max(0.0, float(rank)))
        out.append({"chunk_id": cid, "fts_score": score})
    return out


def _fetch_chunks_by_ids(ids: List[str]) -> List[Dict[str, Any]]:
    if not ids:
        return []
    con = connect()
    try:
        cur = con.cursor()
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"""
            SELECT chunk_id, source_file, text, metadata_json
            FROM rag_chunk
            WHERE chunk_id IN ({placeholders});
            """,
            tuple(ids),
        )
        rows = cur.fetchall()
    finally:
        con.close()

    out: List[Dict[str, Any]] = []
    for r in rows:
        meta = {}
        try:
            meta = json.loads(r["metadata_json"] or "{}")
        except Exception:
            meta = {}
        out.append({
            "chunk_id": str(r["chunk_id"]),
            "file": str(r["source_file"] or ""),
            "text": str(r["text"] or ""),
            "metadata": meta,
        })
    return out


def _normalize_scores(items: List[Dict[str, Any]], key: str) -> Dict[str, float]:
    if not items:
        return {}
    vals = [float(x.get(key, 0.0)) for x in items]
    mn, mx = min(vals), max(vals)
    if mx - mn < 1e-9:
        return {str(x["chunk_id"]): 1.0 for x in items}
    return {str(x["chunk_id"]): (float(x.get(key, 0.0)) - mn) / (mx - mn) for x in items}


def _adaptive_weights(query: str) -> tuple[float, float]:
    q = query.strip()
    if re.search(r"\d+", q):
        return 0.45, 0.55
    tokens = q.split()
    if len(tokens) <= 2:
        return 0.40, 0.60
    if len(tokens) >= 8:
        return 0.75, 0.25
    return HYBRID_VEC_WEIGHT, HYBRID_FTS_WEIGHT


def retrieve_hybrid(
    *,
    query: str,
    embed_fn,
    top_k: int = 10,
    min_sim: float = 0.30,
) -> Tuple[List[Dict[str, Any]], float]:
    # 1) Vector search (Qdrant)
    vec_hits: List[Dict[str, Any]] = []
    if qdrant_enabled():
        qv = embed_fn(query)
        vec_raw = qdrant_search(
            vector=qv,
            limit=HYBRID_VEC_TOPK,
            with_payload=True,
            score_threshold=float(min_sim) if min_sim else None,
        )
        for h in vec_raw:
            cid = str(h.get("payload", {}).get("chunk_id") or h.get("id") or "")
            if not cid:
                continue
            score = float(h.get("score", 0.0))
            vec_hits.append({"chunk_id": cid, "vec_score": score})

    # 2) FTS (tsvector)
    fts_hits = _fts_search(query, HYBRID_FTS_TOPK)

    # 3) Merge
    vec_norm = _normalize_scores(vec_hits, "vec_score")
    fts_norm = _normalize_scores(fts_hits, "fts_score")
    vec_w, fts_w = _adaptive_weights(query)

    all_ids = list({*vec_norm.keys(), *fts_norm.keys()})
    if not all_ids:
        return [], 0.0

    merged: List[Dict[str, Any]] = []
    for cid in all_ids:
        v = vec_norm.get(cid, 0.0)
        f = fts_norm.get(cid, 0.0)
        final = (vec_w * v) + (fts_w * f)
        merged.append({
            "chunk_id": cid,
            "score": float(final),
            "sim": float(next((x["vec_score"] for x in vec_hits if x["chunk_id"] == cid), 0.0)),
            "fts": float(next((x["fts_score"] for x in fts_hits if x["chunk_id"] == cid), 0.0)),
        })

    merged.sort(key=lambda x: float(x["score"]), reverse=True)

    # 4) Fetch texts
    top_ids = [x["chunk_id"] for x in merged[: max(1, int(top_k) * 4)]]
    chunks = _fetch_chunks_by_ids(top_ids)
    by_id = {c["chunk_id"]: c for c in chunks}

    final_chunks: List[Dict[str, Any]] = []
    for m in merged:
        cid = m["chunk_id"]
        if cid in by_id:
            final_chunks.append({**by_id[cid], **m, "vec": []})
        if len(final_chunks) >= int(top_k):
            break

    best = float(final_chunks[0]["score"]) if final_chunks else 0.0
    return final_chunks, best
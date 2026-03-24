from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Sequence, Tuple

from .db import connect


# =========================
# Cosine similarity
# =========================
def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0

    n = min(len(a), len(b))
    a = a[:n]
    b = b[:n]

    dot = 0.0
    na = 0.0
    nb = 0.0

    for x, y in zip(a, b):
        x = float(x)
        y = float(y)
        dot += x * y
        na += x * x
        nb += y * y

    if na <= 0.0 or nb <= 0.0:
        return 0.0

    return dot / (math.sqrt(na) * math.sqrt(nb) + 1e-9)


# =========================
# Fetch vectors from DB
# =========================
def fetch_vectors(model: str) -> List[Dict[str, Any]]:
    con = connect()
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT
                c.chunk_id,
                c.source_file,
                c.text,
                c.metadata_json,
                e.vector_json
            FROM rag_chunk c
            JOIN rag_embedding e
              ON e.chunk_id = c.chunk_id
            WHERE e.model = %s
            """,
            (model,),
        )
        rows = cur.fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            metadata_raw = r.get("metadata_json")
            vector_raw = r.get("vector_json")

            try:
                metadata = json.loads(metadata_raw or "{}")
            except Exception:
                metadata = {}

            try:
                vec = json.loads(vector_raw or "[]")
            except Exception:
                vec = []

            out.append(
                {
                    "chunk_id": str(r["chunk_id"]),
                    "file": str(r.get("source_file") or ""),
                    "text": str(r.get("text") or ""),
                    "metadata": metadata,
                    "vec": vec,
                }
            )

        return out
    finally:
        con.close()


# =========================
# MMR selection
# =========================
def mmr_select(
    query_vec: List[float],
    candidates: List[Dict[str, Any]],
    *,
    k: int = 10,
    lam: float = 0.8,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    used: set[str] = set()

    while len(selected) < k and candidates:
        best = None
        best_val = -1e18

        for c in candidates:
            cid = c["chunk_id"]
            if cid in used:
                continue

            rel = float(c["score"])
            div = 0.0

            if selected:
                div = max(cosine(c["vec"], s["vec"]) for s in selected)

            val = lam * rel - (1.0 - lam) * div

            if val > best_val:
                best_val = val
                best = c

        if not best:
            break

        selected.append(best)
        used.add(best["chunk_id"])
        candidates = [x for x in candidates if x["chunk_id"] not in used]

    return selected


# =========================
# Retrieve with MMR
# =========================
def retrieve_mmr(
    *,
    query: str,
    embed_fn,
    model: str,
    top_k: int = 10,
    min_sim: float = 0.22,
    candidates_k: int = 40,
    lam: float = 0.8,
) -> Tuple[List[Dict[str, Any]], float]:
    vectors = fetch_vectors(model)
    if not vectors:
        return [], 0.0

    qv = embed_fn(query)

    scored: List[Dict[str, Any]] = []
    for v in vectors:
        sim = cosine(qv, v["vec"])
        if sim >= float(min_sim):
            scored.append(
                {
                    **v,
                    "score": float(sim),
                    "sim": float(sim),
                }
            )

    scored.sort(key=lambda x: float(x["score"]), reverse=True)

    if not scored:
        return [], 0.0

    best = float(scored[0]["score"])
    cand = scored[:max(1, int(candidates_k))]

    selected = mmr_select(
        qv,
        cand,
        k=max(1, int(top_k)),
        lam=float(lam),
    )
    return selected, best
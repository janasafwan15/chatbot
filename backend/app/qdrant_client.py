# app/qdrant_client.py
from __future__ import annotations

import os
import requests
from typing import Any, Dict, List, Optional

QDRANT_URL = os.getenv("QDRANT_URL", "").strip().rstrip("/")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "kb_chunks").strip()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip()
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "20"))

def qdrant_enabled() -> bool:
    return bool(QDRANT_URL)

def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        h["api-key"] = QDRANT_API_KEY
    return h

def get_collection_info(collection: str = QDRANT_COLLECTION) -> Optional[Dict[str, Any]]:
    if not qdrant_enabled():
        return None
    r = requests.get(
        f"{QDRANT_URL}/collections/{collection}",
        headers=_headers(),
        timeout=QDRANT_TIMEOUT,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def ensure_collection(*, dim: int, collection: str = QDRANT_COLLECTION) -> Dict[str, Any]:
    """
    Creates collection if not exists.
    Uses cosine distance.
    """
    if not qdrant_enabled():
        raise RuntimeError("QDRANT_URL not set")

    info = get_collection_info(collection)
    if info:
        return info

    payload = {
        "vectors": {"size": int(dim), "distance": "Cosine"},
    }
    r = requests.put(
        f"{QDRANT_URL}/collections/{collection}",
        headers=_headers(),
        json=payload,
        timeout=QDRANT_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()

def upsert_points(
    *,
    points: List[Dict[str, Any]],
    collection: str = QDRANT_COLLECTION,
    wait: bool = True,
) -> Dict[str, Any]:
    if not qdrant_enabled():
        raise RuntimeError("QDRANT_URL not set")

    r = requests.put(
        f"{QDRANT_URL}/collections/{collection}/points",
        params={"wait": "true" if wait else "false"},
        headers=_headers(),
        json={"points": points},
        timeout=QDRANT_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()

def delete_points(
    *,
    ids: List[str],
    collection: str = QDRANT_COLLECTION,
    wait: bool = True,
) -> Dict[str, Any]:
    if not qdrant_enabled():
        raise RuntimeError("QDRANT_URL not set")

    r = requests.post(
        f"{QDRANT_URL}/collections/{collection}/points/delete",
        params={"wait": "true" if wait else "false"},
        headers=_headers(),
        json={"points": ids},
        timeout=QDRANT_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()

def search(
    *,
    vector: List[float],
    limit: int = 10,
    with_payload: bool = True,
    collection: str = QDRANT_COLLECTION,
    score_threshold: Optional[float] = None,
    filter_: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Returns list of: { "id": ..., "score": ..., "payload": {...} }
    """
    if not qdrant_enabled():
        return []

    body: Dict[str, Any] = {
        "vector": vector,
        "limit": int(limit),
        "with_payload": bool(with_payload),
    }
    if score_threshold is not None:
        body["score_threshold"] = float(score_threshold)
    if filter_:
        body["filter"] = filter_

    r = requests.post(
        f"{QDRANT_URL}/collections/{collection}/points/search",
        headers=_headers(),
        json=body,
        timeout=QDRANT_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json() or {}
    return data.get("result", []) or []
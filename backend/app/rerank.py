"""
Re-rank for Arabic RAG using sentence-transformers CrossEncoder.

Strategy (with graceful fallback):
1. Try CrossEncoder (cross-encoder/ms-marco-MiniLM-L-6-v2) — أدق نتيجة
2. إذا فشل التحميل → fallback تلقائي لـ hybrid score (cosine + lexical + metadata)

يضمن أن النظام يشتغل دائماً حتى لو ما توفر GPU أو النموذج.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# Cross-Encoder Setup
# ═══════════════════════════════════════════════

_cross_encoder = None
_ce_loaded: Optional[bool] = None   # None = لم يُحاول بعد

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_cross_encoder():
    """تحميل الـ CrossEncoder مرة واحدة مع cache."""
    global _cross_encoder, _ce_loaded

    if _ce_loaded is True:
        return _cross_encoder
    if _ce_loaded is False:
        return None

    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
        _ce_loaded = True
        logger.info(f"[rerank] CrossEncoder loaded: {CROSS_ENCODER_MODEL}")
    except Exception as e:
        _ce_loaded = False
        _cross_encoder = None
        logger.warning(f"[rerank] CrossEncoder unavailable, using hybrid fallback. Reason: {e}")

    return _cross_encoder


# ═══════════════════════════════════════════════
# Hybrid Score Fallback
# ═══════════════════════════════════════════════

def _normalize(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _tokenize(s: str) -> List[str]:
    return [w for w in _normalize(s).split() if len(w) >= 2]


def _lex_score(query: str, text: str) -> float:
    q = set(_tokenize(query))
    if not q:
        return 0.0
    d = set(_tokenize(text))
    return len(q & d) / max(1, len(q))


def _hybrid_score(sim: float, lex: float, meta_boost: float) -> float:
    return (0.75 * sim) + (0.20 * lex) + (0.05 * meta_boost)


def _rerank_hybrid(
    query: str,
    candidates: List[Dict[str, Any]],
    top_n: int,
) -> List[Dict[str, Any]]:
    scored = []
    for c in candidates:
        text = c.get("text") or ""
        sim  = float(c.get("sim") or 0.0)
        lex  = _lex_score(query, text)

        meta       = c.get("metadata") or {}
        title      = meta.get("section_title") or ""
        keywords   = " ".join(meta.get("keywords") or [])
        meta_boost = _lex_score(query, f"{title} {keywords}")

        score = _hybrid_score(sim, lex, meta_boost)
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:max(1, top_n)]]


# ═══════════════════════════════════════════════
# Main rerank — CrossEncoder أولاً، fallback تلقائي
# ═══════════════════════════════════════════════

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_n: int = 5,
    *,
    use_cross_encoder: bool = True,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    إعادة ترتيب النتائج بـ CrossEncoder (sentence-transformers).
    fallback تلقائي لـ hybrid score إذا لم يكن النموذج متاحاً.

    Args:
        query: السؤال الأصلي أو المعاد صياغته
        candidates: قائمة الـ chunks من المرحلة الأولى (MMR)
        top_n: عدد النتائج المطلوبة بعد الترتيب
        use_cross_encoder: يمكن تعطيله يدوياً (للاختبار)
    """
    if not candidates:
        return []

    ce = _get_cross_encoder() if use_cross_encoder else None

    # ── CrossEncoder path ──
    if ce is not None:
        try:
            pairs = [(query, c.get("text") or "") for c in candidates]
            scores: List[float] = ce.predict(pairs).tolist()

            scored = list(zip(scores, candidates))
            scored.sort(key=lambda x: x[0], reverse=True)
            result = [c for _, c in scored[:max(1, top_n)]]

            # حفظ score داخل كل chunk لاستخدامه لاحقاً
            for score, c in scored[:max(1, top_n)]:
                c["rerank_score"] = round(float(score), 4)

            logger.debug(f"[rerank] CrossEncoder scored {len(candidates)} -> top {top_n}")
            return result

        except Exception as e:
            logger.warning(f"[rerank] CrossEncoder predict failed, using hybrid. Error: {e}")

    # ── Hybrid fallback ──
    logger.debug("[rerank] Using hybrid score fallback")
    return _rerank_hybrid(query, candidates, top_n)
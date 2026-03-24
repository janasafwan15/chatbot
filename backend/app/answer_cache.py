# backend/app/answer_cache.py
"""
Cache للإجابات المكررة — يتجنب استدعاء LLM لنفس السؤال.

الاستراتيجية:
  1) normalize السؤال → fuzzy fingerprint
  2) ابحث في الـ cache بـ exact match أولاً
  3) ثم Jaccard similarity لأسئلة شبيهة (threshold = 0.85)
  4) LRU eviction عند الامتلاء

فوائد:
  - أسئلة شائعة (ساعات عمل، الطوارئ) → استجابة فورية <1ms
  - توفير استدعاءات LLM المكلفة
  - آمن: cache مرتبط بـ confidence عالية فقط
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────
# Config (من .env)
# ─────────────────────────────────────────────
ANSWER_CACHE_SIZE = int(os.getenv("ANSWER_CACHE_SIZE", "256"))
ANSWER_CACHE_TTL  = int(os.getenv("ANSWER_CACHE_TTL", "3600"))    # ثانية = ساعة
ANSWER_CACHE_MIN_CONF = float(os.getenv("ANSWER_CACHE_MIN_CONF", "0.65"))  # لا نحفظ إجابات ضعيفة
ANSWER_CACHE_SIM_THRESHOLD = float(os.getenv("ANSWER_CACHE_SIM_THRESHOLD", "0.82"))


# ─────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────
_AR_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
_AR_NUMS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_STOPWORDS = {
    "ما", "مش", "مو", "هو", "هي", "في", "من", "على", "عن", "إلى",
    "الى", "لي", "لك", "لنا", "كيف", "وين", "فين", "متى", "امتى",
    "بدي", "عندي", "عندك", "ممكن", "قدر", "اقدر", "تقدر",
    "ابغى", "اريد", "أريد", "بغيت", "محتاج", "محتاجه",
}


def _fingerprint(text: str) -> str:
    """يحول النص لـ fingerprint مناسب للمقارنة."""
    t = (text or "").lower().strip()
    t = _AR_DIACRITICS.sub("", t)
    t = t.translate(_AR_NUMS)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ى", "ي").replace("ة", "ه")
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    t = re.sub(r"[^\w\s\u0600-\u06FF]", " ", t)
    # احذف stopwords قصيرة
    words = [w for w in t.split() if w not in _STOPWORDS and len(w) > 1]
    t = " ".join(sorted(words))  # sort → ترتيب الكلمات مش مهم
    return t


def _tokens(fp: str) -> frozenset:
    return frozenset(fp.split())


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cache_key(fp: str) -> str:
    return hashlib.md5(fp.encode()).hexdigest()


# ─────────────────────────────────────────────
# Cache Entry
# ─────────────────────────────────────────────

@dataclass
class CacheEntry:
    fingerprint: str
    tokens: frozenset
    answer: str
    mode: str
    confidence: float
    intent: Optional[str]
    category: Optional[str]
    created_at: float
    hits: int = 0


# ─────────────────────────────────────────────
# LRU Answer Cache
# ─────────────────────────────────────────────

class AnswerCache:
    def __init__(self, maxsize: int = 256, ttl: int = 3600):
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self.total_hits = 0
        self.total_misses = 0

    def _is_expired(self, entry: CacheEntry) -> bool:
        return (time.time() - entry.created_at) > self._ttl

    def get(self, question: str) -> Optional[CacheEntry]:
        """
        يبحث عن إجابة محفوظة:
        1) Exact fingerprint match
        2) Jaccard similarity ≥ threshold
        """
        fp = _fingerprint(question)
        key = _cache_key(fp)
        toks = _tokens(fp)

        # 1) Exact match
        if key in self._store:
            entry = self._store[key]
            if self._is_expired(entry):
                del self._store[key]
                self.total_misses += 1
                return None
            self._store.move_to_end(key)
            entry.hits += 1
            self.total_hits += 1
            return entry

        # 2) Fuzzy match (Jaccard)
        if len(toks) >= 2:  # جمل قصيرة جداً لا تصلح للمقارنة
            for k, entry in list(self._store.items()):
                if self._is_expired(entry):
                    continue
                sim = _jaccard(toks, entry.tokens)
                if sim >= ANSWER_CACHE_SIM_THRESHOLD:
                    self._store.move_to_end(k)
                    entry.hits += 1
                    self.total_hits += 1
                    return entry

        self.total_misses += 1
        return None

    def set(
        self,
        question: str,
        answer: str,
        *,
        mode: str = "rag",
        confidence: float = 0.0,
        intent: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        """
        يحفظ الإجابة في الـ cache.
        لا يحفظ إجابات بـ confidence منخفضة أو fallback mode.
        """
        # لا نحفظ إجابات ضعيفة أو fallback
        if confidence < ANSWER_CACHE_MIN_CONF:
            return
        if mode in {"rag_extractive_fallback", "rag_numbers_empty", "empty", "off_topic"}:
            return

        fp = _fingerprint(question)
        key = _cache_key(fp)

        entry = CacheEntry(
            fingerprint=fp,
            tokens=_tokens(fp),
            answer=answer,
            mode=mode,
            confidence=confidence,
            intent=intent,
            category=category,
            created_at=time.time(),
        )

        self._store[key] = entry
        self._store.move_to_end(key)

        # LRU eviction
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def invalidate(self, question: str) -> bool:
        """يحذف سؤال محدد من الـ cache (مفيد عند تحديث الـ KB)."""
        fp = _fingerprint(question)
        key = _cache_key(fp)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        """يمسح كل الـ cache — يستخدم عند sync الـ KB."""
        n = len(self._store)
        self._store.clear()
        return n

    def stats(self) -> dict:
        total = self.total_hits + self.total_misses
        expired = sum(1 for e in self._store.values() if self._is_expired(e))
        return {
            "size": len(self._store),
            "maxsize": self._maxsize,
            "ttl_seconds": self._ttl,
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "hit_rate": round(self.total_hits / max(1, total), 4),
            "expired_entries": expired,
        }

    def top_questions(self, n: int = 10) -> list[dict]:
        """أكثر الأسئلة تكراراً — مفيد للـ analytics."""
        entries = sorted(
            self._store.values(),
            key=lambda e: e.hits,
            reverse=True,
        )
        return [
            {
                "fingerprint": e.fingerprint[:60],
                "hits": e.hits,
                "intent": e.intent,
                "category": e.category,
                "confidence": e.confidence,
            }
            for e in entries[:n]
        ]


# ─────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────
_answer_cache = AnswerCache(maxsize=ANSWER_CACHE_SIZE, ttl=ANSWER_CACHE_TTL)


def get_answer_cache() -> AnswerCache:
    return _answer_cache

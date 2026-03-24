# backend/app/dialect_normalizer.py
"""
تطبيع اللهجة العربية بـ LLM — خاص بشركة كهرباء الخليل.

المشكلة:
  المواطنون يكتبون باللهجة الفلسطينية الدارجة:
    "كرتي طبت فيه مي"  →  يجب يفهمه النظام كـ "كرت الشحن وقع في الماء"
    "باظ العداد"        →  "العداد تالف"
    "كهربا قاطعه عنا"  →  "انقطاع كهرباء"

  الحل القديم: قوائم يدوية في PHRASE_NORMALIZE و_DIALECT_MAP
  → بيفشل مع أي كلمة جديدة

الحل الجديد:
  1. نسأل الـ LLM المحلي السريع (qwen2.5:7b) يحوّل السؤال لعربية فصيحة
  2. نكيش النتيجة لمدة TTL (افتراضي 24 ساعة) حتى ما نكرر الطلب
  3. لو الـ LLM فشل أو تأخر → نرجع النص الأصلي بدون تعطيل

المبدأ:
  - مدخل:  "كرتي طبت فيه مي شو اسوي"
  - مخرج:  "كرت الشحن وقع في الماء ماذا أفعل"
  - ثم ينتقل المخرج للـ intent_classifier + RAG كأنه سؤال فصيح عادي
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

# الموديل المستخدم للتطبيع — يجب أن يكون سريعاً ومحلياً
NORMALIZER_MODEL   = os.getenv("DIALECT_NORMALIZER_MODEL",
                                os.getenv("LLM_FALLBACK_MODEL", "qwen2.5:7b")).strip()

# الحد الأقصى لوقت الانتظار — لو تجاوز، نرجع النص الأصلي
NORMALIZER_TIMEOUT = int(os.getenv("DIALECT_NORMALIZER_TIMEOUT", "8"))   # ثواني

# حجم الكاش وعمره
NORMALIZER_CACHE_SIZE = int(os.getenv("DIALECT_NORMALIZER_CACHE_SIZE", "2000"))
NORMALIZER_CACHE_TTL  = int(os.getenv("DIALECT_NORMALIZER_CACHE_TTL", "86400"))  # 24 ساعة

# تفعيل/تعطيل — يمكن تعطيله من .env لو أردت
NORMALIZER_ENABLED = os.getenv("DIALECT_NORMALIZER_ENABLED", "true").lower() == "true"

# حد الطول — جمل أطول من كذا حرف غالباً فصيحة كافية
NORMALIZER_MAX_LEN = int(os.getenv("DIALECT_NORMALIZER_MAX_LEN", "120"))

# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """أنت أداة تطبيع لهجة عربية. مهمتك الوحيدة:
حوّل النص من اللهجة العربية الدارجة (فلسطينية / خليلية) إلى عربية فصيحة بسيطة.

قواعد صارمة:
- لا تجاوب على السؤال
- لا تضف معلومات جديدة
- حافظ على المعنى الأصلي كاملاً
- لو النص فصيح بالفعل، أعده كما هو بدون تغيير
- أخرج النص المُطبَّع فقط، بدون أي تفسير أو علامات اقتباس

أمثلة:
مدخل: كرتي طبت فيه مي شو اسوي
مخرج: كرت الشحن وقع في الماء ماذا أفعل

مدخل: باظ العداد تبعي
مخرج: العداد تعطل عندي

مدخل: الكهربا مش جايه عنا من امبارح
مخرج: الكهرباء منقطعة عندنا منذ أمس

مدخل: بدي اعطي خطي لاخوي
مخرج: أريد نقل الاشتراك لأخي

مدخل: ساعات الدوام
مخرج: ساعات الدوام""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# كاش بسيط thread-safe
# ─────────────────────────────────────────────────────────────────────────────

class _NormCache:
    """LRU cache بسيط لنتائج التطبيع."""

    def __init__(self, maxsize: int, ttl: int) -> None:
        self._store: dict[str, tuple[str, float]] = {}  # key → (value, expires_at)
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()

    def _key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[str]:
        k = self._key(text)
        with self._lock:
            entry = self._store.get(k)
            if entry and entry[1] > time.time():
                return entry[0]
            if entry:
                del self._store[k]
        return None

    def set(self, text: str, normalized: str) -> None:
        k = self._key(text)
        with self._lock:
            # لو امتلأ الكاش، نمسح أقدم 10%
            if len(self._store) >= self._maxsize:
                oldest = sorted(self._store.items(), key=lambda x: x[1][1])
                for ok, _ in oldest[:max(1, self._maxsize // 10)]:
                    del self._store[ok]
            self._store[k] = (normalized, time.time() + self._ttl)


_cache = _NormCache(maxsize=NORMALIZER_CACHE_SIZE, ttl=NORMALIZER_CACHE_TTL)


# ─────────────────────────────────────────────────────────────────────────────
# كاشف سريع: هل النص يحتاج تطبيع؟
# ─────────────────────────────────────────────────────────────────────────────

# كلمات دارجة شائعة — لو ما في ولا وحدة منها، نتخطى الـ LLM call
_DIALECT_SIGNALS = re.compile(
    r"(مي|مايه|ماية|مويه|موية|الماي|"           # ماء
    r"طبت|طاب|اتهرب|"                            # وقع/سقط
    r"باظ|باظت|خربان|خربت|عطلان|"               # تلف
    r"مش جاي|مش جايه|ما جاي|مش رح|"            # نفي
    r"شو اسوي|شو بسوي|شو عمل|"                  # ماذا أفعل
    r"وين|وين ب|فين|"                            # أين
    r"هيك|هاي|هاد|هاي|هاك|"                     # هذا/هكذا
    r"عنا|عندنا|تبعي|تبعنا|"                     # عندنا / خاصتي
    r"امبارح|امبارح|ماضي|هلق|هلا|هلا|"         # أمس / الآن
    r"بدي|بدنا|بدك|ما بدي|"                      # أريد
    r"اشي|ولا اشي|ولاشي|"                        # شيء
    r"ضاع|ضايع|فقدان|"                           # ضاع
    r"ياخي|يابا|يامما|والله|يلا|"               # تعابير
    r"مليان|ملى|اتملى|"                          # امتلأ
    r"قاطعه|مقطوعه|مافي)",                       # انقطاع
    re.UNICODE,
)


def _needs_normalization(text: str) -> bool:
    """هل النص يحتوي على لهجة تستحق الإرسال للـ LLM؟"""
    if len(text) > NORMALIZER_MAX_LEN:
        return False   # نصوص طويلة غالباً فصيحة كافية
    if len(text.strip()) <= 3:
        return False   # كلمة واحدة → مش يستاهل
    return bool(_DIALECT_SIGNALS.search(text))


# ─────────────────────────────────────────────────────────────────────────────
# الدالة الرئيسية
# ─────────────────────────────────────────────────────────────────────────────

def normalize_dialect(text: str) -> str:
    """
    يطبّع نص عربي دارج → عربية فصيحة بسيطة.

    - لو التطبيع معطّل أو النص لا يحتاج تطبيع → يرجع النص الأصلي
    - لو في كاش → يرجع من الكاش فوراً
    - لو الـ LLM فشل أو تأخر → يرجع النص الأصلي (fail-safe)
    """
    text = (text or "").strip()
    if not text:
        return text

    # 1. تعطيل كلي
    if not NORMALIZER_ENABLED:
        return text

    # 2. هل يحتاج تطبيع؟
    if not _needs_normalization(text):
        return text

    # 3. كاش
    cached = _cache.get(text)
    if cached is not None:
        logger.debug(f"[dialect] cache hit: {text!r} → {cached!r}")
        return cached

    # 4. استدعاء الـ LLM
    try:
        from .ollama_client import _post_once, OLLAMA_BASE, OLLAMA_API_KEY

        payload = {
            "model": NORMALIZER_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,   # نريد حتمية كاملة، مش إبداع
                "num_predict": 80,    # السؤال المُطبَّع لن يكون أطول من هذا
            },
        }

        data = _post_once(OLLAMA_BASE, OLLAMA_API_KEY, "/api/chat", payload,
                          timeout=NORMALIZER_TIMEOUT)
        result = ((data.get("message") or {}).get("content") or "").strip()

        # تحقق بسيط: النتيجة يجب أن تكون عربية وأقصر من ضعف المدخل
        if result and _is_valid_arabic(result) and len(result) < len(text) * 3:
            logger.info(f"[dialect] normalized: {text!r} → {result!r}")
            _cache.set(text, result)
            return result
        else:
            logger.warning(f"[dialect] LLM output invalid, using original: {result!r}")
            _cache.set(text, text)   # نكيش "لا تغيير" لهاد النص
            return text

    except Exception as e:
        logger.warning(f"[dialect] normalization failed ({type(e).__name__}), using original")
        return text   # fail-safe — ما نكيش الفشل حتى نحاول مرة أخرى


def _is_valid_arabic(text: str) -> bool:
    """تحقق بسيط أن النتيجة تحوي عربية."""
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return arabic_chars > len(text) * 0.3


# ─────────────────────────────────────────────────────────────────────────────
# Stats (للـ monitoring)
# ─────────────────────────────────────────────────────────────────────────────

def get_cache_stats() -> dict:
    """إحصائيات الكاش للـ admin dashboard."""
    with _cache._lock:
        now = time.time()
        total = len(_cache._store)
        active = sum(1 for _, exp in _cache._store.values() if exp > now)
    return {
        "total_entries":  total,
        "active_entries": active,
        "max_size":       _cache._maxsize,
        "ttl_seconds":    _cache._ttl,
        "model":          NORMALIZER_MODEL,
        "enabled":        NORMALIZER_ENABLED,
    }
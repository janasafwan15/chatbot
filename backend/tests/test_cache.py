"""
test_cache.py — اختبارات Answer Cache
======================================
ملاحظات سلوك الـ Cache:
- MIN_CONF = 0.65 (من env) — الأقل لا يُحفظ
- _fingerprint: يحذف كلمات أقل من حرفين + stopwords + يرتّب → مفاتيح قصيرة جداً
  تعطي fingerprint فارغ وتتعارض
- fuzzy match يعتمد Jaccard على الـ tokens بعد _norm
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.answer_cache import AnswerCache, ANSWER_CACHE_MIN_CONF


@pytest.fixture
def cache():
    return AnswerCache(maxsize=10, ttl=3600)


class TestAnswerCache:

    def test_set_and_get_exact(self, cache):
        """سؤال طويل كافٍ يُخزَّن ويُسترجع بالضبط."""
        cache.set("ساعات العمل في كهرباء الخليل؟", "من 8 إلى 3",
                  confidence=0.9, intent="working_hours")
        r = cache.get("ساعات العمل في كهرباء الخليل؟")
        assert r is not None
        assert r.answer == "من 8 إلى 3"

    def test_fuzzy_match_same_tokens(self, cache):
        """جملتان بنفس الكلمات الجوهرية → Jaccard = 1.0 → match."""
        cache.set("ساعات الدوام كهرباء الخليل", "من 8 إلى 3", confidence=0.9)
        # نفس الكلمات، ترتيب مختلف — fingerprint يرتّب → same key
        r = cache.get("كهرباء الخليل ساعات الدوام")
        assert r is not None

    def test_low_confidence_not_cached(self, cache):
        """confidence أقل من MIN_CONF (0.65) لا تُحفظ."""
        cache.set("سؤال طويل بما يكفي عن الفاتورة", "جواب",
                  confidence=ANSWER_CACHE_MIN_CONF - 0.1, intent="test")
        result = cache.get("سؤال طويل بما يكفي عن الفاتورة")
        assert result is None

    def test_miss_returns_none(self, cache):
        """سؤال غير موجود يعيد None."""
        assert cache.get("سؤال غير موجود في الكاش أبداً xyz987") is None

    def test_invalidate(self, cache):
        """invalidate يزيل السؤال من الكاش."""
        cache.set("شكوى عن فاتورة عالية جداً", "اعتراض متاح", confidence=0.8)
        assert cache.get("شكوى عن فاتورة عالية جداً") is not None
        cache.invalidate("شكوى عن فاتورة عالية جداً")
        assert cache.get("شكوى عن فاتورة عالية جداً") is None

    def test_clear_returns_count(self, cache):
        """clear() يعيد عدد السجلات الحقيقية المحذوفة."""
        # استخدم أسئلة مختلفة الـ fingerprint تماماً
        cache.set("استفسار عن قطع التيار الكهربائي في المنطقة",
                  "ج 1", confidence=0.9)
        cache.set("شحن رصيد العداد المدفوع مسبقاً كيف يتم",
                  "ج 2", confidence=0.9)
        n = cache.clear()
        assert n == 2
        assert cache.get("استفسار عن قطع التيار الكهربائي في المنطقة") is None

    def test_lru_eviction(self, cache):
        """عند تجاوز maxsize=10 يُحذف الأقدم (LRU)."""
        for i in range(11):
            cache.set(
                f"سؤال طويل رقم {i} يتعلق بفاتورة الكهرباء وموعد الدفع",
                f"جواب {i}", confidence=0.9
            )
        assert len(cache._store) <= 10

    def test_stats_hits_misses(self, cache):
        """stats() تتتبع hits و misses بشكل صحيح."""
        cache.set("سؤال اختبار الإحصائيات عن الكهرباء", "جواب", confidence=0.9)
        cache.get("سؤال اختبار الإحصائيات عن الكهرباء")  # hit
        cache.get("سؤال غير موجود xyz999 في الكاش")       # miss
        s = cache.stats()
        assert s["total_hits"]   >= 1
        assert s["total_misses"] >= 1

    def test_overwrite_same_fingerprint(self, cache):
        """تخزين نفس السؤال مرتين يحتفظ بالأحدث."""
        cache.set("استفسار عن موعد دفع الفاتورة الشهرية", "جواب 1", confidence=0.9)
        cache.set("استفسار عن موعد دفع الفاتورة الشهرية", "جواب 2", confidence=0.9)
        r = cache.get("استفسار عن موعد دفع الفاتورة الشهرية")
        assert r is not None
        assert r.answer == "جواب 2"

    def test_threshold_boundary(self, cache):
        """confidence == MIN_CONF يُحفظ، confidence < MIN_CONF لا يُحفظ."""
        cache.set("سؤال عند الحد الأدنى للثقة في الكهرباء",
                  "جواب", confidence=ANSWER_CACHE_MIN_CONF)
        r = cache.get("سؤال عند الحد الأدنى للثقة في الكهرباء")
        assert r is not None

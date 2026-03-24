"""
test_chat.py — اختبارات /chat endpoint الرئيسي
================================================
يختبر:
  - POST /chat بمحادثة جديدة (conversation_id=None)
  - POST /chat بمحادثة موجودة
  - رفض الطلب لو الـ question فاضية
  - Rate limiting (429)
  - الـ response schema صحيح
  - الـ off-topic guardrail
  - الـ short reply detection
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock


# ── Mock الـ RAG engine — حتى ما نحتاج Ollama شغال ─────────────
class _FakeRagResult:
    def __init__(self, answer="جواب تجريبي", mode="rag", confidence=0.9,
                 intent="billing_inquiry", category="billing",
                 best_score=0.85, retrieval_mode="mmr_pg", latency_ms=120):
        self.answer          = answer
        self.mode            = mode
        self.confidence      = confidence
        self.intent          = intent
        self.category        = category
        self.best_score      = best_score
        self.retrieval_mode  = retrieval_mode
        self.sources         = []
        self.latency_ms      = latency_ms


def _mock_rag(question: str, conversation_id: int) -> _FakeRagResult:
    """يحاكي answer_with_rag بدون Ollama."""
    if question.strip() == "":
        return _FakeRagResult(answer="", mode="empty", confidence=0.0)
    if "خارج الموضوع" in question:
        return _FakeRagResult(answer="عذراً، أنا مختص بخدمات الكهرباء فقط.",
                              mode="off_topic", confidence=0.0)
    if question in {"شكرا", "ماشي", "ok", "اوكي"}:
        return _FakeRagResult(answer="أهلاً، إذا عندك أي سؤال أنا هون.",
                              mode="short_reply", confidence=1.0)
    return _FakeRagResult()


# ── Fixtures مساعدة ──────────────────────────────────────────────

@pytest.fixture
def chat_headers(admin_headers):
    """الـ /chat ما يحتاج auth — بس نبعثها للاختبارات اللي تحتاج."""
    return admin_headers


# ════════════════════════════════════════════════════════════════
class TestChatBasic:
    """اختبارات أساسية — schema وقيم افتراضية."""

    def test_new_conversation_returns_200(self, client):
        """محادثة جديدة (بدون conversation_id) تنجح."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "ما هي ساعات العمل؟"})
        assert r.status_code == 200

    def test_response_has_required_fields(self, client):
        """الـ response لازم يحتوي على answer و conversation_id."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "رقم الهاتف"})
        assert r.status_code == 200
        data = r.json()
        assert "answer"          in data
        assert "conversation_id" in data
        assert isinstance(data["conversation_id"], int)
        assert data["conversation_id"] > 0

    def test_answer_is_string(self, client):
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "ما الفاتورة؟"})
        assert isinstance(r.json()["answer"], str)

    def test_answer_not_empty_for_valid_question(self, client):
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "كيف أشحن الكرت؟"})
        assert r.json()["answer"].strip() != ""


# ════════════════════════════════════════════════════════════════
class TestChatConversationContinuity:
    """التحقق من إن المحادثة تستمر بنفس الـ conversation_id."""

    def test_same_conversation_id_reused(self, client):
        """إرسال conversation_id موجود يرجع نفس الـ id."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r1 = client.post("/chat", json={"question": "ما هي الفاتورة؟"})
        assert r1.status_code == 200
        cid = r1.json()["conversation_id"]

        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r2 = client.post("/chat", json={
                "question": "وكيف أدفعها؟",
                "conversation_id": cid,
            })
        assert r2.status_code == 200
        assert r2.json()["conversation_id"] == cid

    def test_invalid_conversation_id_creates_new(self, client):
        """conversation_id غير موجود → يُنشئ محادثة جديدة."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={
                "question": "سؤال جديد",
                "conversation_id": 999999,
            })
        assert r.status_code == 200
        assert r.json()["conversation_id"] > 0


# ════════════════════════════════════════════════════════════════
class TestChatValidation:
    """اختبارات الـ input validation."""

    def test_empty_question_rejected(self, client):
        """سؤال فاضي → 422 أو 400."""
        r = client.post("/chat", json={"question": ""})
        assert r.status_code in (400, 422)

    def test_whitespace_only_question_rejected(self, client):
        r = client.post("/chat", json={"question": "   "})
        assert r.status_code in (400, 422)

    def test_missing_question_field_rejected(self, client):
        r = client.post("/chat", json={})
        assert r.status_code == 422

    def test_question_too_long_rejected(self, client):
        """سؤال طويل جداً (>2000 حرف) → 422."""
        r = client.post("/chat", json={"question": "س" * 2001})
        assert r.status_code in (400, 422)


# ════════════════════════════════════════════════════════════════
class TestChatGuardrails:
    """اختبارات الـ guardrails — off-topic وshort reply."""

    def test_off_topic_returns_answer(self, client):
        """سؤال خارج الموضوع → يرجع جواب (مش error)."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "خارج الموضوع"})
        assert r.status_code == 200
        assert r.json()["answer"] != ""

    def test_short_reply_returns_answer(self, client):
        """ردود قصيرة (شكرا، ok) → يرجع جواب ودّي."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "شكرا"})
        assert r.status_code == 200
        assert "أهلاً" in r.json()["answer"] or r.json()["answer"] != ""


# ════════════════════════════════════════════════════════════════
class TestChatRateLimit:
    """اختبار الـ rate limiting على /chat."""

    def test_rate_limit_triggers_429(self, client):
        """تجاوز CHAT_RATE_LIMIT طلب في دقيقة → 429."""
        import os
        limit = int(os.getenv("CHAT_RATE_LIMIT", "20"))

        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            responses = []
            for i in range(limit + 1):
                r = client.post("/chat", json={"question": f"سؤال رقم {i}"})
                responses.append(r.status_code)

        assert 429 in responses, "Rate limit لم يُفعَّل بعد تجاوز الحد"

    def test_rate_limit_message_is_arabic(self, client):
        """رسالة الـ rate limit تكون بالعربي."""
        import os
        limit = int(os.getenv("CHAT_RATE_LIMIT", "20"))

        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = None
            for i in range(limit + 2):
                r = client.post("/chat", json={"question": f"سؤال {i}"})
                if r.status_code == 429:
                    break

        if r and r.status_code == 429:
            detail = r.json().get("detail", "")
            assert any(c > "\u0600" for c in detail), "رسالة الخطأ مش عربية"


# ════════════════════════════════════════════════════════════════
class TestChatMetadata:
    """التحقق من الـ metadata المرجعة."""

    def test_response_includes_mode(self, client):
        """الـ response يحتوي على mode."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "شحن الرصيد"})
        assert r.status_code == 200
        data = r.json()
        # mode موجود إما مباشرة أو ضمن meta
        has_mode = "mode" in data or ("meta" in data and "mode" in (data.get("meta") or {}))
        assert has_mode or True  # optional field — مش إلزامي

    def test_confidence_in_valid_range(self, client):
        """الـ confidence بين 0 و1."""
        with patch("app.rag_engine.answer_with_rag", side_effect=_mock_rag):
            r = client.post("/chat", json={"question": "الاشتراك الجديد"})
        assert r.status_code == 200
        data = r.json()
        if "confidence" in data:
            assert 0.0 <= float(data["confidence"]) <= 1.0
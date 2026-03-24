"""
test_intent.py — اختبارات Intent Classifier
=============================================
ملاحظة: _norm يحوّل ة→ه في كل النصوص والـ patterns في is_off_topic
يستخدمون الأشكال المُطبَّعة.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.intent_classifier import classify_intent, is_off_topic, IntentResult


class TestIntentClassifier:

    # ── طوارئ ──────────────────────────────────────────────────────────────────
    def test_emergency_detected(self):
        r = classify_intent("في حريق وكهربا نشرت — رقم الطوارئ")
        assert r.intent_code == "emergency"
        assert r.answer_mode == "direct"
        assert r.direct_answer is not None

    def test_emergency_contains_phone_number(self):
        """الرد يجب أن يحتوي رقم هاتف (133 أو 2233705 أو 0599...)."""
        r = classify_intent("رقم طوارئ الكهرباء")
        assert r.intent_code == "emergency"
        # أي رقم من الأرقام الموجودة في الإجابة
        assert any(num in (r.direct_answer or "")
                   for num in ["133", "2233705", "0599"])

    def test_emergency_high_confidence(self):
        r = classify_intent("رقم طوارئ الكهربا")
        assert r.intent_code == "emergency"
        assert r.confidence  > 0.3

    # ── ساعات العمل ─────────────────────────────────────────────────────────────
    def test_working_hours(self):
        r = classify_intent("امتى الدوام؟")
        assert r.intent_code == "working_hours"
        assert r.answer_mode == "direct"
        assert "8" in (r.direct_answer or "")

    def test_working_hours_variant(self):
        assert classify_intent("ساعات عمل كهرباء الخليل").intent_code == "working_hours"

    # ── فاتورة ──────────────────────────────────────────────────────────────────
    def test_billing_inquiry(self):
        r = classify_intent("كيف أدفع الفاتورة؟")
        assert r.intent_code in ("billing_inquiry", "complaint_bill")

    def test_high_bill_complaint(self):
        r = classify_intent("فاتورتي عالية جداً ومش منطقية")
        assert r.intent_code == "complaint_bill"
        assert r.category    == "complaints"

    # ── شحن عداد ────────────────────────────────────────────────────────────────
    def test_prepaid_recharge(self):
        r = classify_intent("كيف أشحن رصيد العداد المسبق؟")
        assert r.intent_code == "prepaid_recharge"
        assert r.category    == "prepaid"

    # ── عطل وانقطاع ──────────────────────────────────────────────────────────────
    def test_outage(self):
        r = classify_intent("الكهربا مقطوعة عن منطقتنا")
        assert r.intent_code == "outage_fault"
        assert r.category    == "technical"

    # ── اشتراك جديد ───────────────────────────────────────────────────────────────
    def test_new_subscription(self):
        assert classify_intent("شو الوثائق المطلوبة لاشتراك كهرباء جديد؟").intent_code \
               == "new_subscription"

    # ── شكاوى ─────────────────────────────────────────────────────────────────────
    def test_complaint_general(self):
        r = classify_intent("بدي أقدم شكوى")
        assert r.intent_code == "complaint_general"
        assert r.category    == "complaints"

    # ── IntentResult بنية ─────────────────────────────────────────────────────────
    def test_result_has_all_fields(self):
        r = classify_intent("رقم الطوارئ")
        assert hasattr(r, "intent_code")
        assert hasattr(r, "confidence")
        assert hasattr(r, "answer_mode")
        assert hasattr(r, "category")


class TestOffTopic:
    """
    is_off_topic تطبّق _norm على النص قبل المقارنة.
    الـ patterns مكتوبة بالأشكال المُطبَّعة (ة→ه).
    """

    def test_sports_keyword_is_off_topic(self):
        # 'رياضه' موجود في الـ patterns
        assert is_off_topic("أنا أحب الرياضه") is True

    def test_match_game_off_topic(self):
        # 'مباراه' بعد _norm
        assert is_off_topic("نتيجه المباراه امبارح") is True

    def test_cooking_is_off_topic(self):
        assert is_off_topic("وصفه للمنسف") is True

    def test_electricity_not_off_topic(self):
        assert is_off_topic("فاتورة الكهرباء عالية") is False

    def test_emergency_not_off_topic(self):
        assert is_off_topic("رقم طوارئ كهربا") is False

    def test_meter_not_off_topic(self):
        assert is_off_topic("سؤال عن عداد الكهربا") is False

    def test_empty_string_false(self):
        assert is_off_topic("") is False

    def test_outage_not_off_topic(self):
        assert is_off_topic("انقطاع التيار في حينا") is False


class TestConfidenceScoring:

    def test_emergency_positive_confidence(self):
        r = classify_intent("رقم الطوارئ")
        assert r.confidence > 0.0

    def test_unknown_falls_back_to_rag(self):
        r = classify_intent("سؤال غامض xyz123 لا يوجد له تصنيف واضح")
        assert r.answer_mode == "rag"

    def test_empty_string_unknown(self):
        r = classify_intent("")
        assert r.intent_code == "unknown"
        assert r.confidence  == 0.0

    def test_confidence_between_0_and_1(self):
        for q in ["فاتورة", "عداد", "شكوى", "انقطاع", "اشتراك"]:
            r = classify_intent(q)
            assert 0.0 <= r.confidence <= 1.0, f"confidence خارج النطاق لـ: {q}"

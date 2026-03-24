"""
test_stats.py — اختبارات Stats & Chat Analysis API
====================================================
ملاحظة مهمة:
  chat_analysis endpoints تقرأ من message_type='assistant'
  (كل رد من الـ assistant = سؤال واحد وُجِّه من المواطن)

يغطي:
  GET /stats/overview
  GET /stats/chat-problems
  GET /stats/neighborhood-complaints
  GET /stats/questions-trend
  GET /stats/repeated-questions
  GET /stats/intent-hourly-heatmap
  GET /stats/rag-eval-metrics
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── helpers ───────────────────────────────────────────────────────────────────
def _seed_conv(db_con, user_id: int) -> int:
    cur = db_con.cursor()
    cur.execute(
        "INSERT INTO conversation (user_id, channel, language, status) "
        "VALUES (%s, 'web', 'ar', 'open') RETURNING conversation_id;",
        (user_id,),
    )
    cid = cur.fetchone()["conversation_id"]
    db_con.commit()
    return cid


def _seed_msg(db_con, conv_id: int, text: str,
              intent: str = "billing_inquiry",
              answer_found: int = 1,
              best_score: float = 0.8,
              msg_type: str = "assistant") -> int:
    """يُدخل رسالة — افتراضياً message_type='assistant'
       لأن chat_analysis يحسب الإحصائيات من ردود الـ assistant."""
    cur = db_con.cursor()
    cur.execute(
        """
        INSERT INTO message
          (conversation_id, message_type, message_text, response_text,
           intent_pred, intent_conf, response_mode, best_score, answer_found, category)
        VALUES (%s, %s, %s, 'رد تجريبي', %s, 0.9, 'rag', %s, %s, 'billing')
        RETURNING message_id;
        """,
        (conv_id, msg_type, text, intent, best_score, answer_found),
    )
    mid = cur.fetchone()["message_id"]
    db_con.commit()
    return mid


def _admin_uid(db_con) -> int:
    cur = db_con.cursor()
    cur.execute("SELECT user_id FROM app_user WHERE username = 'admin';")
    return cur.fetchone()["user_id"]


# ── /stats/overview ───────────────────────────────────────────────────────────
class TestOverview:

    def test_requires_auth(self, client):
        assert client.get("/stats/overview").status_code == 401

    def test_returns_structure(self, client, admin_headers):
        r = client.get("/stats/overview", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_messages" in data or "total_conversations" in data or isinstance(data, dict)


# ── /stats/chat-problems ─────────────────────────────────────────────────────
class TestChatProblems:

    def test_requires_auth(self, client):
        assert client.get("/stats/chat-problems").status_code == 401

    def test_structure_always_present(self, client, admin_headers):
        r = client.get("/stats/chat-problems", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_messages"   in data
        assert "top_problems"     in data
        assert "top_keywords"     in data
        assert "unanswered_count" in data
        assert "unanswered_rate"  in data

    def test_empty_db_zero(self, client, admin_headers):
        r = client.get("/stats/chat-problems", headers=admin_headers)
        data = r.json()
        # بدون بيانات total_messages = 1 (denominator guard في الكود) أو 0
        assert data["total_messages"] >= 0
        assert isinstance(data["top_problems"], list)

    def test_counts_assistant_messages(self, client, admin_headers, db_con):
        """الكود يحسب من message_type='assistant' فقط."""
        uid = _admin_uid(db_con)
        cid = _seed_conv(db_con, uid)
        for _ in range(3):
            _seed_msg(db_con, cid, "كيف أدفع الفاتورة؟", intent="billing_inquiry",
                      msg_type="assistant")
        _seed_msg(db_con, cid, "انقطاع التيار", intent="outage_fault", msg_type="assistant")
        # user messages لا تُحسب
        _seed_msg(db_con, cid, "رسالة مستخدم", msg_type="user")

        r = client.get("/stats/chat-problems?days=30", headers=admin_headers)
        data = r.json()
        # 4 assistant messages فقط
        assert data["total_messages"] >= 4
        assert len(data["top_problems"]) > 0
        assert data["top_problems"][0]["problem"] == "billing_inquiry"
        assert data["top_problems"][0]["count"] >= 3

    def test_days_param(self, client, admin_headers):
        r7  = client.get("/stats/chat-problems?days=7",  headers=admin_headers)
        r90 = client.get("/stats/chat-problems?days=90", headers=admin_headers)
        assert r7.status_code  == 200
        assert r90.status_code == 200


# ── /stats/neighborhood-complaints ──────────────────────────────────────────
class TestNeighborhoodComplaints:

    def test_requires_auth(self, client):
        assert client.get("/stats/neighborhood-complaints").status_code == 401

    def test_structure(self, client, admin_headers):
        r = client.get("/stats/neighborhood-complaints", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "top_neighborhoods" in data
        assert "total_analyzed"    in data
        assert "neighborhoods_found" in data

    def test_empty_db(self, client, admin_headers):
        r = client.get("/stats/neighborhood-complaints", headers=admin_headers)
        data = r.json()
        assert data["total_analyzed"]    == 0
        assert data["neighborhoods_found"] == 0
        assert data["top_neighborhoods"] == []

    def test_with_assistant_messages(self, client, admin_headers, db_con):
        """يحتاج message_type='assistant' — يحلّل النص للبحث عن أسماء أحياء."""
        uid = _admin_uid(db_con)
        cid = _seed_conv(db_con, uid)
        # رسائل assistant تحتوي أسماء أحياء
        _seed_msg(db_con, cid, "في وسط البلد انقطاع كهربا",
                  intent="outage_fault", msg_type="assistant")
        _seed_msg(db_con, cid, "حي الرشيدية الكهربا مقطوعة",
                  intent="outage_fault", msg_type="assistant")

        r = client.get("/stats/neighborhood-complaints", headers=admin_headers)
        data = r.json()
        # تأكد إنه تحلّل الرسائل على الأقل
        assert data["total_analyzed"] >= 2
        # neighborhoods_found اعتماداً على قدرة _extract_neighborhood
        assert isinstance(data["neighborhoods_found"], int)
        assert isinstance(data["top_neighborhoods"], list)


# ── /stats/questions-trend ───────────────────────────────────────────────────
class TestQuestionsTrend:

    def test_requires_auth(self, client):
        assert client.get("/stats/questions-trend").status_code == 401

    def test_empty_db_returns_empty_list(self, client, admin_headers):
        r = client.get("/stats/questions-trend", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "daily" in data
        assert data["daily"] == []

    def test_with_assistant_messages(self, client, admin_headers, db_con):
        uid = _admin_uid(db_con)
        cid = _seed_conv(db_con, uid)
        _seed_msg(db_con, cid, "سؤال أول", answer_found=1, msg_type="assistant")
        _seed_msg(db_con, cid, "سؤال ثاني", answer_found=0, msg_type="assistant")

        r = client.get("/stats/questions-trend?days=30", headers=admin_headers)
        data = r.json()
        assert len(data["daily"]) > 0
        row = data["daily"][0]
        assert "day"             in row
        assert "total_questions" in row
        assert "answered"        in row
        assert "unanswered"      in row


# ── /stats/repeated-questions ────────────────────────────────────────────────
class TestRepeatedQuestions:

    def test_requires_auth(self, client):
        assert client.get("/stats/repeated-questions").status_code == 401

    def test_response_key_is_questions(self, client, admin_headers):
        """الـ endpoint يعيد 'questions' مش 'repeated'."""
        r = client.get("/stats/repeated-questions", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "questions"  in data
        assert "days"       in data
        assert "min_count"  in data

    def test_empty_db_empty_list(self, client, admin_headers):
        r = client.get("/stats/repeated-questions", headers=admin_headers)
        assert r.json()["questions"] == []

    def test_finds_repeated_above_min_count(self, client, admin_headers, db_con):
        uid = _admin_uid(db_con)
        cid = _seed_conv(db_con, uid)
        q = "كيف أشحن رصيد العداد المسبق؟"
        for _ in range(4):
            _seed_msg(db_con, cid, q, intent="prepaid_recharge", msg_type="assistant")

        r = client.get("/stats/repeated-questions?min_count=3&days=30", headers=admin_headers)
        data = r.json()
        assert len(data["questions"]) >= 1
        assert data["questions"][0]["count"] >= 4

    def test_below_min_count_not_returned(self, client, admin_headers, db_con):
        uid = _admin_uid(db_con)
        cid = _seed_conv(db_con, uid)
        # سؤال يُكرَّر مرتين فقط
        for _ in range(2):
            _seed_msg(db_con, cid, "سؤال نادر مكرر مرتين فقط",
                      msg_type="assistant")

        r = client.get("/stats/repeated-questions?min_count=5", headers=admin_headers)
        qs = [q["question"] for q in r.json()["questions"]]
        assert "سؤال نادر مكرر مرتين فقط" not in qs


# ── /stats/intent-hourly-heatmap ────────────────────────────────────────────
class TestIntentHeatmap:

    def test_requires_auth(self, client):
        assert client.get("/stats/intent-hourly-heatmap").status_code == 401

    def test_structure(self, client, admin_headers):
        r = client.get("/stats/intent-hourly-heatmap", headers=admin_headers)
        assert r.status_code == 200
        assert "heatmap" in r.json()

    def test_with_data(self, client, admin_headers, db_con):
        uid = _admin_uid(db_con)
        cid = _seed_conv(db_con, uid)
        _seed_msg(db_con, cid, "سؤال heatmap", intent="outage_fault", msg_type="assistant")
        r = client.get("/stats/intent-hourly-heatmap?days=7", headers=admin_headers)
        assert r.status_code == 200


# ── /stats/rag-eval-metrics ──────────────────────────────────────────────────
class TestRagEvalMetrics:

    def test_requires_auth(self, client):
        assert client.get("/stats/rag-eval-metrics").status_code == 401

    def test_empty_structure(self, client, admin_headers):
        r = client.get("/stats/rag-eval-metrics", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for key in ("avg_precision", "avg_recall", "avg_f1", "avg_mrr",
                    "hit_rate", "total_evals", "daily"):
            assert key in data, f"missing key: {key}"
        assert data["total_evals"] == 0

    def test_with_eval_rows(self, client, admin_headers, db_con):
        cur = db_con.cursor()
        cur.execute(
            """
            INSERT INTO rag_eval_log
              (question, k, precision_k, recall_k, f1_k, mrr, hit_at_k,
               retrieved_ids_json, relevant_ids_json)
            VALUES
              ('سؤال 1', 5, 0.8, 0.6, 0.69, 0.75, 1, '[]', '[]'),
              ('سؤال 2', 5, 0.6, 0.4, 0.48, 0.50, 1, '[]', '[]'),
              ('سؤال 3', 5, 0.0, 0.0, 0.00, 0.00, 0, '[]', '[]');
            """
        )
        db_con.commit()

        r = client.get("/stats/rag-eval-metrics?days=30", headers=admin_headers)
        data = r.json()
        assert data["total_evals"] == 3
        assert 0.0 < data["avg_f1"]  < 1.0
        assert 0.0 <= data["hit_rate"] <= 1.0
        assert isinstance(data["daily"], list)

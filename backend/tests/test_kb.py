"""
test_kb.py — اختبارات Knowledge Base API
==========================================
المسارات الفعلية:
  GET    /kb
  POST   /kb         ← KBCreate: {title_ar, content_ar, category?, intent_code?, is_active?}
  PUT    /kb/{kb_id} ← KBCreate
  DELETE /kb/{kb_id}

الصلاحيات: employee/supervisor/admin يقدرون يعملوا كل شيء
(لا يوجد حماية مختلفة بين الـ roles في الـ KB حسب الكود الفعلي)
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── helper ────────────────────────────────────────────────────────────────────
def _create_kb(client, headers, title="سؤال اختبار", content="جواب اختبار", category="billing"):
    r = client.post("/kb", headers=headers, json={
        "title_ar":   title,
        "content_ar": content,
        "category":   category,
        "is_active":  True,
    })
    assert r.status_code == 200, f"create_kb failed: {r.text}"
    return r.json()["kb_id"]


# ── Auth ──────────────────────────────────────────────────────────────────────
class TestKbAuth:

    def test_list_requires_auth(self, client):
        assert client.get("/kb").status_code == 401

    def test_create_requires_auth(self, client):
        r = client.post("/kb", json={"title_ar": "q", "content_ar": "a"})
        assert r.status_code == 401

    def test_delete_requires_auth(self, client):
        assert client.delete("/kb/1").status_code == 401


# ── List ──────────────────────────────────────────────────────────────────────
class TestKbList:

    def test_list_empty_db(self, client, admin_headers):
        r = client.get("/kb", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert r.json() == []

    def test_list_as_employee(self, client, employee_headers):
        r = client.get("/kb", headers=employee_headers)
        assert r.status_code == 200

    def test_list_returns_created_items(self, client, admin_headers):
        _create_kb(client, admin_headers, title="سؤال مرئي في القائمة")
        r = client.get("/kb", headers=admin_headers)
        titles = [i["title_ar"] for i in r.json()]
        assert "سؤال مرئي في القائمة" in titles


# ── Create ────────────────────────────────────────────────────────────────────
class TestKbCreate:

    def test_create_success(self, client, admin_headers):
        r = client.post("/kb", headers=admin_headers, json={
            "title_ar":   "ما هو رقم الطوارئ؟",
            "content_ar": "رقم الطوارئ 133",
            "category":   "emergency",
        })
        assert r.status_code == 200
        data = r.json()
        assert "kb_id" in data
        assert data["title_ar"] == "ما هو رقم الطوارئ؟"
        assert data["is_active"] is True

    def test_create_missing_content_fails(self, client, admin_headers):
        r = client.post("/kb", headers=admin_headers,
                        json={"title_ar": "سؤال بدون محتوى"})
        assert r.status_code in (400, 422)

    def test_create_missing_title_fails(self, client, admin_headers):
        r = client.post("/kb", headers=admin_headers,
                        json={"content_ar": "محتوى بدون عنوان"})
        assert r.status_code in (400, 422)

    def test_create_with_category(self, client, admin_headers):
        r = client.post("/kb", headers=admin_headers, json={
            "title_ar":   "سؤال مصنّف",
            "content_ar": "جواب مصنّف",
            "category":   "technical",
        })
        assert r.status_code == 200
        assert r.json()["category"] == "technical"

    def test_create_inactive(self, client, admin_headers):
        r = client.post("/kb", headers=admin_headers, json={
            "title_ar":   "سؤال غير نشط",
            "content_ar": "جواب",
            "is_active":  False,
        })
        assert r.status_code == 200
        assert r.json()["is_active"] is False


# ── Update ────────────────────────────────────────────────────────────────────
class TestKbUpdate:

    def test_update_content(self, client, admin_headers):
        kid = _create_kb(client, admin_headers, content="جواب قديم")
        r = client.put(f"/kb/{kid}", headers=admin_headers, json={
            "title_ar":   "نفس العنوان",
            "content_ar": "جواب جديد بعد التعديل",
        })
        assert r.status_code == 200
        assert r.json()["content_ar"] == "جواب جديد بعد التعديل"

    def test_update_nonexistent_404(self, client, admin_headers):
        r = client.put("/kb/999999", headers=admin_headers, json={
            "title_ar":   "لا يهم",
            "content_ar": "لا يهم",
        })
        assert r.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────
class TestKbDelete:

    def test_delete_success(self, client, admin_headers):
        kid = _create_kb(client, admin_headers, title="سيُحذف هذا السؤال")
        r = client.delete(f"/kb/{kid}", headers=admin_headers)
        assert r.status_code == 200
        # تأكد الحذف
        titles = [i["title_ar"] for i in client.get("/kb", headers=admin_headers).json()]
        assert "سيُحذف هذا السؤال" not in titles

    def test_delete_nonexistent_404(self, client, admin_headers):
        assert client.delete("/kb/999999", headers=admin_headers).status_code == 404

    def test_delete_then_list_not_found(self, client, admin_headers):
        kid = _create_kb(client, admin_headers, title="سؤال مؤقت")
        client.delete(f"/kb/{kid}", headers=admin_headers)
        r = client.get("/kb", headers=admin_headers)
        ids = [i["kb_id"] for i in r.json()]
        assert kid not in ids


# ── Employee permissions ──────────────────────────────────────────────────────
class TestKbPermissions:

    def test_employee_can_list(self, client, employee_headers):
        assert client.get("/kb", headers=employee_headers).status_code == 200

    def test_employee_can_create(self, client, employee_headers):
        r = client.post("/kb", headers=employee_headers, json={
            "title_ar":   "سؤال من موظف",
            "content_ar": "جواب من موظف",
        })
        assert r.status_code == 200

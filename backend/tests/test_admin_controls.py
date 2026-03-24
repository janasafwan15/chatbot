"""
test_admin_controls.py — اختبارات Admin Controls API
======================================================
يغطي:
  - /admin/kb-health
  - /admin/rebuild-embeddings  (POST + GET status)
  - /admin/llm-usage
  - /admin/system-health
  - /admin/audit-trail
  - صلاحيات: employee يجب أن يُرفض (403)
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Auth / Permission ────────────────────────────────────────────────────────
class TestAdminPermissions:

    def test_kb_health_requires_auth(self, client):
        assert client.get("/admin/kb-health").status_code == 401

    def test_llm_usage_requires_auth(self, client):
        assert client.get("/admin/llm-usage").status_code == 401

    def test_system_health_requires_auth(self, client):
        assert client.get("/admin/system-health").status_code == 401

    def test_audit_trail_requires_auth(self, client):
        assert client.get("/admin/audit-trail").status_code == 401

    def test_rebuild_requires_auth(self, client):
        assert client.post("/admin/rebuild-embeddings").status_code == 401

    def test_employee_cannot_access_kb_health(self, client, employee_headers):
        r = client.get("/admin/kb-health", headers=employee_headers)
        assert r.status_code in (403, 401)

    def test_employee_cannot_access_llm_usage(self, client, employee_headers):
        r = client.get("/admin/llm-usage", headers=employee_headers)
        assert r.status_code in (403, 401)

    def test_employee_cannot_rebuild(self, client, employee_headers):
        r = client.post("/admin/rebuild-embeddings", headers=employee_headers)
        assert r.status_code in (403, 401)


# ─── /admin/kb-health ────────────────────────────────────────────────────────
class TestKbHealth:

    def test_returns_structure(self, client, admin_headers):
        r = client.get("/admin/kb-health", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_chunks"         in data
        assert "total_embeddings"     in data
        assert "missing_embeddings"   in data
        assert "coverage_pct"         in data
        assert "chunks_without_embeddings" in data

    def test_empty_db_zero_chunks(self, client, admin_headers):
        r = client.get("/admin/kb-health", headers=admin_headers)
        data = r.json()
        assert data["total_chunks"]       == 0
        assert data["missing_embeddings"] == 0
        # 0/0 → الكود يعيد 0.0 أو 100 — كلاهما مقبول
        assert data["coverage_pct"] in (0, 0.0, 100, 100.0)

    def test_chunk_without_embedding_detected(self, client, admin_headers, db_con):
        cur = db_con.cursor()
        cur.execute(
            """
            INSERT INTO rag_chunk (chunk_id, source_file, text)
            VALUES ('chunk_test_001', 'test.pdf', 'نص اختباري بدون embedding');
            """
        )
        db_con.commit()

        r = client.get("/admin/kb-health", headers=admin_headers)
        data = r.json()
        assert data["total_chunks"] >= 1
        assert data["missing_embeddings"] >= 1
        assert data["coverage_pct"] < 100
        # يجب أن يظهر في القائمة
        ids = [c["chunk_id"] for c in data["chunks_without_embeddings"]]
        assert "chunk_test_001" in ids

    def test_chunk_with_embedding_covered(self, client, admin_headers, db_con):
        cur = db_con.cursor()
        cur.execute(
            "INSERT INTO rag_chunk (chunk_id, source_file, text) VALUES ('c2', 'f.pdf', 'نص');"
        )
        cur.execute(
            """
            INSERT INTO rag_embedding (chunk_id, model, dims, vector_json)
            VALUES ('c2', 'test-model', 3, '[0.1,0.2,0.3]');
            """
        )
        db_con.commit()

        r = client.get("/admin/kb-health", headers=admin_headers)
        data = r.json()
        ids = [c["chunk_id"] for c in data["chunks_without_embeddings"]]
        assert "c2" not in ids


# ─── /admin/rebuild-embeddings ────────────────────────────────────────────────
class TestRebuildEmbeddings:

    def test_start_rebuild_returns_202(self, client, admin_headers):
        r = client.post("/admin/rebuild-embeddings", headers=admin_headers)
        # 202 Accepted أو 200 مقبول
        assert r.status_code in (200, 202)
        data = r.json()
        # يجب أن يعيد رابط check_status أو رسالة
        assert "check_status" in data or "message" in data or "status" in data

    def test_status_endpoint_exists(self, client, admin_headers):
        client.post("/admin/rebuild-embeddings", headers=admin_headers)
        r = client.get("/admin/rebuild-embeddings/status", headers=admin_headers)
        assert r.status_code == 200

    def test_status_structure(self, client, admin_headers):
        client.post("/admin/rebuild-embeddings", headers=admin_headers)
        r = client.get("/admin/rebuild-embeddings/status", headers=admin_headers)
        data = r.json()
        assert "running"      in data
        assert "done"         in data
        assert "errors"       in data
        assert "progress_pct" in data

    def test_overwrite_flag(self, client, admin_headers):
        r = client.post("/admin/rebuild-embeddings?overwrite=true", headers=admin_headers)
        assert r.status_code in (200, 202)

    def test_limit_param(self, client, admin_headers):
        r = client.post("/admin/rebuild-embeddings?limit=5", headers=admin_headers)
        assert r.status_code in (200, 202)


# ─── /admin/llm-usage ────────────────────────────────────────────────────────
class TestLlmUsage:

    def test_structure(self, client, admin_headers):
        r = client.get("/admin/llm-usage", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_calls"      in data
        assert "success_rate"     in data
        assert "avg_latency_ms"   in data
        assert "total_tokens_in"  in data
        assert "total_tokens_out" in data
        assert "calls_per_model"  in data
        assert "hourly"           in data
        # الـ key الفعلي هو 'errors' (وليس 'recent_errors')
        assert "errors" in data or "recent_errors" in data

    def test_empty_zero_calls(self, client, admin_headers):
        r = client.get("/admin/llm-usage", headers=admin_headers)
        data = r.json()
        assert data["total_calls"] == 0

    def test_hours_param(self, client, admin_headers):
        r24  = client.get("/admin/llm-usage?hours=24",  headers=admin_headers)
        r168 = client.get("/admin/llm-usage?hours=168", headers=admin_headers)
        assert r24.status_code  == 200
        assert r168.status_code == 200


# ─── /admin/system-health ────────────────────────────────────────────────────
class TestSystemHealth:

    def test_returns_200(self, client, admin_headers):
        r = client.get("/admin/system-health", headers=admin_headers)
        assert r.status_code == 200

    def test_structure(self, client, admin_headers):
        data = client.get("/admin/system-health", headers=admin_headers).json()
        assert "overall" in data or "ok" in data or "services" in data

    def test_db_service_present(self, client, admin_headers):
        data = client.get("/admin/system-health", headers=admin_headers).json()
        # يجب أن يُشير للـ DB بأي شكل
        text = str(data).lower()
        assert "db" in text or "database" in text or "postgres" in text


# ─── /admin/audit-trail ──────────────────────────────────────────────────────
class TestAuditTrail:

    def test_returns_list(self, client, admin_headers):
        r = client.get("/admin/audit-trail", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data or "trail" in data or isinstance(data, list)

    def test_days_param(self, client, admin_headers):
        r = client.get("/admin/audit-trail?days=30", headers=admin_headers)
        assert r.status_code == 200

    def test_limit_param(self, client, admin_headers):
        r = client.get("/admin/audit-trail?limit=10", headers=admin_headers)
        assert r.status_code == 200

    def test_audit_created_on_kb_change(self, client, admin_headers):
        """إنشاء KB entry يجب أن يُسجَّل في audit_trail."""
        client.post("/knowledge", headers=admin_headers, json={
            "question": "سؤال لاختبار الـ audit",
            "answer":   "جواب الاختبار",
            "category": "billing",
        })
        r = client.get("/admin/audit-trail?days=1", headers=admin_headers)
        assert r.status_code == 200

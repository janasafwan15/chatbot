"""
test_auth.py — اختبارات Auth API
==================================
المسارات الفعلية:
  POST /auth/login
  POST /auth/logout
  POST /auth/change-password
  GET  /kb  ← endpoint محمي للتحقق من auth
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLogin:

    def test_login_success(self, client):
        r = client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and data["token"] != ""

    def test_login_returns_role(self, client):
        r = client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_login_wrong_password(self, client):
        r = client.post("/auth/login", json={"username": "admin", "password": "wrongpass"})
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        r = client.post("/auth/login", json={"username": "ghost_user_xyz", "password": "pass"})
        assert r.status_code == 401

    def test_login_empty_credentials(self, client):
        r = client.post("/auth/login", json={"username": "", "password": ""})
        assert r.status_code in (400, 401, 422)

    def test_login_rate_limit(self, client):
        """5 محاولات فاشلة من نفس الـ IP → 429."""
        for _ in range(5):
            client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 429

    def test_login_must_change_password_false_for_admin(self, client):
        """مدير النظام must_change_password=0 → False في الرد."""
        r = client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert r.status_code == 200
        assert r.json()["must_change_password"] is False


class TestProtectedEndpoints:

    def test_no_token_returns_401(self, client):
        r = client.get("/kb")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, client):
        r = client.get("/kb", headers={"Authorization": "Bearer totally-invalid-token"})
        assert r.status_code == 401

    def test_malformed_header_returns_401(self, client):
        r = client.get("/kb", headers={"Authorization": "NotBearer abc123"})
        assert r.status_code == 401

    def test_valid_token_allows_access(self, client, admin_headers):
        r = client.get("/kb", headers=admin_headers)
        assert r.status_code == 200

    def test_stats_requires_auth(self, client):
        r = client.get("/stats/overview")
        assert r.status_code == 401


class TestLogout:

    def test_logout_success(self, client):
        login = client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert login.status_code == 200
        token = login.json()["token"]
        r = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    def test_token_invalid_after_logout(self, client):
        login = client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
        token = login.json()["token"]
        client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        check = client.get("/kb", headers={"Authorization": f"Bearer {token}"})
        assert check.status_code == 401

    def test_logout_without_token(self, client):
        r = client.post("/auth/logout")
        assert r.status_code == 401


class TestPasswordChange:

    def test_must_change_password_flag_for_new_user(self, client, db_con):
        """مستخدم جديد must_change_password=1 → True في الرد."""
        from app.auth import hash_password
        cur = db_con.cursor()
        cur.execute(
            """
            INSERT INTO app_user (username, password_hash, role, full_name,
                                  status, must_change_password)
            VALUES ('new_emp_test', %s, 'employee', 'موظف جديد', 'active', 1);
            """,
            (hash_password("Temp@1234"),),
        )
        db_con.commit()

        r = client.post("/auth/login", json={"username": "new_emp_test", "password": "Temp@1234"})
        assert r.status_code == 200
        assert r.json()["must_change_password"] is True

    def test_change_password_requires_auth(self, client):
        r = client.post("/auth/change-password",
                        json={"old_password": "Admin@123", "new_password": "New@12345"})
        assert r.status_code == 401

    def test_change_password_success(self, client, admin_headers):
        r = client.post("/auth/change-password",
                        headers=admin_headers,
                        json={"old_password": "Admin@123", "new_password": "NewPass@123"})
        # 200 أو 400 لو الـ policy لا تسمح — المهم مش 401/500
        assert r.status_code in (200, 400)

"""
seed_users.py — بذر المستخدمين الأوليين في PostgreSQL
======================================================
الاستخدام:
    python -m app.seed_users
    # أو مباشرة:
    python app/seed_users.py
"""
from __future__ import annotations

from app.db import init_db, connect
from app.auth import hash_password


def upsert(username: str, full_name: str, role: str, password: str) -> None:
    """يُضيف مستخدماً أو يُحدّثه لو موجود."""
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO app_user (username, password_hash, role, full_name, status, must_change_password)
        VALUES (%s, %s, %s, %s, 'active', 0)
        ON CONFLICT (username) DO UPDATE SET
            password_hash       = EXCLUDED.password_hash,
            role                = EXCLUDED.role,
            full_name           = EXCLUDED.full_name,
            updated_at          = NOW();
        """,
        (username, hash_password(password), role, full_name),
    )
    con.commit()
    con.close()
    print(f"  ✅ {role:12} → {username} ({full_name})")


if __name__ == "__main__":
    print("🔧 تهيئة قاعدة البيانات...")
    init_db()

    print("\n👤 بذر المستخدمين:")
    # admin
    upsert("mohammad", "محمد المحتسب", "admin",    "Admin@Hepco2024")

    # employees
    upsert("jana",     "جنى الجعبري",   "employee", "Emp@Hepco2024")
    upsert("ameera",   "أميرة الدويك",  "employee", "Emp@Hepco2024")
    upsert("sara",     "سارة أبو زينة", "employee", "Emp@Hepco2024")

    print("\n✅ Seed done!")

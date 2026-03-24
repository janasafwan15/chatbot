from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from .db import init_db, connect, execute_returning
from .auth import hash_password


def ensure_department(code: str, name_ar: str) -> int:
    con = connect()
    try:
        cur = con.cursor()

        cur.execute(
            "SELECT department_id FROM department WHERE department_code=%s",
            (code,),
        )
        r = cur.fetchone()
        if r:
            return int(r["department_id"])

        dept_id = execute_returning(
            cur,
            """
            INSERT INTO department (department_code, name_ar, is_active)
            VALUES (%s, %s, 1)
            RETURNING department_id
            """,
            (code, name_ar),
        )
        con.commit()
        return int(dept_id)
    finally:
        con.close()


def upsert_user(username: str, full_name: str, role: str, password_plain: str, dept_id: int | None):
    con = connect()
    try:
        cur = con.cursor()

        cur.execute(
            "SELECT user_id FROM app_user WHERE username=%s",
            (username,),
        )
        r = cur.fetchone()

        if r:
            cur.execute(
                """
                UPDATE app_user
                SET password_hash=%s,
                    role=%s,
                    full_name=%s,
                    department_id=%s,
                    status='active',
                    updated_at=NOW()
                WHERE username=%s
                """,
                (hash_password(password_plain), role, full_name, dept_id, username),
            )
            con.commit()
            return

        cur.execute(
            """
            INSERT INTO app_user (
                username, password_hash, role, full_name, department_id, status
            )
            VALUES (%s, %s, %s, %s, %s, 'active')
            """,
            (username, hash_password(password_plain), role, full_name, dept_id),
        )
        con.commit()
    finally:
        con.close()


def run_seed():
    init_db()
    dept = ensure_department("CS", "خدمة العملاء")

    upsert_user("mohammad", "محمد المحتسب", "admin", "admin123", dept)
    upsert_user("jana", "جنى الجعبري", "employee", "emp123", dept)
    upsert_user("ameera", "أميرة الدويك", "employee", "emp123", dept)
    upsert_user("sara", "سارة أبو زينة", "employee", "emp123", dept)


if __name__ == "__main__":
    run_seed()
    print("Seed done ✅")
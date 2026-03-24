#!/usr/bin/env python3
"""
scripts/init_db.py — تهيئة قاعدة البيانات من الصفر
======================================================
الاستخدام:
    python scripts/init_db.py              # schema فقط
    python scripts/init_db.py --seed       # schema + مستخدمين أوليين
    python scripts/init_db.py --seed --drop # احذف كل شيء ثم أعد البناء (خطر!)

متغيرات البيئة المطلوبة (.env):
    DATABASE_URL=postgresql://hepco:hepco_secret@localhost:5432/hepco_db
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def create_schema() -> None:
    from app.db import init_db
    from app.rag_metrics import ensure_eval_table
    print("🔧 Creating schema...")
    init_db()
    ensure_eval_table()
    print("✅ Schema ready.")


def seed_users() -> None:
    from app.seed_users import upsert
    print("\n👤 Seeding users...")
    upsert("admin",   "مدير النظام",    "admin",    "Admin@Hepco2024")
    upsert("jana",    "جنى الجعبري",    "employee", "Emp@Hepco2024")
    upsert("ameera",  "أميرة الدويك",   "employee", "Emp@Hepco2024")
    upsert("sara",    "سارة أبو زينة",  "employee", "Emp@Hepco2024")
    print("✅ Users seeded.")


def drop_all() -> None:
    from app.db import connect
    DROP_ORDER = [
        "rag_eval_log", "feedback", "message", "conversation_state",
        "conversation", "user_session", "kb_changelog", "rag_embedding",
        "rag_chunk_fts", "rag_chunk", "knowledge_base", "user_specialization",
        "employee_specialization", "app_user", "intent", "department",
        "audit_trail", "system_log", "configuration",
    ]
    con = connect()
    cur = con.cursor()
    print("⚠️  Dropping all tables...")
    for tbl in DROP_ORDER:
        try:
            cur.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE;')
        except Exception as e:
            print(f"  Warning dropping {tbl}: {e}")
    con.commit()
    con.close()
    print("✅ All tables dropped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HEPCO DB Init")
    parser.add_argument("--seed", action="store_true", help="بذر المستخدمين الأوليين")
    parser.add_argument("--drop", action="store_true", help="احذف كل الجداول أولاً (خطر!)")
    args = parser.parse_args()

    if args.drop:
        confirm = input("⚠️  هذا سيحذف كل البيانات. اكتب 'yes' للمتابعة: ").strip()
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)
        drop_all()

    create_schema()

    if args.seed:
        seed_users()

    print("\n🚀 Database ready!")

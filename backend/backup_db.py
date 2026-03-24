#!/usr/bin/env python3
"""
backup_db.py — نسخ احتياطي تلقائي لقاعدة بيانات PostgreSQL
=============================================================
الاستخدام:
    python backup_db.py                        # نسخة واحدة الآن
    python backup_db.py --keep 7               # احتفظ بآخر 7 نسخ (افتراضي)
    python backup_db.py --dest /my/path        # مجلد مخصص للنسخ
    python backup_db.py --format plain         # SQL نصي بدل custom
    python backup_db.py --restore backups/hepco_20250101_020000.dump

cron (كل يوم الساعة 2 صباحاً):
    0 2 * * * cd /path/to/backend && python backup_db.py >> logs/backup.log 2>&1

متغيرات البيئة المستخدمة (من .env):
    DATABASE_URL = postgresql://user:pass@host:5432/dbname
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://hepco:hepco_secret@localhost:5432/hepco_db",
)
BACKUP_DIR = Path(__file__).resolve().parent / "backups"


def _parse_dsn(url: str) -> dict:
    p = urlparse(url)
    return {
        "host":     p.hostname or "localhost",
        "port":     str(p.port or 5432),
        "user":     p.username or "hepco",
        "password": p.password or "",
        "dbname":   (p.path or "/hepco_db").lstrip("/"),
    }


def backup(dest_dir: Path, keep: int, fmt: str = "custom") -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)

    dsn  = _parse_dsn(DATABASE_URL)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext  = "sql" if fmt == "plain" else "dump"
    dest = dest_dir / f"hepco_{ts}.{ext}"
    pg_fmt = "plain" if fmt == "plain" else "custom"

    env = {**os.environ, "PGPASSWORD": dsn["password"]}
    cmd = [
        "pg_dump",
        "-h", dsn["host"],
        "-p", dsn["port"],
        "-U", dsn["user"],
        "-d", dsn["dbname"],
        "-F", pg_fmt,
        "--no-password",
        "-f", str(dest),
    ]

    print(f"[backup] 🚀 pg_dump → {dest.name} ...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[backup] ❌ pg_dump failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_kb = dest.stat().st_size // 1024
    print(f"[backup] ✅ {dest.name}  ({size_kb} KB)")

    pattern = "hepco_*.sql" if fmt == "plain" else "hepco_*.dump"
    all_backups = sorted(dest_dir.glob(pattern))
    if len(all_backups) > keep:
        for old in all_backups[:-keep]:
            old.unlink()
            print(f"[backup] 🗑️  removed: {old.name}")

    return dest


def restore(backup_file: Path) -> None:
    if not backup_file.exists():
        print(f"[restore] ❌ File not found: {backup_file}", file=sys.stderr)
        sys.exit(1)

    dsn = _parse_dsn(DATABASE_URL)
    env = {**os.environ, "PGPASSWORD": dsn["password"]}

    print(f"[restore] ⚠️  هذا سيُعيد كتابة قاعدة البيانات '{dsn['dbname']}' بالكامل!")
    confirm = input("اكتب 'yes' للمتابعة: ").strip().lower()
    if confirm != "yes":
        print("[restore] ❌ تم الإلغاء.")
        sys.exit(0)

    if backup_file.suffix.lower() == ".sql":
        cmd = ["psql", "-h", dsn["host"], "-p", dsn["port"],
               "-U", dsn["user"], "-d", dsn["dbname"],
               "--no-password", "-f", str(backup_file)]
    else:
        cmd = ["pg_restore", "-h", dsn["host"], "-p", dsn["port"],
               "-U", dsn["user"], "-d", dsn["dbname"],
               "--no-password", "--clean", "--if-exists", str(backup_file)]

    print(f"[restore] 🔄 Restoring from {backup_file.name} ...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[restore] ❌ Restore failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"[restore] ✅ تم الاستعادة بنجاح من {backup_file.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HEPCO DB Backup/Restore (PostgreSQL)")
    parser.add_argument("--dest",    default=str(BACKUP_DIR))
    parser.add_argument("--keep",    default=7, type=int)
    parser.add_argument("--format",  default="custom", choices=["custom", "plain"])
    parser.add_argument("--restore", default=None, metavar="FILE")
    args = parser.parse_args()

    if args.restore:
        restore(Path(args.restore))
    else:
        backup(Path(args.dest), args.keep, args.format)

#!/usr/bin/env bash
# setup.sh — تهيئة المشروع من الصفر على Ubuntu/Debian
# =====================================================
# الاستخدام:
#   chmod +x setup.sh && ./setup.sh
# =====================================================
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Python & pip ──────────────────────────────────────────────────────────
info "فحص Python..."
python3 --version >/dev/null 2>&1 || error "Python 3 غير مثبَّت"
pip3 --version    >/dev/null 2>&1 || error "pip غير مثبَّت"

# ── 2. تثبيت المتطلبات ───────────────────────────────────────────────────────
info "تثبيت المتطلبات..."
pip3 install -r requirements.txt --quiet

# ── 3. ملف .env ──────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    warn ".env غير موجود — نسخ من .env.example"
    cp .env.example .env
    warn "⚠️  عدّل .env وضع كلمات المرور الصحيحة قبل التشغيل!"
fi

# ── 4. PostgreSQL — تحقق من الاتصال ─────────────────────────────────────────
info "فحص الاتصال بـ PostgreSQL..."
source .env 2>/dev/null || true
DB_URL="${DATABASE_URL:-postgresql://hepco:hepco_secret@localhost:5432/hepco_db}"

python3 -c "
import psycopg2, sys
try:
    psycopg2.connect('$DB_URL').close()
    print('✅ PostgreSQL متاح')
except Exception as e:
    print(f'❌ لا يمكن الاتصال بـ PostgreSQL: {e}')
    print('   تأكد إن PostgreSQL شغّال وإن DATABASE_URL صحيح في .env')
    sys.exit(1)
"

# ── 5. init DB ───────────────────────────────────────────────────────────────
info "تهيئة قاعدة البيانات (schema)..."
python3 -c "
import os, sys
sys.path.insert(0, '.')
from app.db import init_db
from app.rag_metrics import ensure_eval_table
init_db()
ensure_eval_table()
print('✅ Schema جاهز')
"

# ── 6. seed users ────────────────────────────────────────────────────────────
info "بذر المستخدمين الأوليين..."
python3 -m app.seed_users

# ── 7. مجلد logs ─────────────────────────────────────────────────────────────
mkdir -p logs backups
info "✅ مجلدات logs/ و backups/ جاهزة"

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ الإعداد اكتمل — لتشغيل السيرفر:     ${NC}"
echo -e "${GREEN}     uvicorn app.main:app --reload         ${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"

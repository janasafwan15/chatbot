# دليل التشغيل والاختبار — HEPCO Backend

## ⚡ تشغيل سريع (من الصفر)

```bash
# 1. تثبيت
pip install -r requirements.txt

# 2. إعداد البيئة
cp .env.example .env
# عدّل .env (DATABASE_URL وغيرها)

# 3. تهيئة كاملة (schema + seed)
./setup.sh

# 4. تشغيل السيرفر
uvicorn app.main:app --reload
```

---

## 🗄️ PostgreSQL — إعداد يدوي

```bash
# إنشاء المستخدم والقاعدة (كـ postgres)
su -s /bin/bash postgres -c "psql -c \"CREATE ROLE hepco WITH LOGIN PASSWORD 'hepco_secret';\""
su -s /bin/bash postgres -c "psql -c \"CREATE DATABASE hepco_db OWNER hepco;\""

# أو بـ psql مباشرة (لو عندك صلاحيات)
psql -U postgres -c "CREATE ROLE hepco WITH LOGIN PASSWORD 'hepco_secret';"
psql -U postgres -c "CREATE DATABASE hepco_db OWNER hepco;"
```

---

## 🧪 تشغيل الاختبارات

### المتطلبات
```bash
pip install pytest httpx --quiet
```

### إعداد قاعدة بيانات الاختبار (مرة واحدة)
```bash
su -s /bin/bash postgres -c "psql -c \"CREATE DATABASE hepco_test OWNER hepco;\""
```

### تشغيل كل الاختبارات
```bash
TEST_DATABASE_URL=postgresql://hepco:hepco_secret@127.0.0.1:5432/hepco_test \
    python -m pytest -v
```

### نتيجة متوقعة
```
122 passed in ~60s
```

### تشغيل ملف محدد
```bash
# بدون DB (سريعة جداً — 0.3 ثانية)
pytest tests/test_cache.py tests/test_intent.py -v

# مع DB
pytest tests/test_auth.py tests/test_kb.py tests/test_stats.py tests/test_admin_controls.py -v
```

---

## 💾 النسخ الاحتياطي

```bash
# نسخة الآن (custom compressed)
python backup_db.py

# نسخة SQL نصية
python backup_db.py --format plain

# مجلد مخصص + الاحتفاظ بـ 14 نسخة
python backup_db.py --dest /mnt/backup --keep 14

# استعادة
python backup_db.py --restore backups/hepco_20250301_020000.dump

# cron — يومي الساعة 2 صباحاً
# 0 2 * * * cd /opt/hepco/backend && python backup_db.py >> logs/backup.log 2>&1
```

---

## 🔍 الـ Tests — ماذا يُغطّى

| الملف | Tests | يغطي |
|-------|-------|------|
| `test_cache.py` | 10 | LRU cache، confidence threshold، fuzzy match |
| `test_intent.py` | 24 | تصنيف النوايا، off-topic detection، confidence |
| `test_auth.py` | 18 | login/logout، rate-limit، protected endpoints، password |
| `test_kb.py` | 18 | CRUD قاعدة المعرفة، permissions، validation |
| `test_stats.py` | 25 | chat-problems، neighborhoods، RAG metrics، heatmap |
| `test_admin_controls.py` | 27 | kb-health، rebuild، llm-usage، system-health، audit |
| **المجموع** | **122** | **100% passed ✅** |

# HEPCO — Hebron Electricity RAG Backend

نظام دعم مواطني كهرباء الخليل — FastAPI + PostgreSQL + Ollama + Qdrant

---

## 🚀 تشغيل المشروع من الصفر

### 1. المتطلبات
```
Python 3.11+
PostgreSQL 14+
Ollama (للـ LLM والـ embeddings)
Qdrant (اختياري — لـ vector search)
```

### 2. تثبيت الحزم
```bash
pip install -r requirements.txt
```

### 3. ملف البيئة
```bash
cp .env.example .env
# عدّل القيم حسب بيئتك
```

محتوى `.env`:
```env
DATABASE_URL=postgresql://hepco:hepco_secret@localhost:5432/hepco_db
SECRET_KEY=your-very-secret-key-change-this
OLLAMA_BASE=http://localhost:11434
EMBED_BASE=http://localhost:11434
EMBED_MODEL=bge-m3
LLM_MODEL=qwen2.5:7b
QDRANT_URL=http://localhost:6333
```

### 4. إنشاء قاعدة البيانات
```bash
# أنشئ الـ user والـ database في PostgreSQL
psql -U postgres -c "CREATE ROLE hepco WITH LOGIN PASSWORD 'hepco_secret';"
psql -U postgres -c "CREATE DATABASE hepco_db OWNER hepco;"

# تهيئة الـ schema + بذر المستخدمين
python scripts/init_db.py --seed
```

### 5. تشغيل الـ server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

الـ API متاح على: http://localhost:8000

---

## 🧪 تشغيل الاختبارات

### إعداد قاعدة بيانات الاختبار (مرة واحدة)
```bash
psql -U postgres -c "CREATE DATABASE hepco_test OWNER hepco;"
```

### تثبيت حزم الاختبار
```bash
pip install -r requirements-test.txt
```

### تشغيل كل الاختبارات
```bash
TEST_DATABASE_URL=postgresql://hepco:hepco_secret@127.0.0.1:5432/hepco_test \
    python -m pytest -v
```

### نتائج متوقعة
```
122 passed in ~65s
```

---

## 💾 النسخ الاحتياطي

```bash
# نسخة يومية
python backup_db.py --keep 7

# استعادة
python backup_db.py --restore backups/hepco_20250101_020000.dump
```

cron (يومياً الساعة 2 صباحاً):
```
0 2 * * * cd /opt/hepco/backend && python backup_db.py >> logs/backup.log 2>&1
```

---

## 🐳 Docker

```bash
docker-compose up -d
```

---

## 📁 هيكل المشروع

```
backend/
├── app/
│   ├── main.py              # FastAPI app + auth routes + KB routes
│   ├── db.py                # PostgreSQL connection pool
│   ├── auth.py              # JWT sessions + password hashing
│   ├── schemas.py           # Pydantic models
│   ├── rag_engine.py        # RAG pipeline
│   ├── rag_api.py           # RAG endpoints
│   ├── rag_metrics.py       # RAG evaluation (precision/recall/F1/MRR)
│   ├── stats_api.py         # Statistics endpoints
│   ├── chat_analysis_api.py # Chat history analysis
│   ├── admin_controls_api.py# Admin: rebuild embeddings, LLM usage, health
│   ├── intent_classifier.py # Arabic intent classification
│   ├── answer_cache.py      # LRU answer cache
│   ├── logging_config.py    # Professional 4-file logging system
│   └── seed_users.py        # Initial users seed
├── scripts/
│   └── init_db.py           # Schema creation + seeding
├── tests/
│   ├── conftest.py          # Pytest fixtures (PostgreSQL)
│   ├── test_auth.py         # Auth API tests (18 tests)
│   ├── test_kb.py           # Knowledge Base tests (18 tests)
│   ├── test_cache.py        # Answer Cache tests (10 tests)
│   ├── test_intent.py       # Intent Classifier tests (24 tests)
│   ├── test_stats.py        # Stats & Chat Analysis tests (25 tests)
│   └── test_admin_controls.py # Admin Controls tests (27 tests)
├── requirements.txt         # Production dependencies
├── requirements-test.txt    # Test-only dependencies
├── backup_db.py             # PostgreSQL backup/restore
└── pytest.ini               # Test configuration
```

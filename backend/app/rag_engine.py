from __future__ import annotations

import json
import logging
import os
import re
import time as _time

# ── Structured JSON Logger ──────────────────────────────────
import logging.config

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "logging.Formatter",
            "fmt": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
        "plain": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "level": _LOG_LEVEL,
        },
    },
    "root": {"level": _LOG_LEVEL, "handlers": ["console"]},
})

logger = logging.getLogger(__name__)
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .db import connect
from .ollama_client import post_json, get_ok
from .rerank import rerank
from .vector_store import retrieve_mmr
from .hybrid_retrieve import retrieve_hybrid
from .qdrant_client import qdrant_enabled
from .intent_classifier import classify_intent, is_off_topic, OFF_TOPIC_REPLY, IntentResult
from .answer_cache import get_answer_cache
from .dialect_normalizer import normalize_dialect
# =============================
# Config
# =============================

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = BASE_DIR / "rag_index.json"

# ---- LLM (Ollama Cloud) ----
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v3.1:671b-cloud").strip()
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

# ---- Embeddings (Ollama ONLY) ----
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "ollama").lower().strip()
if EMBED_PROVIDER and EMBED_PROVIDER != "ollama":
    raise RuntimeError("This project is configured for EMBED_PROVIDER=ollama only.")

EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3").strip()

EMBED_BASE = os.getenv("EMBED_BASE", "").strip().rstrip("/")
if not EMBED_BASE:
    EMBED_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")

EMBED_API_KEY = os.getenv("EMBED_API_KEY", os.getenv("OLLAMA_API_KEY", "")).strip()
EMBED_TIMEOUT = int(os.getenv("EMBED_TIMEOUT", "30"))
MAX_EMBED_CHARS = int(os.getenv("MAX_EMBED_CHARS", "1800"))

# Retrieval
TOP_K = int(os.getenv("RAG_TOP_K", "10"))
RERANK_TOP_N = int(os.getenv("RAG_RERANK_TOP_N", "5"))   # رُفع من 3 → 5
MIN_SIM = float(os.getenv("RAG_MIN_SIM", "0.30"))         # رُفع من 0.22 → 0.30

# Confidence
LOW_CONF = float(os.getenv("RAG_LOW_CONF", "0.38"))       # رُفع من 0.28 → 0.38

# Context
CONTEXT_K = int(os.getenv("RAG_CONTEXT_K", "6"))
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))

# Contact (fallback only)
SUPPORT_PHONE = os.getenv("SUPPORT_PHONE", "2292820")

SYSTEM_PROMPT = """
[CRITICAL INSTRUCTION] You MUST respond in Arabic only. Any response in English, Chinese, or any other language is strictly forbidden. Arabic only — no exceptions.

أنت مساعد دعم ذكي متخصص لشركة كهرباء الخليل (HEPCO). مهمتك الوحيدة: مساعدة المواطنين في كل ما يتعلق بخدمات الكهرباء.

══════════════════════════════════
قواعد الدقة — احترافها إلزامي
══════════════════════════════════
1. اعتمد حصراً على [المعلومات] المرفقة أدناه. لا تضِف أي معلومة غير موجودة فيها.
2. لا تخترع: أرقاماً هاتفية، تعرفة، رسوماً، مدداً زمنية، أو أسماء موظفين.
3. إذا غابت المعلومة — قُل ذلك صراحةً واقترح التواصل المباشر.
4. لا تكرر السؤال داخل الجواب.
5. الأرقام الهاتفية: استخدم فقط ما في [المعلومات] أو رقم الطوارئ 133.

══════════════════════════════════
فهم اللهجة الفلسطينية — إلزامي
══════════════════════════════════
السؤال قد يصلك بعد تطبيع لهجوي. تنبّه لهذه المعاني:
• "وقع في الماء / امتلى ماء / تبلّل" = الكرت تعرّض للماء → أجب عن كرت بدل تالف
• "باظ / خربان / خربت" = تعطّل أو تلف
• "طبت / طاب فيه شي" = وقع فيه شيء / سقط في شيء
• "ضاع / ضايع" = مفقود → أجب عن كرت بدل فاقد
• "مي / مايه / مويه / بركة" = ماء
✗ لا تفسّر "امتلى/امتلأ" على أنه امتلاء ذاكرة الكرت إذا كان السياق يشير للماء أو التلف.
✗ لا تفسّر "البلدية فاتحة؟" على أنه سؤال عن التطبيق — هو سؤال عن ساعات الدوام.

══════════════════════════════════
أسلوب الرد — حسب نوع السؤال
══════════════════════════════════
• مشكلة تقنية (عطل، انقطاع، قاطع):
  → ابدأ بـ "الأسباب الشائعة:" ثم قائمة
  → ثم "الخطوات:" مرقمة وواضحة
  → اختم بـ "إذا استمرت المشكلة: تواصل معنا"

• سؤال إجرائي (اشتراك، تحويل، شكوى):
  → "المستندات المطلوبة:" ثم قائمة (إن وجدت)
  → "خطوات التقديم:" مرقمة
  → "المدة المتوقعة:" (من المعلومات فقط)

• استعلام عن رقم/تواصل:
  → جواب قصير مباشر — رقم فقط بدون مقدمة طويلة

• أسئلة عامة:
  → فقرة واحدة واضحة، 3-5 جمل كحد أقصى

══════════════════════════════════
محظورات — لا تفعل أبداً
══════════════════════════════════
✗ لا تبدأ بـ: "بالتأكيد"، "يسعدني"، "بكل سرور"، "وبالطبع"
✗ لا تذكر: "مصدر"، "المصادر"، "وفقاً للمعلومات المرفقة"، "كمساعد ذكاء"
✗ لا تعطِ وعوداً بخدمات غير مذكورة في المعلومات
✗ لا تجب على أسئلة خارج نطاق الكهرباء
✗ لا تستخدم تاريخ اليوم للإجابة عن أسئلة الدوام — استخدم المعلومات الثابتة فقط

══════════════════════════════════
السياق والمحادثة
══════════════════════════════════
- لو في تاريخ محادثة، اربط جوابك بالسياق طبيعياً.
- لو المواطن يسأل عن تفصيل من جواب سابق، اشرحه مباشرة.
- اللغة: عربي فصيح مع لهجة محلية مقبولة حسب السياق.
""".strip()



# =============================
# Health checks
# =============================

def ping_ollama() -> bool:
    return get_ok("/api/tags", timeout=10)

def ping_embeddings() -> bool:
    # ✅ #6: use ollama_client constants — single source of truth
    from .ollama_client import EMBED_BASE as _EMBED_BASE, EMBED_API_KEY as _EMBED_API_KEY
    try:
        headers = {"Content-Type": "application/json"}
        if _EMBED_API_KEY:
            headers["Authorization"] = f"Bearer {_EMBED_API_KEY}"
        r = requests.get(f"{_EMBED_BASE}/api/tags", headers=headers, timeout=10)
        return bool(r.ok)
    except Exception:
        return False


# =============================
# Normalization
# =============================

AR_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
AR_PUNCT = re.compile(r"[^\w\s\u0600-\u06FF]")
AR_NUMS_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

PHRASE_NORMALIZE: list[tuple[str, str]] = [
    ("فاتورتي", "فاتوره"),
    ("الفاتوره", "فاتوره"),
    ("فاتورة", "فاتوره"),
    ("فواتير", "فاتوره"),
    ("غاليه", "عاليه"),
    ("غالية", "عاليه"),
    ("مرتفعة", "عاليه"),
    ("مرتفعه", "عاليه"),
    ("محرقة", "عاليه"),
    ("نار", "عاليه"),
    ("الطوترئ", "الطوارئ"),
    ("الطواري", "الطوارئ"),
    ("الطوارى", "الطوارئ"),
    ("طوارىء", "طوارئ"),
    ("طواريء", "طوارئ"),
    ("طوارئ", "الطوارئ"),
    ("رقم طوارئ", "رقم الطوارئ"),
    ("1 فاز", "احادي الفاز"),
    ("١ فاز", "احادي الفاز"),
    ("فاز واحد", "احادي الفاز"),
    ("3 فاز", "ثلاثي الفاز"),
    ("3 فازات", "ثلاثي الفاز"),
    ("٣ فاز", "ثلاثي الفاز"),
    ("ثلاث فازات", "ثلاثي الفاز"),
    ("ثلاثة فازات", "ثلاثي الفاز"),
    ("ترقيه الخدمه", "ترقيه خدمه"),
    ("ترقية الخدمة", "ترقيه خدمه"),
    ("العداد بفصل", "قاطع عداد"),
    ("العداد يفصل", "قاطع عداد"),
    ("بفصل الكهربا", "قاطع عداد"),
    ("يفصل الكهربا", "قاطع عداد"),
    ("الكهربا بتقطع", "انقطاع كهرباء"),
    ("الكهرباء تنقطع", "انقطاع كهرباء"),
    ("كهربا مقطوعه", "انقطاع كهرباء"),
    ("مافي كهربا", "انقطاع كهرباء"),
    ("شحن العداد", "شحن رصيد عداد"),
    ("شحن الكود", "شحن رصيد عداد"),
    ("رصيد العداد", "رصيد عداد مسبق الدفع"),
    ("اشتراك جديد", "طلب اشتراك كهرباء"),
    ("توصيل كهربا", "طلب اشتراك كهرباء"),
    ("دفع الفاتوره", "سداد فاتوره"),
    ("دفع الفواتير", "سداد فاتوره"),
    # ── اللهجة الفلسطينية: ماء وتلف الكرت ──────────────────
    ("مي",              "ماء"),
    ("مايه",            "ماء"),
    ("ماية",            "ماء"),
    ("مويه",            "ماء"),
    ("موية",            "ماء"),
    ("الماي",           "الماء"),
    ("بالماي",          "بالماء"),
    ("بركه",            "ماء"),
    ("بركة",            "ماء"),
    ("طبت فيه ماء",     "وقع في الماء"),
    ("طاب في الماء",    "وقع في الماء"),
    ("كرت تالف",        "بدل كرت تالف"),
    ("كرت خربان",       "بدل كرت تالف"),
    ("كرت مبلول",       "كرت شحن وقع في الماء"),
    ("كرت اتبلل",       "كرت شحن وقع في الماء"),
    ("كرت ضاع",         "كرت شحن مفقود"),
    ("كرتي ضاع",        "كرت شحن مفقود"),
    ("الكرت ضاع",       "كرت شحن مفقود"),
    ("باظ الكرت",       "كرت تالف"),
    ("كرت باظ",         "كرت تالف"),
]

def normalize_ar(text: str) -> str:
    t = (text or "").lower().strip()
    t = AR_DIACRITICS.sub("", t)
    t = t.translate(AR_NUMS_MAP)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ى", "ي").replace("ة", "ه")
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    t = AR_PUNCT.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def normalize_query(text: str) -> str:
    t = normalize_ar(text)
    if not t:
        return t
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)
    for a, b in PHRASE_NORMALIZE:
        t = t.replace(normalize_ar(a), normalize_ar(b))
    t = re.sub(r"\s+", " ", t).strip()
    return t


# =============================
# Index + DB storage
# =============================

def load_chunks() -> List[Dict[str, Any]]:
    if not INDEX_PATH.exists():
        raise RuntimeError("rag_index.json not found. Run: python build_index.py")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    chunks = data if isinstance(data, list) else data.get("chunks", [])
    out: list[dict[str, Any]] = []
    for c in chunks:
        if isinstance(c, dict) and (c.get("text") or "").strip():
            out.append(c)
    return out

CHUNKS: List[Dict[str, Any]] = load_chunks()

def ensure_rag_tables() -> None:
    # ✅ PostgreSQL: الجداول تُنشأ في init_db() — هذه الدالة تبقى للتوافق
    from .db import init_db as _init_db
    try:
        _init_db()
    except Exception:
        pass  # الجداول موجودة أصلاً

ensure_rag_tables()

def upsert_chunks_into_db() -> int:
    import json
    from pathlib import Path

    index_path = Path(INDEX_PATH)
    if not index_path.exists():
        return 0

    with index_path.open("r", encoding="utf-8") as f:
        items = json.load(f)

    if not isinstance(items, list):
        return 0

    con = connect()
    try:
        cur = con.cursor()
        upserted = 0

        for item in items:
            chunk_id = str(item.get("chunk_id") or "").strip()
            if not chunk_id:
                continue

            source_file = str(item.get("source_file") or item.get("file") or "").strip()
            text = str(item.get("text") or "").strip()

            metadata = item.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}

            metadata_json = json.dumps(metadata, ensure_ascii=False)

            cur.execute(
                """
                INSERT INTO rag_chunk (
                    chunk_id,
                    source_file,
                    text,
                    metadata_json
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    source_file = EXCLUDED.source_file,
                    text = EXCLUDED.text,
                    metadata_json = EXCLUDED.metadata_json
                """,
                (chunk_id, source_file, text, metadata_json),
            )

            upserted += 1

        con.commit()
        return upserted
    finally:
        con.close()

# =============================
# Embeddings (Ollama)
# =============================

from collections import OrderedDict
import hashlib

# ── Embedding Cache (RAM + disk persistence) ───────────────────
# يُحفظ على disk عند كل إضافة جديدة → لا يضيع عند restart
_EMBED_CACHE_SIZE = int(os.getenv("EMBED_CACHE_SIZE", "512"))
_EMBED_CACHE_PATH = Path(os.getenv("EMBED_CACHE_PATH", "")).resolve() if os.getenv("EMBED_CACHE_PATH") else                     BASE_DIR / "embed_cache.json"

class _LRUEmbedCache:
    def __init__(self, maxsize: int, cache_path: Path):
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._maxsize = maxsize
        self._path = cache_path
        self.hits = 0
        self.misses = 0
        self._dirty = 0          # عدد التعديلات منذ آخر حفظ
        self._SAVE_EVERY = 10    # احفظ على disk كل 10 entries جديدة
        self._load()

    def _key(self, text: str, model: str) -> str:
        return hashlib.md5(f"{model}:{text}".encode()).hexdigest()

    def _load(self) -> None:
        """يحمّل الـ cache من disk عند الـ startup."""
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for k, v in list(data.items())[-self._maxsize:]:
                    self._cache[k] = v
                logger.info(f"[embed_cache] loaded {len(self._cache)} entries from {self._path}")
        except Exception as e:
            logger.warning(f"[embed_cache] load failed (starting fresh): {e}")

    def _save(self) -> None:
        """يحفظ الـ cache على disk — fail-safe."""
        try:
            self._path.write_text(
                json.dumps(dict(self._cache), ensure_ascii=False),
                encoding="utf-8",
            )
            self._dirty = 0
        except Exception as e:
            logger.warning(f"[embed_cache] save failed: {e}")

    def get(self, text: str, model: str):
        k = self._key(text, model)
        if k in self._cache:
            self._cache.move_to_end(k)
            self.hits += 1
            return self._cache[k]
        self.misses += 1
        return None

    def set(self, text: str, model: str, vec: list[float]) -> None:
        k = self._key(text, model)
        self._cache[k] = vec
        self._cache.move_to_end(k)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)
        self._dirty += 1
        if self._dirty >= self._SAVE_EVERY:
            self._save()

    def flush(self) -> None:
        """يحفظ فوراً — استخدمي عند shutdown أو أي عملية مهمة."""
        if self._dirty > 0:
            self._save()

    @property
    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "size": self.size,
            "maxsize": self._maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / max(1, total), 4),
            "cache_path": str(self._path),
        }

_embed_cache = _LRUEmbedCache(_EMBED_CACHE_SIZE, _EMBED_CACHE_PATH)

def get_embed_cache_stats() -> dict:
    return _embed_cache.stats()



def embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) > MAX_EMBED_CHARS:
        text = text[:MAX_EMBED_CHARS]

    # ── Cache lookup ──
    cached = _embed_cache.get(text, EMBED_MODEL)
    if cached is not None:
        return cached

    # ✅ #6: delegate to ollama_client.embed — single source of truth للـ embeddings
    from .ollama_client import embed as _ollama_embed
    vec = _ollama_embed(text)
    if vec:
        _embed_cache.set(text, EMBED_MODEL, vec)
    return vec


def upsert_embedding(chunk_id: str, vec: List[float], model: str = EMBED_MODEL) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO rag_embedding (chunk_id, model, dims, vector_json, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (chunk_id) DO UPDATE SET
          model=EXCLUDED.model,
          dims=EXCLUDED.dims,
          vector_json=EXCLUDED.vector_json,
          updated_at=NOW()
        """,
        (chunk_id, model, int(len(vec)), json.dumps(vec)),
    )
    con.commit()
    con.close()

def build_embeddings(*, limit: Optional[int] = None, overwrite: bool = False) -> Dict[str, Any]:
    """✅ Optimized: no per-chunk DB connect to check existence."""
    upserted = upsert_chunks_into_db()

    con = connect()
    cur = con.cursor()

    cur.execute("SELECT chunk_id, text FROM rag_chunk ORDER BY chunk_id")
    rows = cur.fetchall()

    existing: set[str] = set()
    if not overwrite:
        cur.execute("SELECT chunk_id FROM rag_embedding WHERE model = %s", (EMBED_MODEL,))
        existing = {str(r["chunk_id"]) for r in cur.fetchall()}

    con.close()

    done = 0
    skipped = 0
    errors: list[str] = []

    for row in rows:
        if limit is not None and done >= int(limit):
            break

        chunk_id = str(row["chunk_id"])
        text = str(row["text"])

        if (not overwrite) and (chunk_id in existing):
            skipped += 1
            continue

        try:
            vec = embed_text(text)
            upsert_embedding(chunk_id, vec, EMBED_MODEL)
            done += 1
        except Exception as e:
            errors.append(f"{chunk_id}: {type(e).__name__}: {e}")

    return {
        "ok": True,
        "chunks_upserted": upserted,
        "embeddings_built": done,
        "skipped": skipped,
        "errors": errors[:10],
    }


# =============================
# Dereference + Clarify
# =============================

PRONOUNS = ["هيك", "هي", "هذا", "هاذ", "هاظ", "هدي", "هاد", "هاذي", "هناك", "هون"]

CLEAR_SHORT_QUERIES = {
    "عطل", "شحن", "رصيد", "فاتوره", "فاتورة", "قاطع",
    "عداد", "اشتراك", "تحويل", "ترقيه", "ترقية",
    "اشتراكات", "فواتير", "بلاغ", "انقطاع",
    "عطل كهربا", "العداد بفصل", "العداد يفصل",
}

# كلمات تدل على follow-up لجواب سابق
FOLLOWUP_PATTERNS = [
    "ما فهمت", "مش فاهم", "وضح", "توضيح",
    "الخطوة", "الخطوه", "النقطة", "النقطه",
    "يعني شو", "يعني إيش", "كيف يعني",
    "اكمل", "أكمل", "اشرح", "شرح", "أكثر",
    # ردود موافقة قصيرة — تحتاج context
    "اه", "آه", "أه", "تمام", "ماشي", "زبط", "صح", "اوكي", "اوك", "ok", "okay",
    "شو يعني", "وبعدين", "وبعد", "كمل", "يلا", "طيب",
]

def looks_ambiguous(q: str) -> bool:
    t = normalize_query(q)
    # follow-up صريح → دايماً ambiguous يحتاج context
    for pat in FOLLOWUP_PATTERNS:
        if normalize_query(pat) in t:
            return True
    for clear in CLEAR_SHORT_QUERIES:
        if normalize_query(clear) in t:
            return False
    if len(t) < 4:
        return True
    if t.isdigit():
        return True
    if any(t == normalize_query(p) for p in PRONOUNS):
        return True
    toks = t.split()
    if len(toks) <= 2 and any(tok in PRONOUNS for tok in toks):
        return True
    return False

def dereference(question: str, history: str, last_full_response: str = "") -> str:
    if not history and not last_full_response:
        return question
    if not looks_ambiguous(question):
        return question

    last_users: list[str] = []
    last_bot: Optional[str] = None

    for line in reversed(history.splitlines()):
        line = line.strip()
        if line.startswith("المساعد:") and last_bot is None:
            last_bot = line.replace("المساعد:", "").strip()
            continue
        if line.startswith("المستخدم:"):
            txt = line.replace("المستخدم:", "").strip()
            if txt:
                last_users.append(txt)
                if len(last_users) >= 2:
                    break

    last_users = list(reversed(last_users))

    ctx_parts = []
    if last_users:
        ctx_parts.append("السياق السابق (من المواطن): " + " | ".join(last_users))

    # follow-up → حط الجواب الكامل السابق لأن المستخدم يسأل عن تفصيل منه
    if last_full_response:
        ctx_parts.append("الجواب السابق الكامل:\n" + last_full_response)
    elif last_bot:
        ctx_parts.append("آخر رد من الدعم: " + last_bot)

    ctx = "\n".join(ctx_parts).strip()
    if not ctx:
        return question

    return f"{ctx}\nسؤال المواطن الآن: {question}".strip()

def clarify_question(q: str) -> str:
    if looks_ambiguous(q):
        return "ممكن توضّح قصدك أكثر؟ مثلاً: شحن رصيد، عطل كهربا، تحويل عداد من فاز لثلاثة فازات، رصيد العداد."
    return f"ما لقيت معلومة دقيقة لطلبك حالياً. تقدر/ي تتواصل/ي معنا على: {SUPPORT_PHONE} أو وضّح/ي السؤال أكثر."


# =============================
# Context building
# =============================

def dedup_chunks(chunks: List[Dict[str, Any]], sim_threshold: float = 0.85) -> List[Dict[str, Any]]:
    """
    يحذف الـ chunks المتكررة بناءً على تشابه النص (Jaccard على الكلمات).
    يحتفظ بأعلى واحد من كل مجموعة متشابهة.
    """
    if not chunks:
        return chunks

    def _tokens(text: str) -> set:
        return set(re.sub(r"[^\w\u0600-\u06FF]", " ", text.lower()).split())

    def _jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    kept: List[Dict[str, Any]] = []
    for chunk in chunks:
        tok = _tokens(chunk.get("text") or "")
        is_dup = False
        for k in kept:
            if _jaccard(tok, _tokens(k.get("text") or "")) >= sim_threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(chunk)
    return kept


def build_context(top_chunks: List[Dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, c in enumerate(top_chunks[:CONTEXT_K], start=1):
        txt = (c.get("text") or "").strip()
        meta = c.get("metadata", {}) or {}
        title = str(meta.get("section_title") or "").strip()
        header = f"[معلومة {i}]"
        if title:
            header += f" — {title}"
        parts.append(header + "\n" + txt)

    ctx = "\n\n".join(parts).strip()
    if len(ctx) > MAX_CONTEXT_CHARS:
        ctx = ctx[:MAX_CONTEXT_CHARS] + "\n\n...(تم قص جزء من السياق للتخفيف)"
    return ctx


# =============================
# Query typing + length control
# =============================

def _qtype(q: str) -> str:
    t = normalize_query(q)

    if "رقم" in t and ("الطوارئ" in t or "طوار" in t):
        return "emergency_number"
    if "واتس" in t or "whatsapp" in t:
        return "whatsapp"
    if "رقم" in t and ("الهاتف" in t or "المقر" in t or "الشرك" in t or "تواصل" in t or "التواصل" in t):
        return "contact_number"
    if t.strip() in {"رقم", "ارقام", "أرقام", "رقم الهاتف", "رقم التواصل", "رقم الشركه", "ارقام التواصل"}:
        return "contact_number"

    return "general"

# =============================
# Topic Detection
# =============================

# مجموعات الـ topics — كل مجموعة = موضوع واحد
# لو السؤال الجديد من نفس المجموعة = نفس الموضوع
# لو من مجموعة مختلفة = موضوع جديد → نقطع الـ context

TOPIC_GROUPS: List[List[str]] = [
    # فواتير واعتراض
    ["فاتوره", "فواتير", "سداد", "دفع", "حساب", "عاليه", "مرتفع", "اعتراض استهلاك"],
    # عداد مسبق الدفع وشحن
    ["مسبق الدفع", "شحن رصيد عداد", "رصيد عداد", "كود", "بطاقه شحن", "كرت شحن", "شحن"],
    # اشتراك جديد ووثائق
    ["طلب اشتراك كهرباء", "اشتراك جديد", "توصيل", "وثائق", "مستندات", "طابو"],
    # عطل وانقطاع
    ["انقطاع كهرباء", "عطل", "قاطع عداد", "ضعف تيار", "خلل", "لا يعمل"],
    # تحويل فاز وترقية
    ["ثلاثي الفاز", "احادي الفاز", "تحويل", "ترقيه خدمه", "زيادة قدره"],
    # تواصل وأرقام
    ["رقم الهاتف", "رقم التواصل", "رقم الطوارئ", "واتس", "ايميل", "مقر"],
    # طاقة شمسية
    ["طاقه شمسيه", "سولار", "الواح"],
    # شكاوى
    ["شكوى", "شكاوي", "تقديم شكوى"],
    # ترشيد طاقة
    ["ترشيد", "توفير كهربا", "توفير طاقه"],
]

def _get_topic_group(q_norm: str) -> Optional[int]:
    """ترجع رقم المجموعة (index) إذا انتمى السؤال لموضوع محدد، أو None."""
    for i, keywords in enumerate(TOPIC_GROUPS):
        if any(kw in q_norm for kw in keywords):
            return i
    return None


def detect_topic_change(new_q_norm: str, conversation_id: int) -> bool:
    """
    يقارن موضوع السؤال الجديد مع آخر سؤال بالمحادثة.
    ترجع True لو الموضوع تغير فعلاً (موضوع جديد).
    ترجع False لو نفس الموضوع أو مش واضح.
    """
    new_topic = _get_topic_group(new_q_norm)

    # لو السؤال الجديد ما انتمى لأي موضوع محدد → مش واضح → لا نقطع
    if new_topic is None:
        return False

    try:
        con = connect()
        cur = con.cursor()
        # آخر سؤال من المستخدم في نفس المحادثة
        cur.execute(
            """
            SELECT message_text FROM message
            WHERE conversation_id = %s
              AND message_type = 'user'
            ORDER BY message_id DESC
            LIMIT 1
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
        con.close()
    except Exception:
        return False

    if not row:
        return False  # أول رسالة → لا يوجد تاريخ

    last_q_norm = normalize_query(str(row["message_text"]))
    last_topic  = _get_topic_group(last_q_norm)

    # لو آخر سؤال ما كان له موضوع محدد → لا نقطع
    if last_topic is None:
        return False

    # الموضوع تغير
    changed = last_topic != new_topic
    if changed:
        logger.info(
            f"[topic] conv={conversation_id} topic changed: group {last_topic} → group {new_topic} "
            f"| last={last_q_norm[:40]!r} new={new_q_norm[:40]!r}"
        )
    return changed


def wants_long_answer(q: str) -> bool:
    t = normalize_query(q)

    if "رقم" in t or "هاتف" in t or "واتس" in t or "طوار" in t:
        return False

    keywords = [
        "يفصل", "بفصل", "فصل", "عطل", "ضعيف", "تيار", "شحنت",
        "ما حول", "ما وصل", "فاتوره", "عاليه", "مرتفع",
        "انقطاع", "تحويل", "ثلاثي", "احادي", "تعرفه",
        "اشتراك", "طلب اشتراك", "وثائق", "مستندات",
    ]
    return any(k in t for k in keywords) or len(t.split()) >= 5


# =============================
# LLM
# =============================

def call_llm(
    *,
    context: str,
    question: str,
    intent_code: str = "",
    category: str = "",
    history_messages: list[dict] | None = None,
) -> str:
    long_mode = wants_long_answer(question)

    # ── Prompt ذكي حسب الـ intent ─────────────────────────────
    intent_hint = ""
    if intent_code == "complaint_bill":
        intent_hint = "\n[تعليمات إضافية] هذا اعتراض على فاتورة — اشرح خطوات الاعتراض بوضوح."
    elif intent_code == "outage_fault":
        intent_hint = "\n[تعليمات إضافية] مشكلة تقنية — ابدأ بالأسباب الشائعة ثم خطوات الحل."
    elif intent_code in ("new_subscription", "phase_upgrade"):
        intent_hint = "\n[تعليمات إضافية] طلب خدمة — اذكر المستندات المطلوبة والخطوات والمدة."
    elif intent_code == "prepaid_recharge":
        intent_hint = "\n[تعليمات إضافية] عداد مسبق الدفع — اشرح خطوات الشحن وحل مشاكله."
    elif intent_code == "contact_info":
        intent_hint = "\n[تعليمات إضافية] سؤال عن تواصل — جواب قصير مباشر بالأرقام فقط."

    options = {
        "temperature": 0.20 if long_mode else 0.10,
        "top_p": 0.85,
        "num_predict": 1200 if long_mode else 380,
    }

    # ── بناء messages مع الـ history ─────────────────────────
    # الترتيب: system → history (user/assistant) → رسالة المستخدم الجديدة
    #
    # المعلومات (RAG context) نحطها في آخر رسالة user فقط —
    # لأن الـ LLM يركز على آخر رسالة أكثر، وبهيك نوفر tokens
    # على الـ turns القديمة.

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history_messages:
        # نضيف الـ history بدون معلومات RAG (هي للسؤال الحالي فقط)
        messages.extend(history_messages)

    # الرسالة الأخيرة: السؤال الجديد + المعلومات من الـ RAG
    # تاريخ اليوم — مهم لأسئلة الانقطاع المجدول والمواعيد
    _days_ar = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    _today = datetime.now()
    _today_str = f"{_days_ar[_today.weekday()]} {_today.strftime('%Y-%m-%d')}"
    user_content = f"[تاريخ اليوم: {_today_str}]\n\n[المعلومات]\n{context}\n\n[سؤال المواطن]\n{question}"
    if intent_hint:
        user_content += intent_hint

    # ✅ إلزام الرد بالعربية — حماية من انزلاق الـ LLM للغات أخرى
    user_content += "\n\n[إلزامي: الرد باللغة العربية فقط]"

    messages.append({"role": "user", "content": user_content})

    data = post_json(
        "/api/chat",
        {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "options": options,
        },
        timeout=OLLAMA_TIMEOUT,
    )
    return ((data.get("message") or {}).get("content") or "").strip()

def rewrite_query(question: str, history: str) -> str:
    question = (question or "").strip()
    if not question:
        return question

    prompt = f"""
أعد صياغة سؤال المواطن إلى "استعلام بحث" واضح ومحدد لشركة كهرباء الخليل.
- لا تجاوب.
- فقط اكتب الاستعلام بجملة واحدة.
- أضف كلمات مفتاحية مناسبة.
سؤال المواطن: {question}
سياق مختصر (إن وجد): {history[-400:] if history else ""}
""".strip()

    try:
        data = post_json(
            "/api/chat",
            {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "أنت مساعد يعيد صياغة الاستعلام فقط."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        out = ((data.get("message") or {}).get("content") or "").strip()
        return out or question
    except Exception:
        return question


# =============================
# Post-processing + Numbers extraction
# =============================

def clean_answer(ans: str) -> str:
    if not ans:
        return ans
    ans = ans.strip()

    bad_phrases = [
        "كمساعد", "مصدر", "المصادر",
        "بناء على", "وفقاً لطلبك", "بالنسبة لسؤالك",
        "وفقاً للمعلومات المرفقة", "بناءً على المعلومات المتوفرة",
        "استناداً إلى", "يسعدني مساعدتك", "بكل سرور",
        "بالتأكيد، ", "بالتأكيد سأساعدك", "شكراً على سؤالك",
    ]

    lines = [l.strip() for l in ans.split("\n") if l.strip()]
    lines = [l for l in lines if not any(p in l for p in bad_phrases)]

    # احذف السطر الأول لو كان تكرار السؤال
    if len(lines) >= 2 and (lines[0].endswith("؟") or lines[0].endswith("%s")):
        lines = lines[1:]

    out = "\n".join(lines).strip()
    if len(out) > 4500:
        out = out[:4500].rstrip()
    return out

PHONE_REGEX = re.compile(r"(?:(?:هاتف|تلفون|رقم|tel|phone|واتس|whatsapp)\s*[:\-]?\s*)?(\+?[\d][\d\s\-\/]{5,}\d)", re.IGNORECASE)

def extract_numbers_from_chunks(chunks: List[Dict[str, Any]], *, max_numbers: int = 8) -> str:
    numbers: list[str] = []
    seen: set[str] = set()

    for c in chunks:
        text = (c.get("text") or "")
        found = PHONE_REGEX.findall(text)
        for n in found:
            n = re.sub(r"\s+", " ", n.strip())
            if n and n not in seen:
                seen.add(n)
                numbers.append(n)

    if not numbers:
        return ""

    lines = [f"- {n}" for n in numbers[:max_numbers]]
    return "أرقام التواصل المتوفرة:\n" + "\n".join(lines)

def collect_allowed_numbers(chunks: List[Dict[str, Any]]) -> set[str]:
    allowed: set[str] = set()
    for c in chunks or []:
        text = (c.get("text") or "")
        for n in PHONE_REGEX.findall(text):
            n = re.sub(r"\s+", " ", n.strip())
            if n:
                allowed.add(n)
    if SUPPORT_PHONE:
        allowed.add(SUPPORT_PHONE)
    return allowed

def strip_untrusted_numbers(answer: str, allowed: set[str]) -> str:
    if not answer:
        return answer

    def _repl(m: re.Match) -> str:
        n = re.sub(r"\s+", " ", m.group(0).strip())
        return n if (n in allowed) else SUPPORT_PHONE

    return PHONE_REGEX.sub(_repl, answer)

def extractive_answer(question: str, ranked: List[Dict[str, Any]]) -> str:
    q_words = [w for w in normalize_query(question).split() if len(w) > 2]
    if not ranked:
        return ""
    text = (ranked[0].get("text") or "").strip()
    if not text:
        return ""

    sents = re.split(r"[\.!\%s。\n\r]+", text)
    sents = [s.strip() for s in sents if s.strip()]

    def score_sent(s: str) -> int:
        t = normalize_query(s)
        return sum(1 for w in q_words if w in t)

    scored = [(score_sent(s), s) for s in sents]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_sents = [s for sc, s in scored if sc > 0][:4]
    if not best_sents:
        return "\n".join(text.splitlines()[:3]).strip()
    return " ".join(best_sents).strip()


# =============================
# Conversation history
# =============================

def load_recent_chat(conversation_id: int, limit: int = 6) -> str:
    """نص مختصر للـ dereference و rewrite_query."""
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        SELECT message_type, message_text, response_text
        FROM message
        WHERE conversation_id=%s
        ORDER BY message_id DESC
        LIMIT %s
        """,
        (conversation_id, limit),
    )
    rows = list(reversed(cur.fetchall()))
    con.close()

    lines: list[str] = []
    for r in rows:
        if r["message_type"] == "user":
            lines.append(f"المستخدم: {r['message_text']}")
        else:
            resp = (r["response_text"] or r["message_text"] or "").strip()
            lines.append(f"المساعد: {resp[:300]}{'...' if len(resp) > 300 else ''}")
    return "\n".join(lines).strip()


def load_history_as_messages(conversation_id: int, limit: int = 6) -> list[dict]:
    """
    يجيب تاريخ المحادثة بصيغة messages مناسبة للـ LLM.
    كل رسالة: {"role": "user"|"assistant", "content": "..."}
    يُستخدم لإعطاء الـ LLM سياق المحادثة الكاملة وليس فقط السؤال.

    limit=6 يعني آخر 3 رسائل من المستخدم + 3 ردود من البوت.
    نقطع الـ response عند 600 حرف لتجنب تضخم الـ context window.
    """
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        SELECT message_type, message_text, response_text
        FROM message
        WHERE conversation_id=%s
        ORDER BY message_id DESC
        LIMIT %s
        """,
        (conversation_id, limit),
    )
    rows = list(reversed(cur.fetchall()))
    con.close()

    msgs: list[dict] = []
    for r in rows:
        if r["message_type"] == "user":
            msgs.append({"role": "user", "content": str(r["message_text"] or "").strip()})
        else:
            resp = (r["response_text"] or r["message_text"] or "").strip()
            # نقطع الردود الطويلة لتوفير tokens
            if len(resp) > 600:
                resp = resp[:600] + "..."
            msgs.append({"role": "assistant", "content": resp})

    return msgs


def load_last_bot_response(conversation_id: int) -> str:
    """
    آخر جواب كامل من البوت — يُستخدم لما المستخدم يسأل
    عن تفصيل أو خطوة من جواب سابق (follow-up).
    """
    try:
        con = connect()
        cur = con.cursor()
        cur.execute(
            """
            SELECT response_text, message_text
            FROM message
            WHERE conversation_id = %s
              AND message_type = 'assistant'
            ORDER BY message_id DESC
            LIMIT 1
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
        con.close()
        if not row:
            return ""
        return (row["response_text"] or row["message_text"] or "").strip()
    except Exception:
        return ""


# =============================
# Result schema
# =============================

@dataclass
class RagResult:
    answer: str
    sources: List[Dict[str, Any]]
    mode: str
    best_score: float
    intent: Optional[str] = None
    category: Optional[str] = None
    retrieval_mode: str = "unknown"
    confidence: float = 0.0
    latency_ms: int = 0


# =============================
# End-to-end answer
# =============================

from datetime import datetime

# ── كلمات قصيرة لا تحتاج RAG ──────────────────────────────
_SHORT_REPLIES = {
    "ماشي", "شكرا", "شكراً", "ok", "okay", "اه", "اهه", "لا", "نعم",
    "يسلمو", "تسلم", "تسلمي", "مشكور", "مشكوره", "بديش", "بديش اشي",
    "ثانكس", "thanks", "تمام", "مضبوط", "كويس", "هلا", "اوكي", "اوك",
    "طيب", "ايوه", "أيوه", "ايوا", "احسنت", "برافو", "عظيم", "ممتاز",
}

def _is_short_reply(text: str) -> bool:
    """يكشف الردود القصيرة التي لا تحتاج RAG."""
    t = text.strip()
    if len(t) <= 3:
        return True
    t_norm = normalize_ar(t)
    return t_norm in {normalize_ar(w) for w in _SHORT_REPLIES}


def answer_with_rag(question_raw: str, conversation_id: int) -> RagResult:
    _t_start = _time.perf_counter()

    # ── 0) تطبيع اللهجة الدارجة → عربية فصيحة ───────────────
    # يشتغل فقط لو في كلمات دارجة مكتشفة (كاشف سريع قبل LLM call)
    # fail-safe: لو الـ LLM تأخر أو فشل يرجع النص الأصلي
    question_raw = normalize_dialect(question_raw)

    q_norm = normalize_query(question_raw)

    # ── 0a) رد قصير؟ (ماشي، ok، شكرا...) ───────────────────
    if _is_short_reply(question_raw):
        logger.info(f"[rag] conv={conversation_id} short_reply detected: {question_raw!r}")
        return RagResult(
            answer="أهلاً، إذا عندك أي سؤال عن خدمات كهرباء الخليل أنا هون.",
            sources=[],
            mode="short_reply",
            best_score=0.0,
            confidence=1.0,
            retrieval_mode="blocked",
            latency_ms=round((_time.perf_counter() - _t_start) * 1000),
        )

    # ── 0b) Guardrail: خارج الموضوع؟ ─────────────────────────
    if is_off_topic(question_raw):
        logger.info(f"[rag] conv={conversation_id} off_topic detected")
        return RagResult(
            answer=OFF_TOPIC_REPLY,
            sources=[],
            mode="off_topic",
            best_score=0.0,
            confidence=0.0,
            retrieval_mode="blocked",
            latency_ms=round((_time.perf_counter() - _t_start) * 1000),
        )

    # ── 1) Intent Classification ──────────────────────────────
    intent_result: IntentResult = classify_intent(question_raw)
    logger.info(
        json.dumps({
            "event": "intent_classified",
            "conv": conversation_id,
            "intent": intent_result.intent_code,
            "category": intent_result.category,
            "confidence": intent_result.confidence,
            "mode": intent_result.answer_mode,
        }, ensure_ascii=False)
    )

    # ── 1a) Direct Answer (ساعات عمل، طوارئ) — بدون RAG ─────
    if intent_result.answer_mode == "direct" and intent_result.direct_answer:
        _latency = round((_time.perf_counter() - _t_start) * 1000)
        logger.info(f"[rag] conv={conversation_id} direct_answer intent={intent_result.intent_code}")
        return RagResult(
            answer=intent_result.direct_answer,
            sources=[],
            mode="direct_intent",
            best_score=1.0,
            intent=intent_result.intent_code,
            category=intent_result.category,
            retrieval_mode="direct",
            confidence=1.0,
            latency_ms=_latency,
        )

    # ── 2) Answer Cache — نفس السؤال؟ ────────────────────────
    _cache = get_answer_cache()
    cached = _cache.get(question_raw)
    if cached is not None:
        _latency = round((_time.perf_counter() - _t_start) * 1000)
        logger.info(
            f"[rag] conv={conversation_id} CACHE HIT "
            f"intent={cached.intent} latency={_latency}ms"
        )
        return RagResult(
            answer=cached.answer,
            sources=[],
            mode="cache_hit",
            best_score=cached.confidence,
            intent=cached.intent or intent_result.intent_code,
            category=cached.category or intent_result.category,
            retrieval_mode="cache",
            confidence=cached.confidence,
            latency_ms=_latency,
        )

    # ── 3) Topic Detection ────────────────────────────────────
    topic_changed = detect_topic_change(q_norm, conversation_id)

    if topic_changed:
        history          = ""
        history_messages = []
        logger.info(f"[rag] conv={conversation_id} topic changed → context cleared")
    else:
        history          = load_recent_chat(conversation_id, limit=6)
        # نجيب الـ history بصيغة messages للـ LLM (آخر 3 تبادلات = 6 رسائل)
        history_messages = load_history_as_messages(conversation_id, limit=6)

    # ── 4) Dereference + Query Rewrite ───────────────────────
    last_full_resp = load_last_bot_response(conversation_id) if looks_ambiguous(q_norm) else ""
    q_deref        = dereference(q_norm, history, last_full_response=last_full_resp)

    # ── 5) Retrieval ──────────────────────────────────────────
    _retrieval_mode: str
    _t_ret = _time.perf_counter()

    # لو الـ intent واضح، نزيد TOP_K لنجيب أكثر
    top_k_effective = TOP_K + 5 if intent_result.confidence > 0.5 else TOP_K

    if qdrant_enabled():
        top, best = retrieve_hybrid(
            query=q_deref,
            embed_fn=embed_text,
            top_k=top_k_effective,
            min_sim=MIN_SIM,
        )
        _retrieval_mode = "hybrid_qdrant"
    else:
        top, best = retrieve_mmr(
            query=q_deref,
            embed_fn=embed_text,
            model=EMBED_MODEL,
            top_k=top_k_effective,
            min_sim=MIN_SIM,
        )
        _retrieval_mode = "mmr_pg"
    _ret_ms = round((_time.perf_counter() - _t_ret) * 1000)

    # ── 5a) Query Rewrite fallback ────────────────────────────
    if (not top) or (float(best) < float(LOW_CONF)):
        try:
            q_search = rewrite_query(q_norm, history)
            if qdrant_enabled():
                top2, best2 = retrieve_hybrid(
                    query=q_search, embed_fn=embed_text,
                    top_k=top_k_effective, min_sim=MIN_SIM,
                )
            else:
                top2, best2 = retrieve_mmr(
                    query=q_search, embed_fn=embed_text,
                    model=EMBED_MODEL, top_k=top_k_effective, min_sim=MIN_SIM,
                )
            if top2 and (not top or float(best2) > float(best)):
                top = top2
                best = best2
                q_deref = q_search
        except Exception as _rw_err:
            # ✅ اقتراح ب: log بدل صمت — يساعد في التشخيص
            logger.warning(f"[rag] query rewrite failed, using original: {_rw_err}")

    # ── 6) Dedup + Rerank + Context ───────────────────────────
    top = dedup_chunks(top)
    ranked = rerank(q_deref, top, top_n=RERANK_TOP_N, use_cross_encoder=False)
    context = build_context(ranked)

    # intent/category من أفضل chunk
    top_intent: str | None = intent_result.intent_code if intent_result.confidence > 0.3 else None
    top_category: str | None = intent_result.category if intent_result.confidence > 0.3 else None

    # إذا الـ intent classifier غير واثق، خذ من الـ chunk
    if not top_intent and ranked:
        meta0 = ranked[0].get("metadata", {}) or {}
        top_intent = meta0.get("intent") or None
        top_category = meta0.get("category") or None

    # ── 7) Numbers shortcut ───────────────────────────────────
    qt = _qtype(q_norm)
    if qt in {"contact_number", "emergency_number", "whatsapp"}:
        ans_num = extract_numbers_from_chunks(ranked)
        if ans_num:
            sources_num = [
                {
                    "file": c.get("file"),
                    "chunk_id": c.get("chunk_id"),
                    "section_title": (c.get("metadata") or {}).get("section_title") or None,
                    "score": round(float(c.get("score", 0.0)), 4),
                }
                for c in ranked[:CONTEXT_K]
            ]
            return RagResult(
                answer=ans_num, sources=sources_num, mode="rag_numbers",
                best_score=float(best), intent=top_intent, category=top_category,
                retrieval_mode=_retrieval_mode,
                confidence=round(min(float(best), 1.0), 4),
            )
        return RagResult(
            answer="ما لقيت أرقام واضحة داخل قاعدة البيانات الحالية. إذا بتضيف/ي ملف فيه الأرقام أو اسم القسم بقدر أستخرجها.",
            sources=[], mode="rag_numbers_empty",
            best_score=float(best), intent=top_intent, category=top_category,
            retrieval_mode=_retrieval_mode, confidence=0.0,
        )

    # ── 8) LLM ────────────────────────────────────────────────
    allowed_numbers = collect_allowed_numbers(ranked)
    low_conf = float(best) < float(LOW_CONF)
    note = "إذا لم تجد المعلومة كافية، أعطِ إجابة عامة مفيدة واذكر رقم التواصل." if low_conf else ""
    q_for_llm = question_raw.strip() if question_raw.strip() else q_norm

    try:
        _t_llm = _time.perf_counter()
        ans = call_llm(
            context=context,
            question=f"{q_for_llm}\n\nملاحظة: {note}" if note else q_for_llm,
            intent_code=intent_result.intent_code,
            category=intent_result.category,
            history_messages=history_messages if not topic_changed else None,
        )
        _llm_ms = round((_time.perf_counter() - _t_llm) * 1000)
        ans = clean_answer(ans)
        ans = strip_untrusted_numbers(ans, allowed_numbers)

        if not ans:
            ans = clean_answer(extractive_answer(q_norm, ranked)) or clarify_question(q_norm)
            mode = "rag_extractive_fallback"
        else:
            mode = "rag"

    except Exception:
        _llm_ms = 0
        ans = clean_answer(extractive_answer(q_norm, ranked)) or clarify_question(q_norm)
        ans = strip_untrusted_numbers(ans, allowed_numbers)
        mode = "rag_extractive_fallback"

    # ── 9) Save to Answer Cache ───────────────────────────────
    final_confidence = round(min(float(best), 1.0), 4)
    if mode == "rag" and ans:
        _cache.set(
            question_raw,
            ans,
            mode=mode,
            confidence=final_confidence,
            intent=top_intent,
            category=top_category,
        )

    # ── 10) Log ───────────────────────────────────────────────
    _total_ms = round((_time.perf_counter() - _t_start) * 1000)
    logger.info(
        json.dumps({
            "event": "rag_request",
            "conv": conversation_id,
            "retrieval_mode": _retrieval_mode,
            "mode": mode,
            "intent": top_intent,
            "intent_conf": intent_result.confidence,
            "category": top_category,
            "confidence": final_confidence,
            "best_score": round(float(best), 4),
            "chunks_retrieved": len(top),
            "chunks_ranked": len(ranked),
            "low_conf": low_conf,
            "retrieval_ms": _ret_ms,
            "llm_ms": _llm_ms,
            "total_ms": _total_ms,
            "q_len": len(q_norm),
        }, ensure_ascii=False)
    )
    # ✅ AI Logger — يسجّل في ai.log
    try:
        from .logging_config import AiLogger
        AiLogger.log(
            "rag_request",
            conv=conversation_id,
            mode=mode,
            intent=top_intent,
            confidence=final_confidence,
            llm_ms=_llm_ms,
            total_ms=_total_ms,
        )
    except Exception:
        pass
    # ✅ LLM Usage Tracker
    try:
        from .admin_controls_api import llm_tracker
        llm_tracker.record(
            model=LLM_MODEL,
            latency_ms=_llm_ms,
            tokens_in=len(q_norm) // 4,       # تقدير تقريبي
            tokens_out=len(ans) // 4 if ans else 0,
            success=(mode != "rag_extractive_fallback"),
        )
    except Exception:
        pass

    def _enrich_source(c: dict) -> dict:
        meta = c.get("metadata") or {}
        return {
            "file": c.get("file"),
            "chunk_id": c.get("chunk_id"),
            "section_title": meta.get("section_title") or meta.get("title") or None,
            "category": meta.get("category") or None,
            "intent": meta.get("intent") or None,
            "score": round(float(c.get("score", 0.0)), 4),
        }

    sources = [_enrich_source(c) for c in ranked[:CONTEXT_K]]
    return RagResult(
        answer=ans,
        sources=sources,
        mode=mode,
        best_score=float(best),
        intent=top_intent,
        category=top_category,
        retrieval_mode=_retrieval_mode,
        confidence=final_confidence,
        latency_ms=_total_ms,
    )
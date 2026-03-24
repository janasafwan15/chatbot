"""
build_index.py — بناء rag_index.json من مجلد data/
=====================================================
الاستخدام:
    python build_index.py              # يقرأ data/ ويبني rag_index.json
    python build_index.py --data path  # مجلد مخصص
    python build_index.py --verbose    # تفاصيل كل chunk

يدعم: .docx  .pdf  .txt  .md  .html  .xlsx  .csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ═══════════════════════════════════════════════════════════════
# SECTION 1 — تثبيت وتحميل المكتبات
# ═══════════════════════════════════════════════════════════════
def _require(pkg: str, install: str = None):
    import importlib
    try:
        return importlib.import_module(pkg)
    except ImportError:
        pip_name = install or pkg
        print(f"   ⚙️  تثبيت {pip_name}...")
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pip_name, "--break-system-packages", "-q"]
        )
        return importlib.import_module(pkg)


# ═══════════════════════════════════════════════════════════════
# SECTION 2 — تطبيع النص العربي
# ═══════════════════════════════════════════════════════════════
AR_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
AR_PUNCT      = re.compile(r"[^\w\s\u0600-\u06FF]")
AR_NUMS       = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

STOPWORDS = {
    "من","إلى","على","في","عن","مع","أو","حيث","يتم","بعد","خلال",
    "هذا","هذه","كان","يكون","ذلك","التي","الذي","وفق","حسب","قبل",
    "عند","إذا","إذ","أن","لأن","كما","فإن","ثم","كل","قد","لا","لم",
    "ما","هل","هو","هي","نحن","أنت","أنا","يجب","يمكن","يحق","لكن",
}

def normalize(text: str) -> str:
    t = (text or "").lower().strip()
    t = AR_DIACRITICS.sub("", t)
    t = t.translate(AR_NUMS)
    t = t.replace("أ","ا").replace("إ","ا").replace("آ","ا")
    t = t.replace("ى","ي").replace("ة","ه")
    t = t.replace("ؤ","و").replace("ئ","ي")
    t = AR_PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()

def extract_keywords(text: str, n: int = 12) -> List[str]:
    words = re.findall(r"[\u0600-\u06FF]{3,}", text)
    freq  = Counter(w for w in words if normalize(w) not in STOPWORDS)
    return [w for w, _ in freq.most_common(n)]


# ═══════════════════════════════════════════════════════════════
# SECTION 3 — قراءة الملفات
# ═══════════════════════════════════════════════════════════════
ALLOWED = {".docx", ".pdf", ".txt", ".md", ".html", ".htm",
           ".xlsx", ".xls", ".csv"}

def read_docx(path: Path) -> str:
    Document = _require("docx", "python-docx").Document
    if path.name.startswith("~$"):
        return ""
    try:
        doc = Document(str(path))
        return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        print(f"  ⚠️ docx error: {e}")
        return ""

def read_pdf(path: Path) -> str:
    PdfReader = _require("pypdf", "pypdf").PdfReader
    try:
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages):
            t = (page.extract_text() or "").strip()
            if t:
                pages.append(f"[صفحة {i+1}]\n{t}")
        return "\n\n".join(pages)
    except Exception as e:
        print(f"  ⚠️ pdf error: {e}")
        return ""

def read_txt(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "windows-1256", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    return ""

def read_html(path: Path) -> str:
    bs4 = _require("bs4", "beautifulsoup4")
    html = read_txt(path)
    # lxml قد لا يكون مثبت، فلو مش موجود BeautifulSoup رح يشتغل parser افتراضي
    return bs4.BeautifulSoup(html, "lxml").get_text(separator="\n")

def read_excel(path: Path) -> str:
    pd = _require("pandas")
    _require("openpyxl")
    try:
        df = pd.read_excel(path, dtype=str).fillna("")
        rows = []
        for _, row in df.iterrows():
            parts = [f"{c}: {row[c]}" for c in df.columns if str(row[c]).strip()]
            if parts:
                rows.append(" | ".join(parts))
        return "\n".join(rows)
    except Exception as e:
        print(f"  ⚠️ excel error: {e}")
        return ""

def read_csv(path: Path) -> str:
    pd = _require("pandas")
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        rows = []
        for _, row in df.iterrows():
            parts = [f"{c}: {row[c]}" for c in df.columns if str(row[c]).strip()]
            if parts:
                rows.append(" | ".join(parts))
        return "\n".join(rows)
    except Exception as e:
        print(f"  ⚠️ csv error: {e}")
        return ""

def read_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".docx":           return read_docx(path)
    if ext == ".pdf":            return read_pdf(path)
    if ext in {".txt", ".md"}:   return read_txt(path)
    if ext in {".html",".htm"}:  return read_html(path)
    if ext in {".xlsx",".xls"}:  return read_excel(path)
    if ext == ".csv":            return read_csv(path)
    return read_txt(path)


# ═══════════════════════════════════════════════════════════════
# SECTION 3.5 — تحويل Excel/CSV إلى Documents (كل صف Document)
# ═══════════════════════════════════════════════════════════════
def rows_to_documents(path: Path, file_key: str) -> List[Dict[str, Any]]:
    """تحويل Excel/CSV إلى chunks بحيث كل صف = Document واحد.

    الهدف: نص صريح (explicit context) + dereference (sheet/row) داخل metadata.
    """
    ext = path.suffix.lower()
    pd = _require("pandas")

    if ext in {".xlsx", ".xls"}:
        _require("openpyxl")
        try:
            xls = pd.ExcelFile(path)
            all_docs: List[Dict[str, Any]] = []
            for sheet in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet, dtype=str).fillna("")
                for i, row in df.iterrows():
                    parts = []
                    for c in df.columns:
                        v = str(row.get(c, "")).strip()
                        if v:
                            parts.append(f"{c}: {v}")
                    if not parts:
                        continue

                    row_index = int(i) + 2  # غالباً الصف 1 عناوين
                    explicit = (
                        f"ملف: {path.name} | الشيت: {sheet} | الصف: {row_index}\n"
                        + " | ".join(parts)
                    ).strip()

                    cat, intent = detect_intent(explicit)
                    cid = f"{file_key}_{normalize(sheet)[:18]}_row{row_index}"
                    all_docs.append({
                        "chunk_id": cid,
                        "file": file_key,
                        "text": explicit,
                        "metadata": {
                            "source_type": "excel",
                            "source_file": file_key,
                            "file_name": path.name,
                            "sheet_name": sheet,
                            "row_index": row_index,
                            "section_title": f"{path.stem} / {sheet}",
                            "category": cat,
                            "intent": intent,
                            "keywords": extract_keywords(explicit),
                            "char_count": len(explicit),
                        },
                    })
            return all_docs
        except Exception as e:
            print(f"  ⚠️ excel rows error: {e}")
            return []

    if ext == ".csv":
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
            docs: List[Dict[str, Any]] = []
            for i, row in df.iterrows():
                parts = []
                for c in df.columns:
                    v = str(row.get(c, "")).strip()
                    if v:
                        parts.append(f"{c}: {v}")
                if not parts:
                    continue

                row_index = int(i) + 2
                explicit = (
                    f"ملف: {path.name} | الشيت: CSV | الصف: {row_index}\n"
                    + " | ".join(parts)
                ).strip()

                cat, intent = detect_intent(explicit)
                cid = f"{file_key}_csv_row{row_index}"
                docs.append({
                    "chunk_id": cid,
                    "file": file_key,
                    "text": explicit,
                    "metadata": {
                        "source_type": "csv",
                        "source_file": file_key,
                        "file_name": path.name,
                        "sheet_name": "CSV",
                        "row_index": row_index,
                        "section_title": f"{path.stem} / CSV",
                        "category": cat,
                        "intent": intent,
                        "keywords": extract_keywords(explicit),
                        "char_count": len(explicit),
                    },
                })
            return docs
        except Exception as e:
            print(f"  ⚠️ csv rows error: {e}")
            return []

    return []


# ═══════════════════════════════════════════════════════════════
# SECTION 4 — اكتشاف العناوين
# ═══════════════════════════════════════════════════════════════
HEADER_RE = re.compile(
    r"^(?:"
    r"\d{1,2}[\.\-\)]\s+"
    r"|[أا]ولا[ًا]?\s*[:\-]"
    r"|ثانيا[ًا]?\s*[:\-]"
    r"|ثالثا[ًا]?\s*[:\-]"
    r"|رابعا[ًا]?\s*[:\-]"
    r"|خامسا[ًا]?\s*[:\-]"
    r"|سادسا[ًا]?\s*[:\-]"
    r"|سابعا[ًا]?\s*[:\-]"
    r"|ثامنا[ًا]?\s*[:\-]"
    r"|طلب\s"
    r"|كيف\s"
    r"|(?:ما|هل|لماذا|متى|أين)\s"
    r"|(?:مميزات|أعطال|ارشادات|اجراء|الشكاوى)\b"
    r"|(?:تغيير|نقل|فصل|وصل|اعادة|فحص|اصدار)\s"
    r"|(?:ترشيد|تنازل|تخفيض|اعتراض|تعديل|معالجة)\s"
    r")",
    re.IGNORECASE,
)

def is_header(line: str) -> bool:
    t = line.strip()
    if re.search(r"\t\d+\s*$", t):  # جدول محتويات
        return False
    if len(t) < 4 or len(t) > 160:
        return False
    return bool(HEADER_RE.match(t))


# ═══════════════════════════════════════════════════════════════
# SECTION 5 — اكتشاف Intent تلقائياً
# ═══════════════════════════════════════════════════════════════
INTENT_RULES: List[Tuple[List[str], str, str]] = [
    (["اشتراك جديد","تزود باشتراك","توصيل كهرباء","طلب اشتراك"],
     "اشتراك_جديد", "new_subscription"),
    (["1 فاز","3 فاز","فاز إلى","تحويل اشتراك","احادي الفاز","ثلاثي الفاز"],
     "تحويل_فاز", "phase_upgrade"),
    (["زيادة قدرة","قدرة اشتراك"],
     "زيادة_قدرة", "capacity_increase"),
    (["فصل اشتراك","فصل مؤقت"],
     "فصل_اشتراك", "disconnect"),
    (["اعادة وصل","ربط مجدد"],
     "اعادة_وصل", "reconnect"),
    (["تغيير تعرفة","تعرفة مؤقت","تعرفة دائم","تجاري الى منزلي"],
     "تغيير_تعرفة", "tariff_change"),
    (["مسبق الدفع","عداد مسبق","هولي","بطاقة شحن","كرت شحن"],
     "عداد_مسبق_الدفع", "prepaid_meter"),
    (["انهيميتر","عداد ذكي"],
     "عداد_ذكي", "smart_meter"),
    (["شحن","رصيد","وضع البطاقة","شحن العداد"],
     "شحن_رصيد", "recharge"),
    (["رصيد المتبقي","معرفة الرصيد","استعلام رصيد"],
     "استعلام_رصيد", "balance_inquiry"),
    (["يفصل العداد","العداد يفصل","قاطع","فصل تلقائي"],
     "عطل_قاطع", "meter_trip"),
    (["انقطاع الكهرباء","كهرباء مقطوعة","مقطوع"],
     "انقطاع", "outage"),
    (["عطل","خلل","لا يعمل","تعطل"],
     "عطل_عام", "fault_general"),
    (["طوارئ","خطر","عمود هادل"],
     "طوارئ", "emergency"),
    (["فاتورة","فواتير","سداد","دفع الفاتورة"],
     "فواتير", "billing"),
    (["تعرفة","سعر الكيلو","شريحة"],
     "تعرفة_وسعر", "tariff_price"),
    (["استهلاك عالي","فحص العداد","اعتراض"],
     "اعتراض_استهلاك", "consumption_dispute"),
    (["ترشيد","توفير كهرباء","توفير الطاقة"],
     "ترشيد_طاقة", "energy_saving"),
    (["بطاقة بدل فاقد","بدل تالف","فقد البطاقة"],
     "بدل_فاقد", "lost_card"),
    (["نقل عداد","تغيير موقع العداد"],
     "نقل_عداد", "meter_relocation"),
    (["تنازل","نقل ملكية","تغيير اسم"],
     "تنازل_اشتراك", "transfer_subscription"),
    (["إنارة شوارع","احبال زينه","مناسبات"],
     "انارة_شوارع", "street_lighting"),
    (["طاقة شمسية","سولار"],
     "طاقة_شمسية", "solar_energy"),
    (["رقم الهاتف","رقم التواصل","واتس","اتصل بنا","مقر الشركة"],
     "معلومات_تواصل", "contact_info"),
    (["شكوى","اعتراض على","تقديم شكوى"],
     "شكاوى", "complaints"),
    (["وثائق","مستندات","براءة ذمة"],
     "وثائق_مطلوبة", "required_docs"),
    (["تخفيض اقساط","جدولة ديون","تقسيط"],
     "جدولة_ديون", "debt_schedule"),
    (["ضعف التيار","ضغط منخفض"],
     "ضعف_تيار", "low_voltage"),
    (["صيانة","كيبل","مفتاح اوتوماتيك","فيوز"],
     "صيانة", "maintenance"),
]

def detect_intent(text: str) -> Tuple[str, str]:
    t = (text or "").lower()
    for kw_list, cat, intent in INTENT_RULES:
        for kw in kw_list:
            if kw in t:
                return cat, intent
    return "عام", "general"


# ═══════════════════════════════════════════════════════════════
# SECTION 6 — تقطيع الوثيقة إلى Chunks
# ═══════════════════════════════════════════════════════════════
SKIP_LINES = {
    "دليل خدمات المشتركين", "شركة كهرباء الخليل",
    "نشرة تعليمات للمشتركين", "نشرة تعليمات لعدادات الدفع المسبق",
    "معلومات هامة", "مقدمة",
}

def _split_long(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    sents = re.split(r"(?<=[.؟!\n])\s+", text)
    parts, buf = [], ""
    for s in sents:
        cand = (buf + " " + s).strip() if buf else s
        if len(cand) <= max_chars:
            buf = cand
        else:
            if buf:
                parts.append(buf)
            buf = s
    if buf:
        parts.append(buf)
    return parts or [text[:max_chars]]

def chunk_document(
    text: str,
    file_key: str,
    file_name: str = "",
    max_chars: int = 1400,   # FIX 1: من 850 → 1400 لتجنب قطع السياق
    min_chars: int = 40,
    overlap_chars: int = 150  # FIX 1: overlap بين chunks متجاورة
) -> List[Dict[str, Any]]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    chunks: List[Dict[str, Any]] = []
    current_title = ""
    current_body: List[str] = []
    current_page: int | None = None
    doc_prefix = f"وثيقة: {file_name or file_key}".strip()
    last_chunk_tail = ""  # FIX 1: نهاية آخر chunk للـ overlap

    def flush(title: str, body: List[str]) -> None:
        nonlocal last_chunk_tail
        body_text = " ".join(body).strip()
        page_line = f"صفحة: {current_page}" if current_page else ""
        head = " | ".join([p for p in [doc_prefix, page_line, title.strip()] if p])

        # FIX 1: أضف الـ overlap من الـ chunk السابق في البداية
        overlap_prefix = (last_chunk_tail + " ") if last_chunk_tail else ""
        full = (f"{head}\n{overlap_prefix}{body_text}" if body_text else head).strip()

        if len(full) < min_chars:
            return

        for sc in _split_long(full, max_chars):
            sc = sc.strip()
            if len(sc) < min_chars:
                continue
            cat, intent = detect_intent(title + " " + sc)
            cid = f"{file_key}_{len(chunks):04d}"
            chunks.append({
                "chunk_id": cid,
                "file": file_key,
                "text": sc,
                "metadata": {
                    "source_type": "text",
                    "file_name": file_name or file_key,
                    "section_title": title[:120],
                    "page": current_page,
                    "category": cat,
                    "intent": intent,
                    "keywords": extract_keywords(sc),
                    "source_file": file_key,
                    "char_count": len(sc),
                },
            })
            # FIX 1: احفظ نهاية هاد الـ chunk للـ overlap مع التالي
            last_chunk_tail = sc[-overlap_chars:].strip() if len(sc) > overlap_chars else ""

    for line in lines:
        if line in SKIP_LINES:
            continue
        if re.search(r"\t\d+\s*$", line):  # جدول محتويات
            continue

        mpage = re.match(r"^\[صفحة\s+(\d+)\]$", line)
        if mpage:
            try:
                current_page = int(mpage.group(1))
            except Exception:
                pass
            continue

        if is_header(line):
            flush(current_title, current_body)
            current_title = line
            current_body = []
        else:
            current_body.append(line)
            if sum(len(b) for b in current_body) > max_chars * 1.5:
                flush(current_title, current_body)
                current_body = []

    flush(current_title, current_body)
    return chunks


# ═══════════════════════════════════════════════════════════════
# SECTION 7 — Main
# ═══════════════════════════════════════════════════════════════
def build_index(data_dir: Path, out_path: Path, verbose: bool = False) -> List[Dict]:
    if not data_dir.exists():
        raise RuntimeError(f"المجلد غير موجود: {data_dir}")

    files = sorted([
        p for p in data_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in ALLOWED
        and not p.name.startswith("~$")
        and not p.name.startswith(".")
        and p.stat().st_size > 0
    ])

    if not files:
        raise RuntimeError(f"لا توجد ملفات مدعومة في: {data_dir}")

    print(f"\n{'='*55}")
    print(f"  📂 بناء RAG Index من: {data_dir}")
    print(f"  📄 عدد الملفات: {len(files)}")
    print(f"{'='*55}")

    all_chunks: List[Dict[str, Any]] = []
    seen: set[str] = set()
    errors = 0

    for fpath in files:
        print(f"\n  📄 {fpath.name}", end=" ... ", flush=True)
        try:
            ext = fpath.suffix.lower()

            if ext in {".xlsx", ".xls", ".csv"}:
                # ✅ Excel/CSV: كل صف = Document (بدون ما نعتمد على raw)
                doc_chunks = rows_to_documents(fpath, fpath.stem)
                if not doc_chunks:
                    print("⚠️ ما طلع ولا صف — تخطّي")
                    continue
            else:
                raw = (read_file(fpath) or "").strip()
                if not raw:
                    print("⚠️ فارغ — تخطّي")
                    continue
                doc_chunks = chunk_document(raw, fpath.stem, file_name=fpath.name)

        except Exception as e:
            print(f"❌ {e}")
            errors += 1
            continue

        added = 0
        for c in doc_chunks:
            h = hashlib.md5(c["text"].encode("utf-8")).hexdigest()
            if h not in seen:
                seen.add(h)
                all_chunks.append(c)
                added += 1

        print(f"✅ {added} chunk")

        if verbose:
            for c in doc_chunks[:10]:
                print(f"      [{c['metadata'].get('intent')}] {c['text'][:80]!r}")

    # ─── ملخص ───
    print(f"\n{'─'*55}")
    print(f"  ✅ إجمالي الـ chunks: {len(all_chunks)}")
    if errors:
        print(f"  ⚠️  ملفات فشلت: {errors}")

    if all_chunks:
        cats = Counter(c["metadata"]["category"] for c in all_chunks)
        print("\n  📊 توزيع الفئات:")
        for cat, n in cats.most_common():
            bar = "█" * min(n, 25)
            print(f"     {cat:<28} {bar} {n}")

    # ─── حفظ ───
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    size_kb = out_path.stat().st_size // 1024
    print(f"\n  💾 تم الحفظ: {out_path}  ({size_kb} KB)")
    print("  🚀 الخطوة التالية: python build_embeddings.py --overwrite\n")

    return all_chunks


def main():
    ap = argparse.ArgumentParser(
        description="بناء rag_index.json من ملفات مجلد data/"
    )
    ap.add_argument("--data",    default=None, help="مجلد الملفات (default: data/)")
    ap.add_argument("--out",     default=None, help="مسار الـ output (default: rag_index.json)")
    ap.add_argument("--verbose", action="store_true", help="اعرض كل chunk")
    args = ap.parse_args()

    base     = Path(__file__).resolve().parent
    data_dir = Path(args.data) if args.data else base / "data"
    out_path = Path(args.out)  if args.out  else base / "rag_index.json"

    build_index(data_dir, out_path, verbose=args.verbose)


if __name__ == "__main__":
    main()
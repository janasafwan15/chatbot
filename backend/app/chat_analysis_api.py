# backend/app/chat_analysis_api.py
"""
تحليل سجل المحادثات:
  - أكثر المشاكل المطروحة (بناءً على intent_pred + keywords)
  - أكثر الأحياء/المناطق التي تشتكي (NLP بسيط من نص السؤال)
  - اتجاهات يومية/أسبوعية
  - الأسئلة الأكثر تكراراً
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request

from .db import connect
from .auth import require_auth
from .rbac import require_roles

router = APIRouter(prefix="/stats", tags=["chat-analysis"])


def _auth_stats(request: Request):
    user = require_auth(request)
    require_roles(user, ["admin", "supervisor", "employee"])
    return user


def _q_rows(sql: str, params: tuple = ()) -> list[dict]:
    con = connect()
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def _q_scalar(sql: str, params: tuple = ()):
    con = connect()
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return next(iter(row.values())) if row else None
    finally:
        con.close()


# ── قائمة الأحياء والمناطق المعروفة فقط ──────────────────────
# ⚠️ لا تضف كلمات عامة هنا (حي، حارة، شارع...) — تسبب false positives
NEIGHBORHOOD_KEYWORDS = [
    # مدن وبلدات محافظة الخليل
    "الخليل", "البلدة القديمة", "وادي الهريية", "الحي الإسلامي", "الرشيدية",
    "الزاوية", "بيت كاحل", "صيدا", "نوبا", "يطا", "دورا", "سعير",
    "الظاهرية", "بني نعيم", "ترقوميا", "حلحول", "إذنا",
    "الشيوخ", "كرمة", "زيف", "الفوار", "المسافر", "عين سارة",
    "عبدة", "الرامة", "المدبح", "المستقبل", "الحي الجنوبي",
    "أبو سنينة", "جبل جوهر", "الزاهرية", "عيون الحرامية",
    "الديماس", "الصناعية", "الريحية", "قلقيلية", "بيت أمر",
    "بيت عوا", "بيت الروش", "السموع", "شيوخ العروب",
    "خرسا", "طرمة", "حبلة", "الشيوخ", "دير سامت",
    "بيت مرسيم", "الرهاوية", "حوسان", "بيت جبرين",
]

# ── كلمات مستبعدة — لا تُقبل كأسماء أحياء أبداً ──────────────
_NEIGHBORHOOD_BLACKLIST = {
    "حي", "حارة", "منطقة", "شارع", "قرية", "مخيم",
    "كهرباء", "تيار", "عداد", "فاتورة", "شبكة",
    "مشكلة", "عطل", "انقطاع", "خدمة", "طلب",
    "سعر", "كيلو", "واط", "أمبير", "فولت",
    "يوم", "ساعة", "شهر", "أسبوع",
    "بيت", "منزل", "مبنى", "طابق", "شقة",
    "عندي", "عندنا", "عندهم", "المنطقة", "المكان",
}

# ── أنماط regex — مقيّدة بسياق واضح ─────────────────────────
_HOOD_PATTERNS = [
    # "حي X" أو "حارة X" — كلمة واحدة فقط بعد حي/حارة
    re.compile(r"(?:حي|حارة)\s+([\u0600-\u06FF]{3,20})\s*(?:$|[،,\.\?]|(?=\s+(?:كيف|ما|هل|أين|متى|لماذا|أريد|بدي|ممكن|عندي|فيها|فيه|يوجد)))", re.UNICODE),
    # "حي اسم1 اسم2" للأسماء المركبة — مقيّد بأن الكلمة الثانية لا تكون فعلاً
    re.compile(r"(?:حي|حارة)\s+([\u0600-\u06FF]{3,20}\s+[\u0600-\u06FF]{2,15})(?:\s+(?:الكهرباء|فيها|فيه|انقطع|مقطوع|عندنا|عندي))", re.UNICODE),
    # "في منطقة X" أو "من منطقة X"
    re.compile(r"(?:في|من)\s+منطقة\s+([\u0600-\u06FF]{3,20}(?:\s+[\u0600-\u06FF]{2,15})?)", re.UNICODE),
    # "في X" حيث X كلمة واحدة من 4-15 حرف — أكثر تقييداً من السابق
    re.compile(r"(?:في|من)\s+([\u0600-\u06FF]{4,15})\s+(?:الكهرباء|انقطعت|مقطوعة|مشكلة)", re.UNICODE),
]


def _extract_neighborhood(text: str) -> Optional[str]:
    """
    يستخرج اسم الحي/المنطقة من النص.
    يعتمد أولاً على قائمة الأسماء المعروفة، ثم الـ regex بشروط صارمة.
    """
    if not text:
        return None

    # 1) ابحث عن اسم معروف من القائمة (الأدق والأأمن)
    for kw in NEIGHBORHOOD_KEYWORDS:
        if kw in text:
            return kw

    # 2) جرّب الـ regex مع فلترة النتائج
    for pat in _HOOD_PATTERNS:
        m = pat.search(text)
        if m:
            candidate = m.group(1).strip()
            # استبعد الكلمات العامة والقصيرة
            if candidate and candidate not in _NEIGHBORHOOD_BLACKLIST and len(candidate) >= 3:
                # تأكد إنها مش مجرد كلمة شائعة (عدد الحروف الفريدة > 3)
                if len(set(candidate.replace(" ", ""))) > 3:
                    return candidate

    return None


# ══════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════

@router.get("/chat-problems")
def chat_problems(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(15, ge=1, le=50),
    _user=Depends(_auth_stats),
):
    """
    أكثر المشاكل التي يسأل عنها المواطنون.
    يجمع: intent_pred + response_mode + تحليل الكلمات المفتاحية.
    """
    # 1) أكثر الـ intents
    intent_rows = _q_rows(
        """
        SELECT
            COALESCE(intent_pred, 'unknown') AS problem,
            COUNT(*) AS count,
            ROUND(AVG(CASE WHEN answer_found=1 THEN 1.0 ELSE 0 END)*100,1) AS resolved_pct
        FROM message
        WHERE message_type = 'assistant'
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY intent_pred
        ORDER BY count DESC
        LIMIT %s
        """,
        (days, limit),
    )

    # 2) الأسئلة بدون إجابة (fallback) — دليل على فجوات في KB
    unanswered = _q_scalar(
        """
        SELECT COUNT(*) FROM message
        WHERE message_type='assistant'
          AND (answer_found=0 OR response_mode LIKE '%%fallback%%')
          AND created_at >= NOW() - INTERVAL '%s days'
        """,
        (days,),
    ) or 0

    total = _q_scalar(
        "SELECT COUNT(*) FROM message WHERE message_type='assistant' AND created_at >= NOW() - INTERVAL '%s days'",
        (days,),
    ) or 1

    # 3) أكثر الكلمات المفتاحية في الأسئلة (بعد stopwords)
    questions_sample = _q_rows(
        """
        SELECT message_text FROM message
        WHERE message_type='assistant'
          AND message_text IS NOT NULL
          AND created_at >= NOW() - INTERVAL '%s days'
        LIMIT 500
        """,
        (days,),
    )
    keyword_counts = _extract_keywords([r["message_text"] for r in questions_sample])

    return {
        "days": days,
        "total_messages": int(total),
        "unanswered_count": int(unanswered),
        "unanswered_rate": round(int(unanswered) / int(total) * 100, 1),
        "top_problems": intent_rows,
        "top_keywords": keyword_counts[:20],
    }


@router.get("/neighborhood-complaints")
def neighborhood_complaints(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(15, ge=1, le=50),
    _user=Depends(_auth_stats),
):
    """
    أكثر الأحياء/المناطق التي تشتكي — يستخرج اسم الحي من نص السؤال.
    """
    rows = _q_rows(
        """
        SELECT message_text, intent_pred, answer_found, created_at
        FROM message
        WHERE message_type='assistant'
          AND message_text IS NOT NULL
          AND created_at >= NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
        LIMIT 2000
        """,
        (days,),
    )

    hood_counter: Counter = Counter()
    hood_intent_map: dict = {}   # حي → أكثر intent

    for row in rows:
        text = (row.get("message_text") or "").strip()
        hood = _extract_neighborhood(text)
        if hood:
            hood_counter[hood] += 1
            intent = row.get("intent_pred") or "unknown"
            if hood not in hood_intent_map:
                hood_intent_map[hood] = Counter()
            hood_intent_map[hood][intent] += 1

    result = []
    for hood, count in hood_counter.most_common(limit):
        top_intent = hood_intent_map[hood].most_common(1)[0][0] if hood in hood_intent_map else "unknown"
        result.append({
            "neighborhood": hood,
            "complaints": count,
            "top_problem": top_intent,
        })

    return {
        "days": days,
        "total_analyzed": len(rows),
        "neighborhoods_found": len(hood_counter),
        "top_neighborhoods": result,
    }


@router.get("/questions-trend")
def questions_trend(
    days: int = Query(30, ge=1, le=365),
    _user=Depends(_auth_stats),
):
    """
    اتجاه أسئلة المواطنين يومياً — مفيد لرؤية ارتفاع الشكاوى.
    """
    rows = _q_rows(
        """
        SELECT
            DATE(created_at) AS day,
            COUNT(*) AS total_questions,
            SUM(CASE WHEN answer_found=1 THEN 1 ELSE 0 END) AS answered,
            SUM(CASE WHEN answer_found=0 OR response_mode LIKE '%%fallback%%' THEN 1 ELSE 0 END) AS unanswered,
            ROUND(AVG(CASE WHEN best_score IS NULL THEN 0 ELSE best_score END)::numeric, 3) AS avg_confidence
        FROM message
        WHERE message_type='assistant'
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(created_at)
        ORDER BY day ASC
        """,
        (days,),
    )
    return {"days": days, "daily": rows}


@router.get("/repeated-questions")
def repeated_questions(
    days: int = Query(30, ge=1, le=365),
    min_count: int = Query(3, ge=2, le=50),
    limit: int = Query(20, ge=1, le=100),
    _user=Depends(_auth_stats),
):
    """
    الأسئلة الأكثر تكراراً — مهمة لتحسين قاعدة المعرفة.
    """
    rows = _q_rows(
        """
        SELECT
            message_text AS question,
            COUNT(*) AS count,
            ROUND(AVG(CASE WHEN answer_found=1 THEN 1.0 ELSE 0 END)*100, 1) AS resolved_pct,
            MAX(created_at) AS last_asked
        FROM message
        WHERE message_type='assistant'
          AND message_text IS NOT NULL
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY message_text
        HAVING COUNT(*) >= %s
        ORDER BY count DESC
        LIMIT %s
        """,
        (days, min_count, limit),
    )
    return {"days": days, "min_count": min_count, "questions": rows}


@router.get("/intent-hourly-heatmap")
def intent_hourly_heatmap(
    days: int = Query(7, ge=1, le=90),
    _user=Depends(_auth_stats),
):
    """
    هيت ماب: intent × ساعة اليوم.
    يُظهر متى يكثر كل نوع من الأسئلة.
    """
    rows = _q_rows(
        """
        SELECT
            COALESCE(intent_pred, 'unknown') AS intent,
            EXTRACT(HOUR FROM created_at)::int AS hour,
            COUNT(*) AS count
        FROM message
        WHERE message_type='assistant'
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY intent_pred, hour
        ORDER BY intent, hour
        """,
        (days,),
    )
    return {"days": days, "heatmap": rows}


# ── Helper: استخراج الكلمات المفتاحية ────────────────────────
ARABIC_STOPWORDS = {
    "في", "من", "على", "إلى", "عن", "مع", "هل", "كيف", "ما",
    "لماذا", "متى", "أين", "لو", "إذا", "هذا", "هذه", "الذي",
    "التي", "كان", "يكون", "أن", "أو", "لكن", "لم", "لا", "نعم",
    "أنا", "أنت", "نحن", "هم", "هي", "هو", "بس", "يعني", "بدي",
    "بدنا", "عندي", "عندنا", "ممكن", "لازم", "عشان", "الكهرباء",
    "كهرباء", "شركة", "شو", "وين", "ليش",
}

def _extract_keywords(texts: List[str]) -> list:
    counter: Counter = Counter()
    for text in texts:
        if not text:
            continue
        words = re.findall(r"[\u0600-\u06FF]{3,}", text)
        for w in words:
            if w not in ARABIC_STOPWORDS:
                counter[w] += 1
    return [{"word": w, "count": c} for w, c in counter.most_common(50)]
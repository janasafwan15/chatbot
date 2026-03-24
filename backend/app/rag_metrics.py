# backend/app/rag_metrics.py
"""
مقاييس جودة الـ RAG:
  - Precision@K  : من الـ K مستندات المسترجعة، كم منها ذات صلة؟
  - Recall@K     : من كل المستندات الصحيحة، كم نسبة ما استرجعناه؟
  - F1@K         : التوازن بين Precision و Recall
  - MRR          : Mean Reciprocal Rank — أين وُجد أول مستند صحيح؟
  - Hit@K        : هل وُجد مستند صحيح ضمن أفضل K نتيجة؟

يُستخدم لقياس جودة الـ retrieval من قاعدة المعرفة.
يحفظ النتائج في جدول rag_eval_log بالـ DB.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────

@dataclass
class RetrievalEval:
    """نتيجة تقييم استرجاع واحد"""
    question: str
    retrieved_ids: List[str]        # chunk_ids اللي رجعها النظام
    relevant_ids: List[str]         # chunk_ids الصحيحة (ground truth)
    k: int = 5

    # ── computed ──
    precision: float = field(init=False)
    recall: float = field(init=False)
    f1: float = field(init=False)
    mrr: float = field(init=False)
    hit_at_k: bool = field(init=False)

    def __post_init__(self):
        self.precision = _precision(self.retrieved_ids[:self.k], self.relevant_ids)
        self.recall    = _recall(self.retrieved_ids[:self.k], self.relevant_ids)
        self.f1        = _f1(self.precision, self.recall)
        self.mrr       = _mrr(self.retrieved_ids[:self.k], self.relevant_ids)
        self.hit_at_k  = _hit(self.retrieved_ids[:self.k], self.relevant_ids)

    def to_dict(self) -> dict:
        return {
            "question":      self.question,
            "k":             self.k,
            "precision":     round(self.precision, 4),
            "recall":        round(self.recall, 4),
            "f1":            round(self.f1, 4),
            "mrr":           round(self.mrr, 4),
            "hit_at_k":      self.hit_at_k,
            "retrieved_ids": self.retrieved_ids[:self.k],
            "relevant_ids":  self.relevant_ids,
        }


# ── Core metric functions ────────────────────────────────────

def _precision(retrieved: List[str], relevant: List[str]) -> float:
    if not retrieved:
        return 0.0
    rel_set = set(relevant)
    hits = sum(1 for r in retrieved if r in rel_set)
    return hits / len(retrieved)


def _recall(retrieved: List[str], relevant: List[str]) -> float:
    if not relevant:
        return 1.0  # لا توجد مستندات صحيحة → recall = 1 بالاصطلاح
    rel_set = set(relevant)
    hits = sum(1 for r in retrieved if r in rel_set)
    return hits / len(relevant)


def _f1(precision: float, recall: float) -> float:
    denom = precision + recall
    if denom == 0:
        return 0.0
    return 2 * precision * recall / denom


def _mrr(retrieved: List[str], relevant: List[str]) -> float:
    rel_set = set(relevant)
    for rank, rid in enumerate(retrieved, start=1):
        if rid in rel_set:
            return 1.0 / rank
    return 0.0


def _hit(retrieved: List[str], relevant: List[str]) -> bool:
    rel_set = set(relevant)
    return any(r in rel_set for r in retrieved)


# ── Aggregate over a batch ────────────────────────────────────

def aggregate_evals(evals: List[RetrievalEval]) -> dict:
    """يحسب المتوسطات على مجموعة تقييمات"""
    if not evals:
        return {"count": 0, "precision": 0, "recall": 0, "f1": 0, "mrr": 0, "hit_rate": 0}
    n = len(evals)
    return {
        "count":     n,
        "precision": round(sum(e.precision for e in evals) / n, 4),
        "recall":    round(sum(e.recall    for e in evals) / n, 4),
        "f1":        round(sum(e.f1        for e in evals) / n, 4),
        "mrr":       round(sum(e.mrr       for e in evals) / n, 4),
        "hit_rate":  round(sum(1 for e in evals if e.hit_at_k) / n, 4),
    }


# ── Automatic eval from live chat ────────────────────────────

def eval_from_rag_result(
    question: str,
    retrieved_chunk_ids: List[str],
    best_score: Optional[float],
    answer_found: bool,
    k: int = 5,
) -> dict:
    """
    تقييم تقريبي (proxy) بدون ground truth:
    - نعتبر المستند الأول "صحيح" لو best_score >= threshold
    - يُستخدم لتتبع اتجاهات الجودة في الـ DB
    """
    SCORE_THRESHOLD = 0.38
    if answer_found and best_score and best_score >= SCORE_THRESHOLD:
        relevant_ids = retrieved_chunk_ids[:1]  # نفترض أن الأول صحيح
    else:
        relevant_ids = []

    ev = RetrievalEval(
        question=question,
        retrieved_ids=retrieved_chunk_ids,
        relevant_ids=relevant_ids,
        k=k,
    )
    return ev.to_dict()


# ── DB persistence ────────────────────────────────────────────

def save_eval_to_db(
    eval_dict: dict,
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> None:
    """يحفظ نتائج التقييم في جدول rag_eval_log"""
    try:
        from .db import connect
        con = connect()
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO rag_eval_log
                (question, k, precision_k, recall_k, f1_k, mrr, hit_at_k,
                 retrieved_ids_json, relevant_ids_json,
                 conversation_id, message_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
            """,
            (
                (eval_dict.get("question") or "")[:500],
                eval_dict.get("k", 5),
                eval_dict.get("precision", 0),
                eval_dict.get("recall", 0),
                eval_dict.get("f1", 0),
                eval_dict.get("mrr", 0),
                1 if eval_dict.get("hit_at_k") else 0,
                json.dumps(eval_dict.get("retrieved_ids", []), ensure_ascii=False),
                json.dumps(eval_dict.get("relevant_ids", []), ensure_ascii=False),
                conversation_id,
                message_id,
                datetime.utcnow().isoformat(),
            ),
        )
        con.commit()
        con.close()
    except Exception as e:
        logger.warning(f"[rag_metrics] failed to save eval: {e}")


# ── DB schema migration helper ────────────────────────────────

RAG_EVAL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rag_eval_log (
    id                  SERIAL PRIMARY KEY,
    question            TEXT,
    k                   INT,
    precision_k         FLOAT,
    recall_k            FLOAT,
    f1_k                FLOAT,
    mrr                 FLOAT,
    hit_at_k            INT,
    retrieved_ids_json  TEXT,
    relevant_ids_json   TEXT,
    conversation_id     INT,
    message_id          INT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rag_eval_created ON rag_eval_log(created_at);
CREATE INDEX IF NOT EXISTS idx_rag_eval_conv    ON rag_eval_log(conversation_id);
"""


def ensure_eval_table() -> None:
    """ينشئ جدول rag_eval_log لو مش موجود"""
    try:
        from .db import connect
        con = connect()
        cur = con.cursor()
        for stmt in RAG_EVAL_TABLE_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        con.commit()
        con.close()
        logger.info("[rag_metrics] rag_eval_log table ready")
    except Exception as e:
        logger.warning(f"[rag_metrics] ensure_eval_table failed: {e}")

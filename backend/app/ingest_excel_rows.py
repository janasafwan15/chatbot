from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .db import connect


def ingest_excel_rows(path: str) -> int:
    """
    Ingest an Excel KB (output) into SQLite as row-as-document.
    Expected columns:
      - الموضوع الرئيسي (Main Entity)
      - العنوان الفرعي (Subtopic)
      - التفاصيل (Explicit Context for RAG)
    """
    p = Path(path).resolve()
    source_file = p.name

    con = connect()
    cur = con.cursor()

    xl = pd.ExcelFile(str(p))
    n = 0

    for sheet in xl.sheet_names:
        df = xl.parse(sheet).fillna("")

        for i, row in df.iterrows():
            main = str(row.get("الموضوع الرئيسي (Main Entity)", "")).strip()
            sub = str(row.get("العنوان الفرعي (Subtopic)", "")).strip()
            det = str(row.get("التفاصيل (Explicit Context for RAG)", "")).strip()

            if len(det) < 15:
                continue

            text = (
                f"الموضوع الرئيسي: {main}\n"
                f"العنوان الفرعي: {sub}\n"
                f"التفاصيل: {det}\n"
                f"[مرجع]: ملف={source_file} | شيت={sheet} | صف={i+1}"
            ).strip()

            meta = {
                "source_type": "excel",
                "source_file": source_file,
                "sheet_name": sheet,
                "row_index": int(i + 1),
                "main_entity": main,
                "subtopic": sub,
            }

            chunk_id = f"{source_file}::{sheet}::row{i+1}"

            cur.execute(
                """
                INSERT INTO rag_chunk (chunk_id, source_file, text, metadata_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO UPDATE SET
                  source_file=EXCLUDED.source_file,
                  text=EXCLUDED.text,
                  metadata_json=EXCLUDED.metadata_json
                """,
                (chunk_id, source_file, text, json.dumps(meta, ensure_ascii=False)),
            )
            n += 1

    con.commit()
    con.close()
    return n
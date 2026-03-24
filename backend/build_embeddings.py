"""Build and store embeddings for rag_index.json chunks into DB.

Usage:
  python build_index.py               # creates rag_index.json
  python build_embeddings.py          # stores chunks + embeddings in DB
  python build_embeddings.py --overwrite

Env (recommended):

  # ===== Database =====
  DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/hepco_db

  # ===== LLM (via Ollama endpoint) =====
  OLLAMA_BASE=http://127.0.0.1:11434
  LLM_MODEL=deepseek-v3.1:671b-cloud

  # ===== Embeddings (via Ollama endpoint) =====
  EMBED_PROVIDER=ollama
  EMBED_MODEL=bge-m3
  EMBED_BASE=http://127.0.0.1:11434
"""

from __future__ import annotations

import argparse
from dotenv import load_dotenv

load_dotenv()

from app.rag_engine import build_embeddings, ping_embeddings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if not ping_embeddings():
        print("❌ Embeddings backend not ready. Check EMBED_PROVIDER / EMBED_BASE / EMBED_MODEL.")
        return

    res = build_embeddings(limit=args.limit, overwrite=args.overwrite)
    print("✅ Done")
    for k, v in res.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
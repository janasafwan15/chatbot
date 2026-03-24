from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ===== Bases / Keys =====
OLLAMA_BASE     = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_API_KEY  = os.getenv("OLLAMA_API_KEY", "").strip()

EMBED_BASE      = os.getenv("EMBED_BASE", OLLAMA_BASE).rstrip("/")
EMBED_API_KEY   = os.getenv("EMBED_API_KEY", os.getenv("OLLAMA_API_KEY", "")).strip()

# ===== Models =====
LLM_MODEL       = os.getenv("LLM_MODEL", "deepseek-v3.1:671b-cloud").strip()
LLM_FALLBACK    = os.getenv("LLM_FALLBACK_MODEL", "").strip()   # موديل احتياطي لو الأساسي فشل
EMBED_MODEL     = os.getenv("EMBED_MODEL", "bge-m3").strip()

# ===== Timeouts =====
OLLAMA_TIMEOUT  = int(os.getenv("OLLAMA_TIMEOUT", "180"))
EMBED_TIMEOUT   = int(os.getenv("EMBED_TIMEOUT", "120"))

# ===== Retry =====
LLM_RETRIES     = int(os.getenv("LLM_RETRIES", "2"))       # عدد المحاولات قبل الفشل
LLM_RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", "2")) # ثواني بين المحاولات


def _headers(api_key: str = "") -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if (api_key or "").strip():
        h["Authorization"] = f"Bearer {api_key}"
    return h


# ===============================
# Health
# ===============================
def get_ok(path: str, *, timeout: int = 10) -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}{path}", headers=_headers(OLLAMA_API_KEY), timeout=timeout)
        return bool(r.ok)
    except Exception:
        return False


# ===============================
# Internal: single attempt
# ===============================
def _post_once(base: str, api_key: str, path: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """محاولة واحدة — بدون retry."""
    url = f"{base}{path}"
    r = requests.post(url, headers=_headers(api_key), json=payload, timeout=timeout)

    # fallback: /api/chat → /api/generate لو endpoint مش موجود
    if r.status_code == 404 and path == "/api/chat":
        messages = payload.get("messages") or []
        prompt = "\n\n".join(
            f"{(m.get('role') or '').strip()}:\n{(m.get('content') or '').strip()}"
            for m in messages if (m.get("content") or "").strip()
        ).strip()
        gen_payload = {
            "model": payload.get("model"),
            "prompt": prompt,
            "stream": False,
            "options": payload.get("options") or {},
        }
        r = requests.post(
            f"{base}/api/generate",
            headers=_headers(api_key),
            json=gen_payload,
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json() or {}
        return {"message": {"content": (data.get("response") or "").strip()}}

    r.raise_for_status()
    return r.json() or {}


# ===============================
# Generic POST JSON — مع Retry + Fallback Model
# ===============================
def post_json(path: str, payload: Dict[str, Any], *, timeout: int = 60) -> Dict[str, Any]:
    """
    POST JSON لـ Ollama مع:
    - Retry تلقائي (LLM_RETRIES مرات مع delay)
    - Fallback لموديل احتياطي (LLM_FALLBACK_MODEL) لو الأساسي فشل كلياً
    """
    last_exc: Exception | None = None

    # ── المحاولات على الموديل الأساسي ──
    for attempt in range(1, LLM_RETRIES + 1):
        try:
            return _post_once(OLLAMA_BASE, OLLAMA_API_KEY, path, payload, timeout)
        except Exception as e:
            last_exc = e
            logger.warning(
                f"[ollama] attempt {attempt}/{LLM_RETRIES} failed: {type(e).__name__}: {e}"
            )
            if attempt < LLM_RETRIES:
                time.sleep(LLM_RETRY_DELAY)

    # ── Fallback Model ──
    if LLM_FALLBACK and payload.get("model") != LLM_FALLBACK:
        logger.warning(
            f"[ollama] primary model failed after {LLM_RETRIES} attempts, "
            f"switching to fallback: {LLM_FALLBACK}"
        )
        fallback_payload = {**payload, "model": LLM_FALLBACK}
        try:
            result = _post_once(OLLAMA_BASE, OLLAMA_API_KEY, path, fallback_payload, timeout)
            logger.info(f"[ollama] fallback model succeeded: {LLM_FALLBACK}")
            return result
        except Exception as fe:
            logger.error(f"[ollama] fallback model also failed: {type(fe).__name__}: {fe}")
            raise RuntimeError(
                f"Both primary ({payload.get('model')}) and fallback ({LLM_FALLBACK}) models failed. "
                f"Last error: {fe}"
            ) from fe

    raise RuntimeError(
        f"Ollama model {payload.get('model')} failed after {LLM_RETRIES} attempts. "
        f"Last error: {last_exc}"
    ) from last_exc


# ===============================
# LLM convenience
# ===============================
def generate(system: str, prompt: str) -> str:
    data = post_json(
        "/api/chat",
        {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        },
        timeout=OLLAMA_TIMEOUT,
    )
    return ((data.get("message") or {}).get("content") or "").strip()


# ===============================
# Embeddings convenience
# ===============================
def embed(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return []

    # 1) /api/embed (new)
    try:
        r = requests.post(
            f"{EMBED_BASE}/api/embed",
            headers=_headers(EMBED_API_KEY),
            json={"model": EMBED_MODEL, "input": text},
            timeout=EMBED_TIMEOUT,
        )
        if r.ok:
            data = r.json() or {}
            if data.get("embeddings"):
                return data["embeddings"][0]
            if data.get("embedding"):
                return data["embedding"]
    except Exception:
        pass

    # 2) /api/embeddings (old)
    try:
        r2 = requests.post(
            f"{EMBED_BASE}/api/embeddings",
            headers=_headers(EMBED_API_KEY),
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=EMBED_TIMEOUT,
        )
        if r2.ok:
            data2 = r2.json() or {}
            if data2.get("embedding"):
                return data2["embedding"]
    except Exception:
        pass

    # 3) /v1/embeddings (OpenAI-compatible)
    try:
        r3 = requests.post(
            f"{EMBED_BASE}/v1/embeddings",
            headers=_headers(EMBED_API_KEY),
            json={"model": EMBED_MODEL, "input": text},
            timeout=EMBED_TIMEOUT,
        )
        if r3.ok:
            data3 = r3.json() or {}
            if data3.get("data") and data3["data"][0].get("embedding"):
                return data3["data"][0]["embedding"]
    except Exception:
        pass

    raise RuntimeError(
        f"Embeddings failed on {EMBED_BASE} for model={EMBED_MODEL}. "
        "Tried: /api/embed, /api/embeddings, /v1/embeddings"
    )
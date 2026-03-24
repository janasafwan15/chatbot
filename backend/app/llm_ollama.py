from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        h["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
    return h


def get_ok(path: str, *, timeout: int = 10) -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}{path}", headers=_headers(), timeout=timeout)
        return bool(r.ok)
    except Exception:
        return False


def post_json(path: str, payload: Dict[str, Any], *, timeout: int = 60) -> Dict[str, Any]:
    url = f"{OLLAMA_BASE}{path}"
    r = requests.post(url, headers=_headers(), json=payload, timeout=timeout)

    # ✅ لو /api/chat مش موجود، جرّبي /api/generate
    if r.status_code == 404 and path == "/api/chat":
        # حول messages => prompt
        messages = payload.get("messages") or []
        prompt_parts = []
        for m in messages:
            role = (m.get("role") or "").strip()
            content = (m.get("content") or "").strip()
            if content:
                prompt_parts.append(f"{role}:\n{content}")
        prompt = "\n\n".join(prompt_parts).strip()

        gen_payload = {
            "model": payload.get("model"),
            "prompt": prompt,
            "stream": False,
            "options": payload.get("options") or {},
        }

        r = requests.post(f"{OLLAMA_BASE}/api/generate", headers=_headers(), json=gen_payload, timeout=timeout)

        r.raise_for_status()
        data = r.json() or {}
        # شكل generate بيرجع response بدل message.content
        return {"message": {"content": (data.get("response") or "").strip()}}

    r.raise_for_status()
    return r.json() or {}
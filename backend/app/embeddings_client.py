from __future__ import annotations
from .ollama_client import embed

def get_embedding(text: str):
    return embed(text)
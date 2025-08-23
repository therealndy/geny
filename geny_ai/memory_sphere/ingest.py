"""Ingestion pipeline stubs: text/audio/image to embeddings.

Phase v0: only text ingest; audio/image behind feature flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TextChunk:
    text: str
    meta: dict


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def chunk_text(text: str, max_len: int = 512) -> List[str]:
    words = text.split()
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if sum(len(x) + 1 for x in cur) > max_len:
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks

"""MemorySphere service: simple in-memory vector store and ingestion.

Phase v0: text-only ingestion using normalize/chunk, naive search.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .ingest import chunk_text, normalize_text
from .vectorstore import VectorStore


@dataclass
class MemorySphereService:
    vs: VectorStore

    def ingest_text(self, text: str, meta: Dict[str, Any] | None = None) -> int:
        meta = meta or {}
        norm = normalize_text(text)
        chunks = chunk_text(norm)
        items = [(c, {**meta, "len": len(c)}) for c in chunks]
        self.vs.add(items)
        return len(items)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        results = self.vs.search(query, top_k=k)
        return [{"text": t, "meta": m} for (t, m) in results]


_SERVICE = MemorySphereService(vs=VectorStore())


def get_service() -> MemorySphereService:
    return _SERVICE

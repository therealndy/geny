"""Vector store adapter – lightweight and dependency-free for v0.

Implements a naive token-set (Jaccard) similarity for ranking, with
substring fallback. Designed to be easily replaceable by Chroma/FAISS later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def _tokens(s: str) -> List[str]:
    # Simple alnum tokenizer
    out = []
    cur = []
    for ch in s.lower():
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out


def _jaccard(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    if inter == 0:
        return 0.0
    union = len(sa | sb)
    return inter / union if union else 0.0


@dataclass
class VectorStore:
    backend: str = "memory"  # "memory" | "tfidf"
    store: List[Tuple[str, Dict]] = None
    _tfidf_index: Optional[object] = None  # lazy-built
    _cache: Optional[dict] = None
    _write_version: int = 0

    def __post_init__(self):
        self.store = []
        # Allow override by env for quick experiments
        be = os.environ.get("GENY_MS_BACKEND")
        if be in {"memory", "tfidf"}:
            self.backend = be
        # init cache structure
        self._cache = {}

    def add(self, items: List[Tuple[str, dict]]):
        # items: [(text, meta)]
        self.store.extend(items)
        # Invalidate tfidf index on writes
        self._tfidf_index = None
        # Bump version to invalidate cache cheaply
        self._write_version += 1
        if self._cache is not None:
            self._cache.clear()

    def _ensure_tfidf(self):
        if self._tfidf_index is not None:
            return
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except Exception:
            # Fallback to memory backend if sklearn is not available
            self.backend = "memory"
            self._tfidf_index = None
            return
        texts = [t for (t, _m) in self.store]
        vec = TfidfVectorizer()
        mat = vec.fit_transform(texts) if texts else None
        self._tfidf_index = (vec, mat)

    def _search_memory(self, query: str, top_k: int) -> List[Tuple[str, dict]]:
        # Rank by Jaccard over tokens, fallback to substring
        q_tokens = _tokens(query)
        scored: List[Tuple[float, Tuple[str, dict]]] = []
        for t, m in self.store:
            score = _jaccard(q_tokens, _tokens(t))
            if score == 0.0 and query.lower() in t.lower():
                score = 0.01  # minimal bump for substring
            if score > 0.0:
                scored.append((score, (t, m)))
        if not scored:
            # return substring matches if any
            q = query.lower()
            hits = [(t, m) for (t, m) in self.store if q in t.lower()]
            return hits[:top_k]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [pair for (_, pair) in scored[:top_k]]

    def _search_tfidf(self, query: str, top_k: int) -> List[Tuple[str, dict]]:
        self._ensure_tfidf()
        if self._tfidf_index is None:
            # sklearn not available or no data; fallback
            return self._search_memory(query, top_k)

        vec, mat = self._tfidf_index
        if mat is None or mat.shape[0] == 0:
            return []
        qv = vec.transform([query])
        # TfidfVectorizer uses L2 norm by default, so dot product yields cosine sim
        sims = (qv @ mat.T).toarray()[0]
        idxs = sims.argsort()[::-1]
        results: List[Tuple[str, dict]] = []
        for i in idxs[:top_k]:
            results.append(self.store[int(i)])
        return results

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, dict]]:
        # Simple in-process cache; disabled if env says so
        if os.environ.get("GENY_MS_CACHE", "1") not in {"0", "false", "False"}:
            key = (self.backend, self._write_version, query, int(top_k))
            hit = self._cache.get(key) if self._cache is not None else None
            if hit is not None:
                return hit
            if self.backend == "tfidf":
                res = self._search_tfidf(query, top_k)
            else:
                res = self._search_memory(query, top_k)
            if self._cache is not None:
                self._cache[key] = res
            return res
        # Cache disabled
        if self.backend == "tfidf":
            return self._search_tfidf(query, top_k)
        return self._search_memory(query, top_k)

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class VectorStore:
    """Minimal vector store wrapper using sentence-transformers + faiss.

    This implementation uses lazy imports so the repository can be imported
    without having the heavy ML dependencies installed. If you call methods
    that require embeddings/indexing and dependencies are missing, a
    RuntimeError will be raised with a hint to install extras.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        base = persist_dir or os.environ.get("GENY_DATA_DIR") or "data/vectorstore"
        self.persist_dir = Path(base)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self._model = None
        self._index = None
        self._metadata: List[Dict] = []
        self._meta_path = self.persist_dir / "metadata.json"
        self._index_path = self.persist_dir / "index.faiss"
        # try to load metadata if present
        if self._meta_path.exists():
            try:
                self._metadata = json.loads(self._meta_path.read_text())
            except Exception:
                self._metadata = []

    def _ensure_deps(self):
        try:
            import faiss  # noqa: F401
            import numpy as _np  # noqa: F401
            from sentence_transformers import SentenceTransformer  # noqa: F401
        except Exception as e:
            raise RuntimeError(
                "Missing ML dependencies for VectorStore. Install 'sentence-transformers faiss-cpu numpy' or see README."
            ) from e

    def _load_model(self):
        if self._model is None:
            # lazy import
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                raise RuntimeError(
                    "Failed to load sentence-transformers model: " + str(e)
                ) from e

    def index_documents(self, docs: List[Dict]) -> int:
        """Index a list of documents: each doc is {'id': str, 'text': str, 'meta': {...}}.

        Returns number of documents indexed.
        """
        self._ensure_deps()
        import faiss
        import numpy as np

        self._load_model()
        texts = [d.get("text", "") for d in docs]
        if not texts:
            return 0
        embs = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

        # normalize for cosine similarity via inner product
        def _norm(a: np.ndarray):
            norms = np.linalg.norm(a, axis=1, keepdims=True)
            norms[norms == 0.0] = 1.0
            return a / norms

        embs = _norm(embs.astype("float32"))
        d = embs.shape[1]
        if self._index is None:
            self._index = faiss.IndexFlatIP(d)
        # Add embeddings
        self._index.add(embs)
        # append metadata
        for doc in docs:
            self._metadata.append(
                {
                    "doc_id": doc.get("id"),
                    "text": doc.get("text"),
                    "meta": doc.get("meta", {}),
                }
            )
        # persist
        try:
            faiss.write_index(self._index, str(self._index_path))
            self._meta_path.write_text(
                json.dumps(self._metadata, ensure_ascii=False, indent=2)
            )
        except Exception:
            # non-fatal persistence failure
            pass
        return len(docs)

    def rebuild_index(self, docs: List[Dict]) -> int:
        """Rebuild the entire index from the provided documents (overwrite previous data)."""
        self._ensure_deps()
        import faiss
        import numpy as np

        # reset metadata and index
        self._metadata = []
        self._index = None
        if not docs:
            # delete files if present
            try:
                if self._index_path.exists():
                    self._index_path.unlink()
                if self._meta_path.exists():
                    self._meta_path.unlink()
            except Exception:
                pass
            return 0

        self._load_model()
        texts = [d.get("text", "") for d in docs]
        embs = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

        def _norm(a: np.ndarray):
            norms = np.linalg.norm(a, axis=1, keepdims=True)
            norms[norms == 0.0] = 1.0
            return a / norms

        embs = _norm(embs.astype("float32"))
        d = embs.shape[1]
        self._index = faiss.IndexFlatIP(d)
        self._index.add(embs)
        for doc in docs:
            self._metadata.append(
                {
                    "doc_id": doc.get("id"),
                    "text": doc.get("text"),
                    "meta": doc.get("meta", {}),
                }
            )
        # persist
        try:
            faiss.write_index(self._index, str(self._index_path))
            self._meta_path.write_text(
                json.dumps(self._metadata, ensure_ascii=False, indent=2)
            )
        except Exception:
            pass
        return len(docs)

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Search for top-k documents given a query. Returns list of dicts with score and metadata."""
        self._ensure_deps()
        import faiss
        import numpy as np

        self._load_model()
        q_emb = self._model.encode([query], convert_to_numpy=True)[0].astype("float32")
        # normalize
        q_emb = q_emb / (np.linalg.norm(q_emb) or 1.0)
        # try load index if not in-memory
        if self._index is None and self._index_path.exists():
            try:
                self._index = faiss.read_index(str(self._index_path))
            except Exception:
                self._index = None
        if self._index is None or self._index.ntotal == 0:
            return []
        distances, indices = self._index.search(np.expand_dims(q_emb, axis=0), k)
        results: List[Dict] = []
        for score, idx in zip(distances[0].tolist(), indices[0].tolist()):
            if idx < 0 or idx >= len(self._metadata):
                continue
            m = self._metadata[idx]
            results.append(
                {
                    "score": float(score),
                    "doc_id": m.get("doc_id"),
                    "text": m.get("text"),
                    "meta": m.get("meta"),
                }
            )
        return results

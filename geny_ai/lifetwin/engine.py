"""LifeTwin Engine (stub)

- persona_prompt: core persona for Geny
- generate_reply: uses RAG (via VectorStore stub) then delegates to backend /chat for now
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import requests

from geny_ai.memory_sphere.vectorstore import VectorStore

PERSONA_PROMPT = (
    "You are Geny: empathetic, witty, supportive. Prioritize Andreas kindly."
)


@dataclass
class LifeTwin:
    backend_url: str
    vs: VectorStore

    def retrieve(self, query: str, k: int = 3) -> List[str]:
        return [t for (t, _) in self.vs.search(query, top_k=k)]

    def generate_reply(self, message: str) -> str:
        # For now, call existing backend /chat and prepend persona context if useful.
        try:
            ctx = "\n\n".join(self.retrieve(message))
            payload = {"message": f"{PERSONA_PROMPT}\nContext:\n{ctx}\nUser: {message}"}
            r = requests.post(f"{self.backend_url}/chat", json=payload, timeout=20)
            if r.ok:
                return r.json().get("reply", "")
            return f"Backend error: {r.status_code}"
        except Exception as e:
            return f"Error: {e}"

from __future__ import annotations

from typing import Dict, List


def build_rag_prompt(user_message: str, docs: List[Dict], max_snippets: int = 3) -> str:
    """Build a simple RAG-augmented prompt by prepending retrieved snippets.

    This is intentionally small and portable (does not require LangChain). Each
    snippet will be labeled and added as a factual context block for the LLM.
    """
    header = (
        "The following factual context snippets are provided to help answer the user. "
        "When producing the answer, rely only on the facts below and label sources.\n\n"
    )
    parts = [header]
    for i, d in enumerate((docs or [])[:max_snippets], start=1):
        meta = d.get("meta") or {}
        src = meta.get("source") or meta.get("doc_id") or f"doc-{i}"
        txt = (d.get("text") or "").strip()
        parts.append(f"[SOURCE {i} | {src}] {txt}\n")
    parts.append(
        "\nUser question:\n"
        + user_message
        + "\n\nAnswer (use the sources above and be concise):"
    )
    return "\n".join(parts)

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import httpx


async def ddg_instant_answer(
    query: str, *, timeout: float = 8.0, max_related: int = 8
) -> Dict[str, Any]:
    """Call DuckDuckGo Instant Answer API (no key) and extract a compact result.

    Returns: { query, abstract: {text, url, source}, related: [{title, url, text}] }
    """
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "abstract": None,
            "related": [],
        }

    abstract_text = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    abstract_src = (data.get("AbstractSource") or "").strip()

    related_items = []
    for item in data.get("RelatedTopics", [])[:max_related]:
        if isinstance(item, dict) and "Text" in item and "FirstURL" in item:
            related_items.append(
                {
                    "title": item.get("Text", "").strip(),
                    "url": item.get("FirstURL", "").strip(),
                    "text": item.get("Text", "").strip(),
                }
            )
        elif isinstance(item, dict) and "Topics" in item:
            for sub in item.get("Topics", [])[:max_related]:
                if not isinstance(sub, dict):
                    continue
                if "Text" in sub and "FirstURL" in sub:
                    related_items.append(
                        {
                            "title": sub.get("Text", "").strip(),
                            "url": sub.get("FirstURL", "").strip(),
                            "text": sub.get("Text", "").strip(),
                        }
                    )
                if len(related_items) >= max_related:
                    break
        if len(related_items) >= max_related:
            break

    return {
        "query": query,
        "abstract": (
            {
                "text": abstract_text,
                "url": abstract_url,
                "source": abstract_src,
            }
            if abstract_text or abstract_url
            else None
        ),
        "related": related_items,
    }


def _generate_aliases(name: str) -> List[str]:
    """Heuristically generate alias spellings and punctuations for a person name."""
    base = name.strip()
    aliases = {base}
    # Remove dots and excess spaces
    no_dots = re.sub(r"[\.]+", "", base)
    aliases.add(no_dots)
    aliases.add(re.sub(r"\s+", " ", no_dots).strip())
    # Common small variations (domain-specific hook for 'Jamsheere'/'Jamsheree')
    if "jamsheree" in base.lower():
        aliases.add(re.sub(r"(?i)jamsheree", "Jamsheere", base))
    if "jamsheere" in base.lower():
        aliases.add(re.sub(r"(?i)jamsheere", "Jamsheree", base))
    # Without middle token
    parts = base.split()
    if len(parts) >= 3:
        aliases.add(f"{parts[0]} {parts[-1]}")
    return list(dict.fromkeys([a for a in aliases if a]))


async def ddg_aggregate_with_aliases(
    query: str, *, timeout: float = 8.0, max_related: int = 8, max_aliases: int = 5
) -> Dict[str, Any]:
    """Aggregate DDG results across alias spellings and dedupe related items by URL."""
    aliases = _generate_aliases(query)[:max_aliases]
    abstract_best: Dict[str, Any] | None = None
    related_all: Dict[str, Dict[str, str]] = {}
    errors: List[Tuple[str, str]] = []
    for q in aliases:
        res = await ddg_instant_answer(q, timeout=timeout, max_related=max_related)
        if res.get("error"):
            errors.append((q, res["error"]))
        abs_res = res.get("abstract")
        if abs_res and (
            not abstract_best
            or len(abs_res.get("text", "")) > len(abstract_best.get("text", ""))
        ):
            abstract_best = abs_res | {"alias": q}
        for item in res.get("related", []) or []:
            url = item.get("url")
            if url and url not in related_all:
                related_all[url] = item
    return {
        "query": query,
        "aliases": aliases,
        "abstract": abstract_best,
        "related": list(related_all.values())[:max_related],
        "errors": errors,
    }


async def wikipedia_search(
    query: str, *, timeout: float = 6.0
) -> Dict[str, Any] | None:
    """Query Wikipedia REST API (no API key) to fetch a short extract for the best-matching page.

    Returns a dict matching the Wikipedia REST content structure or None on failure.
    """
    # Use the search endpoint to find a relevant page, then fetch the summary extract
    search_url = "https://en.wikipedia.org/w/rest.php/v1/search/title"
    summary_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(search_url, params={"q": query, "limit": 1})
            r.raise_for_status()
            j = r.json()
            pages = j.get("pages") or []
            if not pages:
                return None
            page = pages[0]
            title = page.get("title")
            if not title:
                return None
            s = await client.get(summary_url + httpx.utils.quote(title, safe=""))
            s.raise_for_status()
            return s.json()
    except Exception:
        return None

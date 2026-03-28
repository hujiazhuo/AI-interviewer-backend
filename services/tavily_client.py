import os

import httpx

from config import TAVILY_API_KEY, TAVILY_BASE_URL


async def tavily_search(query: str, max_results: int = 5) -> dict:
    q = (query or "").strip()
    if not q:
        return {"results": [], "source": "empty_query"}
    if not TAVILY_API_KEY:
        return {"results": [], "source": "no_api_key"}

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": q,
        "max_results": max(1, min(10, int(max_results or 5))),
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": False,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(TAVILY_BASE_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            rows = []
            for r in data.get("results") or []:
                rows.append(
                    {
                        "title": str(r.get("title") or ""),
                        "url": str(r.get("url") or ""),
                        "content": str(r.get("content") or "")[:500],
                        "score": float(r.get("score") or 0.0),
                    }
                )
            return {
                "results": rows,
                "answer": str(data.get("answer") or ""),
                "source": "tavily",
            }
    except Exception:
        return {"results": [], "source": "error"}

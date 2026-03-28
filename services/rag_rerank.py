import json
import os
import re

import httpx


def _lexical_score(query: str, text: str) -> float:
    q_tokens = set(re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", (query or "").lower()))
    t_tokens = set(re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", (text or "").lower()))
    if not q_tokens or not t_tokens:
        return 0.0
    inter = len(q_tokens & t_tokens)
    return inter / (len(q_tokens) ** 0.5 * len(t_tokens) ** 0.5)


def _fallback_rerank(query: str, chunks: list[dict], top_k: int):
    rows = []
    for c in chunks:
        s = _lexical_score(query, c.get("content", ""))
        item = dict(c)
        item["rerankScore"] = round(float(s), 6)
        rows.append(item)
    rows.sort(key=lambda x: x.get("rerankScore", 0.0), reverse=True)
    return rows[:top_k], "fallback_lexical"


async def rerank_chunks(query: str, chunks: list[dict], top_k: int = 3):
    if not chunks:
        return {"chunks": [], "source": "empty"}

    n = max(1, min(10, int(top_k or 3)))
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions")

    if not api_key:
        rows, source = _fallback_rerank(query, chunks, n)
        return {"chunks": rows, "source": source}

    brief = []
    for i, c in enumerate(chunks, start=1):
        brief.append(
            {
                "index": i,
                "source": c.get("source", ""),
                "headerPath": c.get("headerPath", ""),
                "content": (c.get("content", "") or "")[:220],
            }
        )

    messages = [
        {
            "role": "system",
            "content": (
                "你是检索重排序助手。"
                "请从候选片段中选出最相关的前N条，并返回JSON。"
                "只输出JSON: {\"indices\":[3,1,2]}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"用户问题: {query}\n"
                f"N={n}\n"
                f"候选: {json.dumps(brief, ensure_ascii=False)}"
            ),
        },
    ]
    payload = {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 180}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=18.0) as client:
            resp = await client.post(base_url, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            obj = json.loads(content)
            indices = obj.get("indices") or []
            picked = []
            used = set()
            for idx in indices:
                try:
                    k = int(idx) - 1
                except Exception:
                    continue
                if k < 0 or k >= len(chunks) or k in used:
                    continue
                used.add(k)
                item = dict(chunks[k])
                item["rerankScore"] = round(1.0 - 0.05 * len(picked), 6)
                picked.append(item)
                if len(picked) >= n:
                    break
            if len(picked) < n:
                fb, _ = _fallback_rerank(query, chunks, n)
                for it in fb:
                    if len(picked) >= n:
                        break
                    if it.get("docId") not in {x.get("docId") for x in picked}:
                        picked.append(it)
            return {"chunks": picked[:n], "source": "llm"}
    except Exception:
        rows, source = _fallback_rerank(query, chunks, n)
        return {"chunks": rows, "source": source}

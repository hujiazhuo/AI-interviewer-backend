import json
import os
import re

import httpx


def _fallback_rewrites(query: str, job_role: str, keywords: list[str]) -> list[str]:
    q = (query or "").strip()
    role = (job_role or "通用技术岗").strip()
    keys = [k.strip() for k in (keywords or []) if str(k).strip()][:3]

    if keys and q:
        return [
            f"{q} 面试题 {role}",
            f"{keys[0]} 与 {keys[1] if len(keys) > 1 else '常见方案'} 区别",
            f"{keys[0]} 高并发 故障排查 最佳实践",
        ]

    if keys:
        return [
            f"{keys[0]} 面试题 {role}",
            f"{keys[0]} 与 {keys[1] if len(keys) > 1 else '常见方案'} 区别",
            f"{keys[0]} 高并发 故障排查 最佳实践",
        ]

    if q:
        return [
            f"{q} 面试题 {role}",
            f"{q} 底层原理 实战场景",
            f"{q} 高频追问 与 优化策略",
        ]

    return [
        f"{role} 核心技术 面试题",
        f"{role} 底层原理 高频追问",
        f"{role} 线上故障排查 案例",
    ]


def _extract_lines(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []

    # 优先 JSON
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            arr = obj.get("rewrites") or obj.get("queries") or []
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        if isinstance(obj, list):
            return [str(x).strip() for x in obj if str(x).strip()]
    except Exception:
        pass

    rows = []
    for line in text.splitlines():
        s = re.sub(r"^\s*[-*\d.\)]\s*", "", line.strip())
        if s:
            rows.append(s)
    return rows


async def rewrite_query(query: str, job_role: str, keywords: list[str] | None = None):
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions")

    keys = [str(k).strip() for k in (keywords or []) if str(k).strip()][:8]

    if not api_key:
        rewrites = _fallback_rewrites(query, job_role, keys)
        return {"rewrites": rewrites[:3], "source": "fallback_no_api_key"}

    messages = [
        {
            "role": "system",
            "content": (
                "你是检索查询改写助手。"
                "请把输入改写为3条技术检索词，用于RAG召回。"
                "只输出JSON: {\"rewrites\":[\"...\",\"...\",\"...\"]}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"岗位: {job_role}\n"
                f"原始意图: {query}\n"
                f"简历关键词: {json.dumps(keys, ensure_ascii=False)}\n"
                "要求：覆盖基础原理、实战场景、高频追问三个角度。"
            ),
        },
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 220,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=18.0) as client:
            resp = await client.post(base_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            lines = _extract_lines(content)
            rewrites = [x for x in lines if x][:3]
            if len(rewrites) < 3:
                rewrites = (rewrites + _fallback_rewrites(query, job_role, keys))[:3]
            return {"rewrites": rewrites, "source": "llm"}
    except Exception:
        rewrites = _fallback_rewrites(query, job_role, keys)
        return {"rewrites": rewrites[:3], "source": "fallback_error"}

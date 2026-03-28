import asyncio

from services import rag_kb
from services import rag_rerank
from services import rag_rewrite
from services import rag_resume
from services import store
from utils.response import err, ok
from config import RAG_TOP_K_RETRIEVE, RAG_TOP_K_RERANK
from config import (
    ENABLE_TAVILY_FALLBACK,
    KNOWLEDGE_DIR,
    RAG_COLLECTION_NAME,
    RAG_PERSIST_DIR,
    SIMILARITY_THRESHOLD,
    TAVILY_BASE_URL,
    TAVILY_API_KEY,
    WRITEBACK_MIN_ANSWER_LEN,
    WRITEBACK_MIN_WEB_SCORE,
    WRITEBACK_ON_WEB_MODE,
)


def knowledge_rebuild(body):
    source_dir = (body.get("source_dir") or "").strip() or None
    force = bool(body.get("force", True))
    try:
        data = rag_kb.rebuild_knowledge(source_dir=source_dir, force=force)
        return 200, ok(data)
    except FileNotFoundError as e:
        return 400, err(4001, str(e))
    except Exception as e:
        return 500, err(5000, f"知识库重建失败: {type(e).__name__}")


def config_view():
    return 200, ok(
        {
            "similarity_threshold": float(SIMILARITY_THRESHOLD),
            "top_k_retrieve": int(RAG_TOP_K_RETRIEVE),
            "top_k_rerank": int(RAG_TOP_K_RERANK),
            "enable_tavily_fallback": bool(ENABLE_TAVILY_FALLBACK),
            "writeback_on_web_mode": bool(WRITEBACK_ON_WEB_MODE),
            "writeback_min_web_score": float(WRITEBACK_MIN_WEB_SCORE),
            "writeback_min_answer_len": int(WRITEBACK_MIN_ANSWER_LEN),
            "knowledge_dir": KNOWLEDGE_DIR,
            "collection_name": RAG_COLLECTION_NAME,
            "persist_dir": RAG_PERSIST_DIR,
            "tavily_base_url": TAVILY_BASE_URL,
            "tavily_key_set": True if TAVILY_API_KEY else False,
        }
    )


def knowledge_ingest(body):
    paths = body.get("paths") or []
    if not isinstance(paths, list) or not paths:
        return 400, err(4001, "参数校验失败")
    try:
        data = rag_kb.ingest_paths(paths)
        return 200, ok(data)
    except Exception as e:
        return 500, err(5000, f"知识库增量入库失败: {type(e).__name__}")


def resume_keywords(user, body):
    top_n = body.get("topN") or body.get("top_n") or 20
    try:
        top_n = max(1, min(50, int(top_n)))
    except Exception:
        top_n = 20

    resume = body.get("resume")
    if not isinstance(resume, dict):
        resume = store.get_resume(user["userId"]) or {}

    if not resume:
        return 404, err(4040, "简历不存在")

    data = rag_resume.extract_resume_keywords(resume, top_n=top_n)
    return 200, ok(
        {
            "keywords": data["keywords"],
            "weighted": data["weighted"],
            "totalCandidates": data["totalCandidates"],
            "source": "body" if body.get("resume") else "store",
        }
    )


def query_rewrite(user, body):
    query = (body.get("query") or body.get("intention") or "").strip()
    job_role = (body.get("job_role") or body.get("jobRole") or "通用技术岗").strip()
    if not query:
        return 400, err(4001, "参数校验失败")

    keywords = body.get("keywords")
    if not isinstance(keywords, list):
        resume = body.get("resume")
        if not isinstance(resume, dict):
            resume = store.get_resume(user["userId"]) or {}
        if isinstance(resume, dict) and resume:
            kw = rag_resume.extract_resume_keywords(resume, top_n=8)
            keywords = kw.get("keywords") or []
        else:
            keywords = []

    result = asyncio.run(rag_rewrite.rewrite_query(query=query, job_role=job_role, keywords=keywords))
    return 200, ok(
        {
            "query": query,
            "job_role": job_role,
            "keywords": keywords,
            "rewrites": result.get("rewrites") or [],
            "source": result.get("source", "unknown"),
        }
    )


def knowledge_retrieve(user, body):
    query = (body.get("query") or "").strip()
    if not query:
        return 400, err(4001, "参数校验失败")

    try:
        top_k = max(1, min(30, int(body.get("topK") or body.get("top_k") or RAG_TOP_K_RETRIEVE)))
    except Exception:
        top_k = RAG_TOP_K_RETRIEVE

    with_rerank = bool(body.get("with_rerank", True))
    job_role = (body.get("job_role") or body.get("jobRole") or "通用技术岗").strip()

    keywords = body.get("keywords")
    if not isinstance(keywords, list):
        resume = body.get("resume")
        if not isinstance(resume, dict):
            resume = store.get_resume(user["userId"]) or {}
        if resume:
            keywords = (rag_resume.extract_resume_keywords(resume, top_n=8) or {}).get("keywords", [])
        else:
            keywords = []

    rewrite_res = asyncio.run(rag_rewrite.rewrite_query(query=query, job_role=job_role, keywords=keywords))
    rewrites = rewrite_res.get("rewrites") or [query]

    merged: dict[str, dict] = {}
    for q in rewrites:
        hits = rag_kb.retrieve_chunks(q, top_k=top_k)
        for h in hits:
            doc_id = h.get("docId")
            if not doc_id:
                continue
            old = merged.get(doc_id)
            if (not old) or (h.get("score", 0) > old.get("score", 0)):
                merged[doc_id] = h

    merged_hits = list(merged.values())
    merged_hits.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    merged_hits = merged_hits[:top_k]

    rerank_source = "disabled"
    reranked = merged_hits
    if with_rerank:
        rr = asyncio.run(rag_rerank.rerank_chunks(query=query, chunks=merged_hits, top_k=RAG_TOP_K_RERANK))
        reranked = rr.get("chunks") or []
        rerank_source = rr.get("source", "unknown")

    return 200, ok(
        {
            "query": query,
            "rewrites": rewrites,
            "rewriteSource": rewrite_res.get("source", "unknown"),
            "hits": merged_hits,
            "reranked": reranked,
            "rerankSource": rerank_source,
        }
    )

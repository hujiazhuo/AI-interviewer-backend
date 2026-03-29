import hashlib
import os
import re
from pathlib import Path

from config import KNOWLEDGE_DIR, RAG_COLLECTION_NAME, RAG_PERSIST_DIR, ROOT_DIR

try:
    import chromadb
except Exception:
    chromadb = None

try:
    from langchain_text_splitters import MarkdownHeaderTextSplitter
except Exception:
    MarkdownHeaderTextSplitter = None


def _ensure_runtime():
    if chromadb is None:
        raise RuntimeError("chromadb 未安装")
    if MarkdownHeaderTextSplitter is None:
        raise RuntimeError("langchain_text_splitters 未安装")


def _resolve_dir(source_dir: str | None = None) -> Path:
    raw = (source_dir or KNOWLEDGE_DIR or "./knowledge").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = Path(ROOT_DIR) / raw
    return p.resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_markdown(content: str):
    if MarkdownHeaderTextSplitter is None:
        # 轻量兜底：按 Markdown 标题分段
        blocks = []
        current_header = {"h1": "", "h2": "", "h3": "", "h4": ""}
        current_lines: list[str] = []

        def _flush():
            text = "\n".join(current_lines).strip()
            if text:
                blocks.append(
                    type(
                        "Doc",
                        (),
                        {
                            "page_content": text,
                            "metadata": dict(current_header),
                        },
                    )()
                )

        for raw in (content or "").splitlines():
            line = raw.rstrip("\n")
            m = re.match(r"^(#{1,4})\s+(.*)$", line)
            if m:
                _flush()
                current_lines = []
                level = len(m.group(1))
                title = m.group(2).strip()
                if level <= 1:
                    current_header.update({"h1": title, "h2": "", "h3": "", "h4": ""})
                elif level == 2:
                    current_header.update({"h2": title, "h3": "", "h4": ""})
                elif level == 3:
                    current_header.update({"h3": title, "h4": ""})
                else:
                    current_header.update({"h4": title})
                continue
            current_lines.append(line)

        _flush()
        return blocks

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
            ("####", "h4"),
        ]
    )
    return splitter.split_text(content)


def _header_path(meta: dict) -> str:
    return " > ".join([meta.get("h1", ""), meta.get("h2", ""), meta.get("h3", ""), meta.get("h4", "")]).strip(
        " >"
    )


def _tokens(text: str):
    return re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", (text or "").lower())


def _embed_text(text: str, dim: int = 256):
    vec = [0.0] * dim
    toks = _tokens(text)
    if not toks:
        return vec
    for tok in toks:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _build_rows(md_path: Path):
    content = _read_text(md_path)
    docs = _split_markdown(content)
    rows = []
    for i, d in enumerate(docs):
        text = (d.page_content or "").strip()
        if not text:
            continue
        meta = dict(d.metadata or {})
        row_id = hashlib.sha1(f"{md_path.as_posix()}::{i}::{text}".encode("utf-8")).hexdigest()[:24]
        rows.append(
            {
                "id": row_id,
                "text": text,
                "embedding": _embed_text(text),
                "metadata": {
                    "source": md_path.as_posix(),
                    "headerPath": _header_path(meta),
                    "h1": str(meta.get("h1", "")),
                    "h2": str(meta.get("h2", "")),
                    "h3": str(meta.get("h3", "")),
                    "h4": str(meta.get("h4", "")),
                },
            }
        )
    return rows


def _get_client():
    if chromadb is None:
        raise RuntimeError("chromadb 未安装")
    os.makedirs(RAG_PERSIST_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=RAG_PERSIST_DIR)


def _get_or_create_collection(client):
    return client.get_or_create_collection(name=RAG_COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def rebuild_knowledge(source_dir: str | None = None, force: bool = True):
    _ensure_runtime()
    kb_dir = _resolve_dir(source_dir)
    if not kb_dir.exists():
        raise FileNotFoundError(f"知识库目录不存在: {kb_dir}")

    files = sorted(kb_dir.glob("**/*.md"))
    client = _get_client()
    if force:
        try:
            client.delete_collection(RAG_COLLECTION_NAME)
        except Exception:
            pass
    collection = _get_or_create_collection(client)

    total_chunks = 0
    for fp in files:
        rows = _build_rows(fp)
        if not rows:
            continue
        collection.add(
            ids=[r["id"] for r in rows],
            documents=[r["text"] for r in rows],
            metadatas=[r["metadata"] for r in rows],
            embeddings=[r["embedding"] for r in rows],
        )
        total_chunks += len(rows)

    return {
        "files": len(files),
        "chunks": total_chunks,
        "collection": RAG_COLLECTION_NAME,
        "persistDir": RAG_PERSIST_DIR,
        "sourceDir": kb_dir.as_posix(),
    }


def ingest_paths(paths: list[str]):
    _ensure_runtime()
    if not paths:
        raise ValueError("paths 不能为空")

    client = _get_client()
    collection = _get_or_create_collection(client)

    file_count = 0
    total_chunks = 0
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = Path(ROOT_DIR) / p
        p = p.resolve()
        if not p.exists() or p.suffix.lower() != ".md":
            continue
        rows = _build_rows(p)
        if not rows:
            continue
        collection.upsert(
            ids=[r["id"] for r in rows],
            documents=[r["text"] for r in rows],
            metadatas=[r["metadata"] for r in rows],
            embeddings=[r["embedding"] for r in rows],
        )
        file_count += 1
        total_chunks += len(rows)

    return {
        "files": file_count,
        "chunks": total_chunks,
        "collection": RAG_COLLECTION_NAME,
        "persistDir": RAG_PERSIST_DIR,
    }


def retrieve_chunks(query: str, top_k: int = 10, source_filter: str | None = None):
    q = (query or "").strip()
    if not q:
        raise ValueError("query 不能为空")

    def _fallback_retrieve() -> list[dict]:
        kb_dir = _resolve_dir(None)
        if not kb_dir.exists():
            return []
        files = sorted(kb_dir.glob("**/*.md"))
        if source_filter:
            sf = source_filter.lower()
            files = [fp for fp in files if sf in fp.as_posix().lower()]

        q_vec = _embed_text(q)

        def _cosine(a: list[float], b: list[float]) -> float:
            if not a or not b:
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            if na <= 0 or nb <= 0:
                return 0.0
            return dot / (na * nb)

        rows = []
        for fp in files:
            for r in _build_rows(fp):
                score = max(0.0, min(1.0, _cosine(q_vec, r.get("embedding") or [])))
                rows.append(
                    {
                        "docId": r.get("id"),
                        "score": round(float(score), 6),
                        "source": r.get("metadata", {}).get("source", ""),
                        "headerPath": r.get("metadata", {}).get("headerPath", ""),
                        "content": r.get("text", ""),
                    }
                )
        rows.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return rows[: max(1, int(top_k or 10))]

    if chromadb is None:
        return _fallback_retrieve()

    client = _get_client()
    collection = _get_or_create_collection(client)

    n = max(1, int(top_k or 10))
    n_query = n * 6 if source_filter else n
    try:
        result = collection.query(
            query_embeddings=[_embed_text(q)],
            n_results=n_query,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return _fallback_retrieve()

    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    hits = []
    for i in range(min(len(ids), len(docs), len(metas), len(dists))):
        dist = float(dists[i])
        sim = max(0.0, min(1.0, 1.0 - dist))
        source = (metas[i] or {}).get("source", "")
        if source_filter and source_filter.lower() not in str(source).lower():
            continue
        hits.append(
            {
                "docId": ids[i],
                "score": round(sim, 6),
                "source": source,
                "headerPath": (metas[i] or {}).get("headerPath", ""),
                "content": docs[i],
            }
        )
        if len(hits) >= n:
            break
    return hits

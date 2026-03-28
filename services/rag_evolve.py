import hashlib
from datetime import datetime
from pathlib import Path

from config import (
    EVOLUTION_KB_FILE,
    KNOWLEDGE_DIR,
    ROOT_DIR,
    WRITEBACK_ON_WEB_MODE,
)
from services import rag_kb


def _resolve_kb_dir() -> Path:
    p = Path(KNOWLEDGE_DIR)
    if not p.is_absolute():
        p = Path(ROOT_DIR) / p
    return p.resolve()


def _resolve_evolution_file() -> Path:
    kb_dir = _resolve_kb_dir()
    kb_dir.mkdir(parents=True, exist_ok=True)
    return (kb_dir / EVOLUTION_KB_FILE).resolve()


def _extract_latest_qa(history: list[dict]) -> tuple[str, str]:
    q = ""
    a = ""
    for m in reversed(history or []):
        role = str(m.get("role", "")).lower()
        text = str(m.get("content", "")).strip()
        if not text:
            continue
        if not a and role in ["user", "human"]:
            a = text
        if not q and role in ["ai", "assistant"]:
            q = text
        if q and a:
            break
    return q, a


def writeback_web_learning(
    job_role: str,
    history: list[dict],
    web_sources: list[dict],
    web_answer: str = "",
    knowledge_scope: str = "",
) -> dict:
    if not WRITEBACK_ON_WEB_MODE:
        return {"written": False, "reason": "disabled"}

    target = _resolve_evolution_file()

    question, answer = _extract_latest_qa(history)

    if not question:
        question = f"{job_role} 面试追问"
    answer = answer.strip()
    ref_answer = (web_answer or "").strip()
    if (not answer) and ref_answer:
        answer = ref_answer[:500]
    if not answer:
        answer = "候选人未提供有效回答，以下为本轮联网学习参考。"

    low_confidence = False
    if len(answer) < 20 and ref_answer:
        answer = f"候选人简答：{answer}\n\n联网参考：{ref_answer[:500]}"
        low_confidence = True
    elif len(answer) < 20:
        low_confidence = True

    src = web_sources[0] if web_sources else {}
    src_score = float(src.get("score") or 0.0)
    if src_score < 0.5:
        low_confidence = True

    if ref_answer and "联网参考" not in answer:
        answer = f"候选人回答：{answer}\n\n联网参考：{ref_answer[:500]}"

    src_title = str(src.get("title") or "")
    src_url = str(src.get("url") or "")
    src_content = str(src.get("content") or "")[:260]

    fingerprint = hashlib.sha1(f"{question}|{answer}".encode("utf-8")).hexdigest()[:12]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scope_txt = (knowledge_scope or "general").strip() or "general"
    src_count = len(web_sources or [])
    block = (
        "\n\n## 自动进化补充（联网学习）\n"
        f"- 时间：{now}\n"
        f"- 岗位：{job_role}\n"
        f"- 知识范围：{scope_txt}\n"
        f"- 指纹：{fingerprint}\n\n"
        f"### 问题\n{question}\n\n"
        f"### 参考答案\n{answer}\n\n"
        f"### 来源\n- 条数：{src_count}\n- 标题：{src_title}\n- 链接：{src_url}\n- 摘要：{src_content}\n"
    )

    old_text = target.read_text(encoding="utf-8") if target.exists() else ""

    if not old_text.strip():
        old_text = (
            "# Evolution Knowledge Base\n\n"
            "该文件用于记录联网检索后的增量学习内容，避免污染原始岗位题库。\n"
        )

    backup = old_text
    with open(target, "w", encoding="utf-8") as f:
        f.write(old_text.rstrip() + block)

    try:
        ingest = rag_kb.ingest_paths([target.as_posix()])
    except Exception:
        # 增量入库失败时回滚文件，避免脏数据
        with open(target, "w", encoding="utf-8") as f:
            f.write(backup)
        return {"written": False, "reason": "ingest_failed_rollback", "file": target.as_posix()}

    return {
        "written": True,
        "file": target.as_posix(),
        "fingerprint": fingerprint,
        "lowConfidence": low_confidence,
        "ingest": ingest,
    }

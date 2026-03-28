import re


CN_STOPWORDS = {
    "负责",
    "参与",
    "相关",
    "以及",
    "进行",
    "一个",
    "我们",
    "项目",
    "系统",
    "能力",
    "经验",
    "工作",
    "开发",
    "实现",
    "优化",
}

EN_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "have",
    "has",
    "you",
    "your",
    "our",
    "team",
    "project",
    "system",
}


def _norm_text(text: str) -> str:
    return (text or "").strip()


def _extract_terms(text: str) -> list[str]:
    src = _norm_text(text)
    if not src:
        return []

    # 中文词串 + 英文/数字标识
    terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_\-+.]{1,}", src)
    out = []
    for t in terms:
        token = t.strip()
        if not token:
            continue
        lower = token.lower()
        if lower in EN_STOPWORDS or token in CN_STOPWORDS:
            continue
        out.append(token)
    return out


def _add_weight(counter: dict[str, float], text: str, weight: float):
    for t in _extract_terms(text):
        counter[t] = counter.get(t, 0.0) + float(weight)


def extract_resume_keywords(resume: dict | None, top_n: int = 20):
    data = resume or {}
    score_map: dict[str, float] = {}

    _add_weight(score_map, str(data.get("targetJobIndustry") or ""), 2.0)
    _add_weight(score_map, str(data.get("techStack") or ""), 3.0)
    _add_weight(score_map, str(data.get("mastery") or ""), 2.0)

    for v in data.get("interviewTypes") or []:
        _add_weight(score_map, str(v), 1.6)
    for v in data.get("directions") or []:
        _add_weight(score_map, str(v), 1.8)

    for p in data.get("projects") or []:
        if not isinstance(p, dict):
            continue
        _add_weight(score_map, str(p.get("name") or ""), 2.2)
        _add_weight(score_map, str(p.get("role") or ""), 1.6)
        _add_weight(score_map, str(p.get("highlights") or ""), 2.4)
        _add_weight(score_map, str(p.get("description") or ""), 1.4)
        _add_weight(score_map, str(p.get("tech") or p.get("techStack") or ""), 2.4)

    # 去重排序：权重降序 + 词长降序
    items = sorted(score_map.items(), key=lambda x: (-x[1], -len(x[0]), x[0]))
    keywords = [k for k, _ in items[: max(1, int(top_n))]]

    return {
        "keywords": keywords,
        "weighted": [{"term": k, "weight": round(v, 3)} for k, v in items[: max(1, int(top_n))]],
        "totalCandidates": len(items),
    }

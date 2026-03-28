from services import store
from utils.response import err, ok


def _calc_completeness(body):
    score = 0
    weights = {
        "name": 8,
        "targetJobIndustry": 12,
        "workYears": 8,
        "interviewTypes": 10,
        "techStack": 14,
        "mastery": 10,
        "directions": 8,
        "projects": 30,
    }

    for key, weight in weights.items():
        value = body.get(key)
        if key in ["interviewTypes", "directions", "projects"]:
            if isinstance(value, list) and len(value) > 0:
                score += weight
        else:
            if isinstance(value, str) and value.strip():
                score += weight

    projects = body.get("projects") or []
    if isinstance(projects, list) and projects:
        quality_bonus = 0
        p = projects[0] if isinstance(projects[0], dict) else {}
        for k in ["name", "responsibility", "challengeSolution", "quantResult"]:
            if isinstance(p.get(k), str) and p.get(k).strip():
                quality_bonus += 2
        score += min(8, quality_bonus)

    return min(100, int(score))


def _validate_resume_body(body):
    list_fields = ["interviewTypes", "directions", "projects"]
    for field in list_fields:
        value = body.get(field)
        if value is not None and not isinstance(value, list):
            return False

    projects = body.get("projects")
    if projects is not None:
        for item in projects:
            if not isinstance(item, dict):
                return False

    return True


def save(user, body, is_draft=False):
    if not isinstance(body, dict):
        return 400, err(4001, "参数校验失败")
    if not _validate_resume_body(body):
        return 400, err(4001, "参数校验失败")

    backend_score = _calc_completeness(body)
    payload = dict(body)
    payload["completeness_score"] = backend_score

    result = store.save_resume(user["userId"], payload, is_draft=is_draft)
    return 200, ok(result)


def my_resume(user):
    data = store.get_resume(user["userId"])
    return 200, ok(data)


def diagnosis(user, body):
    target_job = (body.get("targetJob") or "").strip()
    if not target_job:
        return 400, err(4001, "参数校验失败")

    result = {
        "matchPercent": 86,
        "keywords": ["项目经验", "性能优化", "沟通表达"],
        "suggestions": [
            "补充量化结果（如首屏耗时降低xx%）",
            "增加复杂问题排查案例",
        ],
    }
    store.save_resume_diagnosis(user["userId"], target_job, result)
    return 200, ok(result)

import asyncio
import uuid
from threading import Thread
from urllib.parse import parse_qs

from services import store
from services import rag_evolve
from services.interview_agent import (
    analyze_interview_report,
    closing_summary,
    evaluate_checkpoint_feedback,
    next_question,
    start_question,
)
from utils.response import err, ok
from utils.time_utils import now_iso


def jobs():
    return 200, ok(store.get_jobs())


def _session_id():
    return f"is_{uuid.uuid4().hex[:12]}"


def _report_id():
    return f"rpt_{uuid.uuid4().hex[:12]}"


def _normalize_decision(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ["end", "finish", "stop", "结束", "结束面试", "结束问答", "quit"]:
        return "end"
    if v in ["continue", "cont", "继续", "继续问答", "继续面试", "next"]:
        return "continue"
    return ""


def _build_checkpoint_message(feedback: str, answered_round: int) -> str:
    fb = (feedback or "").strip()
    if not fb:
        fb = "评价：你本阶段整体表现稳定，建议继续保持结构化表达。"
    # 防止点评文案中夹带“下一题”导致前端误判为继续提问
    cleaned_lines = []
    for raw in fb.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("下一题"):
            continue
        if "?" in line or "？" in line:
            continue
        cleaned_lines.append(line)
    fb = "\n".join(cleaned_lines) or "评价：本轮回答完成，建议继续保持结构化表达与证据支撑。"
    return (
        f"{fb}\n"
        f"你已完成第{max(1, int(answered_round or 1))}题。"
        "请在下方按钮中选择“继续问答”或“结束面试”。"
    )


def _normalize_continue_question(text: str) -> str:
    raw = (text or “”).strip()
    if not raw:
        return “请说明你做过的一个复杂故障排查案例，并给出关键证据与结果。”

    # 优先提取”下一题：”后的题干
    if “下一题：” in raw:
        candidate = raw.split(“下一题：”)[-1].strip()
        # 清理可能残留的前缀
        for prefix in [“问题：”, “第11题：”, “第十一题：”, “请回答：”]:
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix) :].strip()
        return candidate

    # “第一个问题：” 格式（首轮）
    if “第一个问题：” in raw:
        candidate = raw.split(“第一个问题：”)[-1].strip()
        for prefix in [“问题：”, “请回答：”]:
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix) :].strip()
        return candidate

    # 无法解析时返回默认题
    return “请说明你做过的一个复杂故障排查案例，并给出关键证据与结果。”


def _extract_review_text(text: str, default_hint: str = "") -> str:
    raw = (text or "").strip()
    if not raw:
        return (default_hint or "回答已收到，建议继续补充细节与量化结果。")

    rows = [x.strip() for x in raw.splitlines() if x.strip()]
    review_lines = []
    for line in rows:
        if line.startswith(("评价：", "纠正：", "建议：", "总结：", "反馈：")):
            review_lines.append(line)

    if review_lines:
        return "\n".join(review_lines[:2])

    if "下一题：" in raw:
        head = raw.split("下一题：", 1)[0].strip()
        if head:
            return head

    return (default_hint or "回答已收到，建议继续补充细节与量化结果。")


def _is_checkpoint_round(answered_round: int, base_rounds: int, cycle_rounds: int) -> bool:
    answered = max(1, int(answered_round or 1))
    base = max(1, int(base_rounds or 10))
    cycle = max(1, int(cycle_rounds or 5))
    if answered == base:
        return True
    if answered > base and ((answered - base) % cycle == 0):
        return True
    return False


def _latest_ai_message(messages: list[dict]) -> str:
    for m in reversed(messages or []):
        if str(m.get("role", "")).lower() in ["ai", "assistant"]:
            text = str(m.get("content", "")).strip()
            if text:
                return text
    return "本次面试已到阶段节点。你可以选择结束面试或继续问答。"


def _checkpoint_payload(session: dict, prompt: str) -> dict:
    current_round = int(session.get("currentRound") or 1)
    total = int(session.get("totalRounds") or 10)
    cycle_rounds = max(1, int(session.get("cycleRounds") or 5))
    # 兼容旧前端：避免使用 currentRound >= totalRounds 直接自动结束
    display_total = max(total, current_round + cycle_rounds)
    return {
        "currentRound": current_round,
        "round": current_round,
        "totalRounds": display_total,
        "total_rounds": display_total,
        "answeredRound": current_round,
        "nextQuestionRound": current_round,
        "awaitChoice": True,
        "mustChoose": True,
        "phase": "checkpoint",
        "status": "checkpoint",
        "allowAutoEnd": False,
        "autoAnalyze": False,
        "decisionDelayMs": 5000,
        "decisionOptions": ["end", "continue"],
        "nextQuestion": prompt,
        "question": prompt,
        "reply": prompt,
        "finished": False,
        "instantFeedback": {"keyword": ["完成本轮"], "scoreHint": 84},
    }


def _can_decide_now(session: dict) -> bool:
    if bool(session.get("decision_pending")):
        return True
    current_round = int(session.get("currentRound") or 1)
    total = int(session.get("totalRounds") or 10)
    # 兼容新前端：当 currentRound >= totalRounds 时，允许直接调用 decision
    return current_round >= total


def _handle_decision(user, session, session_id: str, decision: str, body: dict | None = None):
    if not _can_decide_now(session):
        return 409, err(4090, "当前无需选择结束或继续")

    d = _normalize_decision(decision)
    if not d:
        return 400, err(4001, "参数校验失败")

    current_round = int(session.get("currentRound") or 1)
    cycle_rounds = max(1, int(session.get("cycleRounds") or 5))
    total = int(session.get("totalRounds") or 10)
    messages = list(session.get("messages") or [])
    body = body or {}

    if d == "end":
        closing_text = "好的，本轮到此结束。5秒后将进入评分环节，请稍候。"
        messages.append({"role": "ai", "content": closing_text, "ts": now_iso()})
        store.update_interview_session(
            session_id,
            user["userId"],
            {
                "messages": messages,
                "status": "finished",
                "decision_pending": False,
                "last_decision": "end",
            },
        )
        return 200, ok(
            {
                "currentRound": current_round,
                "current_round": current_round,
                "round": current_round,
                "totalRounds": total,
                "total_rounds": total,
                "sessionId": session_id,
                "session_id": session_id,
                "decision": "end",
                "status": "finished",
                "decisionDelayMs": 500,
                "nextAction": "analyze",
                "message": closing_text,
                "question": closing_text,
                "nextQuestion": closing_text,
                "awaitChoice": False,
                "finished": True,
            }
        )

    # continue
    new_total = total + cycle_rounds
    next_round = current_round + 1
    question_policy = body.get("question_policy") or session.get("question_policy") or {}
    knowledge_scope = (body.get("knowledge_scope") or session.get("knowledge_scope") or "").strip()
    asked_questions = body.get("asked_questions")
    if not isinstance(asked_questions, list):
        asked_questions = list(session.get("asked_questions") or [])

    result = asyncio.run(
        next_question(
            user_id=user["userId"],
            job_role=session.get("job_role", "通用技术岗"),
            resume_data=session.get("resume_data") or {},
            turn_count=next_round,
            history=messages,
            user_answer="",
            question_policy=question_policy,
            knowledge_scope=knowledge_scope,
            asked_questions=asked_questions,
        )
    )
    next_q = _normalize_continue_question(
        result.get("question") or "请你说明一次你解决复杂线上问题的完整排查路径。"
    )
    messages.append({"role": "ai", "content": next_q, "ts": now_iso()})
    asked_questions = (asked_questions + [next_q])[-30:]

    store.update_interview_session(
        session_id,
        user["userId"],
        {
            "messages": messages,
            "status": "active",
            "decision_pending": False,
            "last_decision": "continue",
            "currentRound": next_round,
            "totalRounds": new_total,
            "question_policy": question_policy,
            "knowledge_scope": knowledge_scope,
            "asked_questions": asked_questions,
        },
    )

    return 200, ok(
        {
            # 与文档对齐：continue 后 currentRound 指向“下一题轮次”
            "currentRound": next_round,
            "current_round": next_round,
            "round": next_round,
            "answeredRound": current_round,
            "nextQuestionRound": next_round,
            "totalRounds": new_total,
            "total_rounds": new_total,
            "sessionId": session_id,
            "session_id": session_id,
            "decision": "continue",
            "decisionDelayMs": 500,
            "awaitChoice": False,
            "nextQuestion": next_q,
            "next_question": next_q,
            "question": next_q,
            "trace": result.get("trace") or [],
            "retrieval": result.get("retrieval") or {},
            "finished": False,
            "remainingInCycle": max(0, int(new_total - current_round)),
        }
    )


def start(user, body):
    job_role = (body.get("job_role") or body.get("jobRole") or "").strip()
    if not job_role:
        return 400, err(4001, "参数校验失败")

    session_id = _session_id()
    resume_data = body.get("resume_data") or store.get_resume(user["userId"]) or {}
    question_policy = body.get("question_policy") or {}
    knowledge_scope = (body.get("knowledge_scope") or "").strip()
    asked_questions = body.get("asked_questions") or []
    if not isinstance(asked_questions, list):
        asked_questions = []

    first = asyncio.run(
        start_question(
            user["userId"],
            job_role,
            resume_data,
            question_policy=question_policy,
            knowledge_scope=knowledge_scope,
            asked_questions=asked_questions,
        )
    )
    question = first["question"]

    base_rounds = max(1, int(body.get("base_rounds") or 10))
    cycle_rounds = max(1, int(body.get("cycle_rounds") or 5))
    total_rounds = max(base_rounds, int(body.get("total_rounds") or base_rounds))

    session = {
        "sessionId": session_id,
        "userId": user["userId"],
        "job_role": job_role,
        "status": "active",
        "currentRound": 1,
        "totalRounds": total_rounds,
        "baseRounds": base_rounds,
        "cycleRounds": cycle_rounds,
        "decision_pending": False,
        "last_decision": "",
        "stage": first.get("stage", "tech"),
        "resume_data": resume_data,
        "question_policy": question_policy,
        "knowledge_scope": knowledge_scope,
        "asked_questions": (asked_questions + [question])[-20:],
        "messages": [{"role": "ai", "content": question, "ts": now_iso()}],
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    store.create_interview_session(session)

    return 200, ok(
        {
            "sessionId": session_id,
            "session_id": session_id,
            "currentRound": 1,
            "round": 1,
            "totalRounds": total_rounds,
            "total_rounds": total_rounds,
            "question": question,
            "firstQuestion": question,
            "trace": first.get("trace") or [],
            "retrieval": first.get("retrieval") or {},
        }
    )


def answer(user, body):
    session_id = (body.get("sessionId") or body.get("session_id") or "").strip()
    decision = _normalize_decision(body.get("decision") or body.get("interview_action") or body.get("action") or "")
    answer_text = (body.get("answer") or "").strip()
    if not session_id:
        return 400, err(4001, "参数校验失败")

    session = store.get_interview_session(session_id, user["userId"])
    if not session:
        return 404, err(4040, "会话不存在")
    if session.get("status") not in ["active", "finished"]:
        return 409, err(4090, "会话已结束")

    if decision:
        return _handle_decision(user, session, session_id, decision, body)

    if bool(session.get("decision_pending")):
        prompt = _latest_ai_message(session.get("messages") or [])
        return 409, err(4090, prompt or "当前轮次已完成，请先选择继续问答或结束面试")

    if not answer_text:
        return 400, err(4001, "参数校验失败")
    if session.get("status") != "active":
        return 409, err(4090, "会话已结束")

    messages = list(session.get("messages") or [])
    messages.append({"role": "user", "content": answer_text, "ts": now_iso()})
    question_policy = body.get("question_policy") or session.get("question_policy") or {}
    knowledge_scope = (body.get("knowledge_scope") or session.get("knowledge_scope") or "").strip()
    asked_questions = body.get("asked_questions")
    if not isinstance(asked_questions, list):
        asked_questions = list(session.get("asked_questions") or [])

    current_round = int(session.get("currentRound") or 1)
    next_round = current_round + 1
    total = int(session.get("totalRounds") or 10)
    base_rounds = int(session.get("baseRounds") or 10)
    cycle_rounds = int(session.get("cycleRounds") or 5)
    # 兜底：当到达当前总题数上限时，必须先进入点评+决策，不直接继续出下一题
    reached_checkpoint = _is_checkpoint_round(current_round, base_rounds, cycle_rounds) or (current_round >= total)

    if reached_checkpoint:
        feedback = asyncio.run(
            evaluate_checkpoint_feedback(
                job_role=session.get("job_role", "通用技术岗"),
                user_answer=answer_text,
            )
        )
        prompt = _build_checkpoint_message(feedback, current_round)
        messages.append({"role": "ai", "content": prompt, "ts": now_iso()})
        store.update_interview_session(
            session_id,
            user["userId"],
            {
                "messages": messages,
                "currentRound": current_round,
                "status": "active",
                "decision_pending": True,
            },
        )
        return 200, ok(
            {
                "currentRound": current_round,
                "round": current_round,
                "totalRounds": total,
                "total_rounds": total,
                "answeredRound": current_round,
                "nextQuestionRound": current_round,
                # 文档要求：第10/15/20题必须 awaitChoice=true 触发弹窗，nextQuestion=null
                "awaitChoice": True,
                "mustChoose": True,
                "phase": "checkpoint",
                "status": "checkpoint",
                "checkpoint": True,
                "decisionOptions": ["end", "continue"],
                # 与对接文档保持兼容：点评文案多字段兜底
                "review": prompt,
                "comment": prompt,
                "feedback": prompt,
                "summary": prompt,
                "message": prompt,
                "checkpointComment": prompt,
                # 阶段收口：仅点评，nextQuestion 必须为 null
                "nextQuestion": None,
                "question": None,
                "reply": None,
                "finished": False,
                "instantFeedback": {"keyword": ["完成本轮"], "scoreHint": 84},
            }
        )

    result = asyncio.run(
        next_question(
            user_id=user["userId"],
            job_role=session.get("job_role", "通用技术岗"),
            resume_data=session.get("resume_data") or {},
            turn_count=next_round,
            history=messages,
            user_answer=answer_text,
            question_policy=question_policy,
            knowledge_scope=knowledge_scope,
            asked_questions=asked_questions,
        )
    )
    raw_question = result.get("question") or ""
    next_q = _normalize_continue_question(raw_question)
    review_text = _extract_review_text(
        raw_question,
        default_hint=("你的回答还可以更具体一些，建议补充关键指标与验证方式。" if result.get("is_vague") else "你的回答已覆盖核心点，建议继续保持结构化表达。"),
    )
    messages.append({"role": "ai", "content": next_q, "ts": now_iso()})
    asked_questions = (asked_questions + [next_q])[-20:]

    store.update_interview_session(
        session_id,
        user["userId"],
        {
            "messages": messages,
            "currentRound": next_round,
            "stage": result.get("stage", session.get("stage", "tech")),
            "question_policy": question_policy,
            "knowledge_scope": knowledge_scope,
            "asked_questions": asked_questions,
            "status": "active",
        },
    )

    return 200, ok(
        {
            # currentRound/round 表示“已完成回答的轮次”
            "currentRound": current_round,
            "round": current_round,
            "totalRounds": total,
            "total_rounds": total,
            "answeredRound": current_round,
            "nextQuestionRound": next_round,
            "nextQuestion": next_q,
            "question": next_q,
            "reply": next_q,
            "review": review_text,
            "comment": review_text,
            "feedback": review_text,
            "summary": review_text,
            "trace": result.get("trace") or [],
            "retrieval": result.get("retrieval") or {},
            "finished": False,
            "instantFeedback": {
                "keyword": ["需要更具体" if result.get("is_vague") else "继续深入"],
                "scoreHint": 80,
            },
        }
    )


def end(user, body):
    session_id = (body.get("sessionId") or body.get("session_id") or "").strip()
    if not session_id:
        return 400, err(4001, "参数校验失败")

    session = store.get_interview_session(session_id, user["userId"])
    if not session:
        return 404, err(4040, "会话不存在")

    result = asyncio.run(
        closing_summary(
            job_role=session.get("job_role", "通用技术岗"),
            history=session.get("messages") or [],
        )
    )

    store.update_interview_session(
        session_id,
        user["userId"],
        {
            "status": "finished",
            "summary": result["summary"],
            "finalScore": result["finalScore"],
            "dimensions": result["dimensions"],
        },
    )

    return 200, ok(
        {
            "sessionId": session_id,
            "status": "finished",
            "summary": result["summary"],
            "finalScore": result["finalScore"],
            "dimensions": result["dimensions"],
        }
    )


def chat(user, body):
    return answer(user, body)


def decision(user, body):
    session_id = (body.get("sessionId") or body.get("session_id") or "").strip()
    if not session_id:
        return 400, err(4001, "参数校验失败")
    session = store.get_interview_session(session_id, user["userId"])
    if not session:
        return 404, err(4040, "会话不存在")
    d = body.get("decision") or body.get("interview_action") or body.get("action") or ""
    return _handle_decision(user, session, session_id, d, body)


def session(user, query: str = ""):
    params = parse_qs(query or "")
    session_id = (params.get("sessionId") or params.get("session_id") or [""])[0].strip()
    if not session_id:
        return 400, err(4001, "参数校验失败")

    item = store.get_interview_session(session_id, user["userId"])
    if not item:
        return 404, err(4040, "会话不存在")

    return 200, ok(
        {
            "sessionId": item.get("sessionId"),
            "job_role": item.get("job_role", ""),
            "status": item.get("status", "active"),
            "currentRound": int(item.get("currentRound") or 1),
            "round": int(item.get("currentRound") or 1),
            "totalRounds": int(item.get("totalRounds") or 10),
            "total_rounds": int(item.get("totalRounds") or 10),
            "awaitChoice": bool(item.get("decision_pending")),
            "messages": item.get("messages") or [],
            "createdAt": item.get("createdAt", ""),
            "updatedAt": item.get("updatedAt", ""),
        }
    )


def _shape_record(item):
    return {
        "id": item.get("id"),
        "recordId": item.get("id"),
        "reportId": item.get("id"),
        "sessionId": item.get("sessionId"),
        "job_role": item.get("job_role", ""),
        "job": item.get("job_role", ""),
        "score": int(item.get("finalScore") or item.get("total_score") or 0),
        "finalScore": int(item.get("finalScore") or item.get("total_score") or 0),
        "totalScore": int(item.get("total_score") or item.get("finalScore") or 0),
        "currentRound": int(item.get("currentRound") or 0),
        "round": int(item.get("currentRound") or 0),
        "totalRounds": int(item.get("totalRounds") or 10),
        "total_rounds": int(item.get("totalRounds") or 10),
        "status": item.get("status", "ready"),
        "scorePath": item.get("score_path", "web"),
        "date": item.get("createdAt", ""),
        "createdAt": item.get("createdAt", ""),
    }


def _shape_detail(item):
    return {
        "id": item.get("id"),
        "reportId": item.get("id"),
        "recordId": item.get("id"),
        "sessionId": item.get("sessionId"),
        "job_role": item.get("job_role", ""),
        "finalScore": int(item.get("finalScore") or item.get("total_score") or 0),
        "score": int(item.get("finalScore") or item.get("total_score") or 0),
        "totalScore": int(item.get("total_score") or item.get("finalScore") or 0),
        "summary": item.get("summary", ""),
        "dimensions": {
            "tech": int(item.get("tech_score") or 0),
            "logic": int(item.get("logic_score") or 0),
            "match": int(item.get("match_score") or 0),
            "expression": int(item.get("expression_score") or 0),
            "stability": int(item.get("stability_score") or item.get("expression_score") or 0),
        },
        "strengths": item.get("strengths") or [],
        "highlights": item.get("strengths") or [],
        "weaknesses": item.get("weaknesses") or [],
        "improvements": item.get("weaknesses") or [],
        "suggestions": item.get("suggestions") or [],
        "messages": item.get("chat_history") or [],
        "chat_history": item.get("chat_history") or [],
        "scorePath": item.get("score_path", "web"),
        "routeHint": item.get("score_path", "web"),
        "evidenceType": "kb" if item.get("score_path") == "kb" else "web",
        "evidenceChunks": item.get("evidence_chunks") or [],
        "webSources": item.get("web_sources") or [],
        "growthNote": item.get("growth_note") or "",
        "evolution": item.get("evolution") or {},
        "scoreRouteMeta": item.get("score_route_meta") or {},
        "status": item.get("status", "ready"),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }


def _run_analyze_job(report_id, user_id, job_role, chat_history, session_meta):
    try:
        result = asyncio.run(analyze_interview_report(job_role=job_role, history=chat_history))
        updates = {
            "status": "ready",
            "total_score": int(result["total_score"]),
            "tech_score": int(result["tech_score"]),
            "logic_score": int(result["logic_score"]),
            "match_score": int(result["match_score"]),
            "expression_score": int(result["expression_score"]),
            "finalScore": int(result["total_score"]),
            "score_path": result.get("score_path", "web"),
            "score_route_meta": result.get("score_route_meta") or {},
            "evidence_chunks": result.get("evidence_chunks") or [],
            "web_sources": result.get("web_sources") or [],
            "growth_note": "",
            "evolution": {},
            "summary": result["summary"],
            "strengths": result["strengths"],
            "weaknesses": result["weaknesses"],
            "suggestions": result["suggestions"],
            "dimensions": {
                "tech": int(result["tech_score"]),
                "logic": int(result["logic_score"]),
                "match": int(result["match_score"]),
                "expression": int(result["expression_score"]),
                "stability": int(result["expression_score"]),
            },
        }

        if result.get("score_path") == "web":
            evo = rag_evolve.writeback_web_learning(
                job_role=job_role,
                history=chat_history,
                web_sources=result.get("web_sources") or [],
                web_answer=result.get("web_answer") or "",
                knowledge_scope=(session_meta or {}).get("knowledge_scope", ""),
            )
            updates["evolution"] = evo
            if evo.get("written"):
                updates["growth_note"] = "本次面试中，AI 通过联网学习了新技术点，并已同步至知识库。"
            else:
                updates["growth_note"] = f"本次面试未写回知识库：{evo.get('reason', 'unknown')}"

        store.update_interview_report(report_id, user_id, updates)
        if session_meta:
            store.update_interview_session(
                session_meta["sessionId"],
                user_id,
                {
                    "status": "finished",
                    "summary": result["summary"],
                    "finalScore": int(result["total_score"]),
                    "dimensions": updates["dimensions"],
                },
            )
    except Exception as e:
        store.update_interview_report(
            report_id,
            user_id,
            {
                "status": "failed",
                "summary": f"评分生成失败: {type(e).__name__}",
            },
        )


def analyze(user, body):
    session_id = (body.get("sessionId") or body.get("session_id") or body.get("interview_id") or "").strip()
    job_role = (body.get("job_role") or body.get("jobRole") or "").strip()
    chat_history = body.get("chat_history") or body.get("chatHistory")

    session = None
    if session_id:
        session = store.get_interview_session(session_id, user["userId"])
        if not session:
            return 404, err(4040, "会话不存在")
        if not job_role:
            job_role = session.get("job_role", "通用技术岗")
        if not chat_history:
            chat_history = session.get("messages") or []

    if not chat_history:
        return 400, err(4001, "参数校验失败")

    if not job_role:
        job_role = "通用技术岗"

    old = store.get_interview_report_by_session(session_id, user["userId"]) if session_id else None
    if old and old.get("status") in ["processing", "ready"]:
        return 200, ok(
            {
                "id": old.get("id"),
                "reportId": old.get("id"),
                "sessionId": old.get("sessionId"),
                "status": old.get("status"),
            }
        )

    report_id = _report_id()
    now = now_iso()
    base_doc = {
        "id": report_id,
        "userId": user["userId"],
        "sessionId": session_id,
        "job_role": job_role,
        "status": "processing",
        "score_path": "pending",
        "score_route_meta": {},
        "evidence_chunks": [],
        "web_sources": [],
        "growth_note": "",
        "evolution": {},
        "currentRound": int((session or {}).get("currentRound") or 0),
        "totalRounds": int((session or {}).get("totalRounds") or 10),
        "chat_history": chat_history,
        "total_score": 0,
        "tech_score": 0,
        "logic_score": 0,
        "match_score": 0,
        "expression_score": 0,
        "finalScore": 0,
        "summary": "评分生成中，请稍候...",
        "strengths": [],
        "weaknesses": [],
        "suggestions": [],
        "createdAt": now,
        "updatedAt": now,
    }
    store.create_interview_report(base_doc)

    Thread(
        target=_run_analyze_job,
        args=(report_id, user["userId"], job_role, chat_history, session),
        daemon=True,
    ).start()

    return 200, ok(
        {
            "id": report_id,
            "reportId": report_id,
            "report_id": report_id,
            "sessionId": session_id,
            "status": "processing",
        }
    )


def records(user, query: str = ""):
    params = parse_qs(query or "")
    limit = int((params.get("limit") or [20])[0])
    page = int((params.get("page") or [1])[0])
    page_size = int((params.get("pageSize") or [limit])[0])

    items, total = store.list_interview_reports(
        user["userId"], limit=limit, page=page, page_size=page_size
    )
    rows = [_shape_record(x) for x in items]
    return 200, ok(
        {
            "records": rows,
            "list": rows,
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
    )


def report(user, report_id: str = "", query: str = ""):
    rid = (report_id or "").strip()
    if not rid:
        params = parse_qs(query or "")
        rid = (params.get("id") or params.get("reportId") or params.get("report_id") or [""])[0].strip()
    if not rid:
        return 400, err(4001, "参数校验失败")

    item = store.get_interview_report(rid, user["userId"])
    if not item:
        return 404, err(4040, "报告不存在")
    return 200, ok(_shape_detail(item))


def delete_record(user, report_id: str = "", query: str = "", body=None):
    rid = (report_id or "").strip()
    payload = body or {}
    if not rid:
        rid = (
            payload.get("id")
            or payload.get("reportId")
            or payload.get("report_id")
            or ""
        ).strip()
    if not rid:
        params = parse_qs(query or "")
        rid = (params.get("id") or params.get("reportId") or params.get("report_id") or [""])[0].strip()

    if not rid:
        return 400, err(4001, "参数校验失败")

    deleted = store.delete_interview_report(rid, user["userId"])
    if not deleted:
        return 404, err(4040, "记录不存在")

    return 200, ok({"id": rid, "deleted": True})

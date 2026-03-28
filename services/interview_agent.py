import os
import json
import re
from typing import Any, Literal, TypedDict

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from config import RAG_TOP_K_RERANK, RAG_TOP_K_RETRIEVE, SIMILARITY_THRESHOLD
from services import rag_kb, rag_rerank, rag_rewrite, rag_resume
from services.tavily_client import tavily_search

SYSTEM_PROMPT = """
你是一位来自锐捷网络的资深技术面试官。

【人格与风格】
- 专业、严谨、客观
- 不说套话，不寒暄，不输出无关内容
- 每次只问一个问题

【面试策略】
1) 先根据岗位 {job_role} 考察基础能力。
2) 再结合候选人简历中的项目经历进行深挖。
3) 如果候选人回答模糊，必须追问，直到获得可验证细节。
4) 问题要短、清晰、可回答，避免一次包含多个子问题。

【输出规则】
- 每场新面试（turn_count=1）必须先说："我是{job_role}岗位的面试官，接下来由我来进行面试。"
- 紧接着必须说："第一个问题：..."，只问一个问题。
- 若候选人已作答（last_user_answer 非空）：先评价回答质量，再指出关键错误或缺失并给出纠正，最后只问一个下一题。
- 若候选人尚未作答（首轮）：直接给出第一题。
- 输出保持简洁，控制在 2~4 句。
- 推荐结构：
    评价：...（1句）
    纠正：...（可无，若回答正确可写“无明显错误”）
    下一题：...（只问一个问题）
- 语气像真实技术面试，不要出现“作为AI”。
""".strip()

USER_PROMPT = """
当前阶段: {stage}
当前轮次: {turn_count}
岗位: {job_role}
出题策略: {question_policy}
简历结构化信息: {resume_data}
最近对话: {history}
候选人最新回答: {last_user_answer}
是否模糊回答: {is_vague}
检索到的知识库片段: {retrieved_context}

请生成“下一句面试问题”。

要求：
- 如果 turn_count=1 且 last_user_answer 为空：严格输出
    我是{job_role}岗位的面试官，接下来由我来进行面试。第一个问题：...
- 如果 last_user_answer 不为空：必须先“评价”，再“纠正”，最后“下一题”。
- 严禁一次给出多个并列问题。
- 若 question_policy.mode=project-lite：可以偶尔提及项目，但不要连续追问项目细节，优先转回基础原理与通用工程能力。
""".strip()


class InterviewState(TypedDict):
    user_id: str
    job_role: str
    resume_data: dict[str, Any]
    turn_count: int
    stage: Literal["intro", "tech", "project", "closing"]
    history: list[dict[str, str]]
    last_user_answer: str
    is_vague: bool
    retrieved_context: list[str]
    question_policy: dict[str, Any]
    knowledge_scope: str
    asked_questions: list[str]
    trace: list[str]
    retrieval: dict[str, Any]
    next_question: str


def _is_vague_answer(text: str) -> bool:
    text = (text or "").strip()
    if len(text) < 20:
        return True
    bad_tokens = ["不太清楚", "记不清", "差不多", "一般", "还行", "忘了"]
    return any(tok in text for tok in bad_tokens)


def _local_feedback_from_answer(answer: str, job_role: str) -> str:
    text = (answer or "").strip()
    if not text:
        return (
            "评价：你的回答信息不足。\n"
            "纠正：请补充技术方案、关键指标与最终效果。\n"
            "下一题：请你结合最近一个项目，说明你是如何定位并解决一次线上性能瓶颈的？"
        )

    has_metric = bool(re.search(r"\d", text)) and any(u in text for u in ["%", "秒", "ms", "毫秒", "QPS"])
    has_action = any(k in text for k in ["优化", "拆分", "缓存", "并发", "懒加载", "索引", "压缩", "监控", "定位"])
    has_verify = any(k in text for k in ["验证", "压测", "监控", "Lighthouse", "RUM", "对比", "指标"])

    if has_metric and has_action:
        eval_line = "评价：你的回答有结果导向，给出了较清晰的优化动作和量化指标。"
    elif has_action:
        eval_line = "评价：你描述了技术动作，但结果量化还不够充分。"
    else:
        eval_line = "评价：你的回答较笼统，技术细节和证据不足。"

    if has_verify:
        fix_line = "纠正：方向基本正确，建议补充瓶颈定位链路和取舍依据（为什么优先做这些优化）。"
    else:
        fix_line = "纠正：请补充验证方式（压测/监控前后对比）与关键指标变化。"

    if "首屏" in text or "性能" in text:
        next_q = "下一题：你提到首屏优化，请具体说明如何定位最耗时环节，以及每一步优化带来的指标变化。"
    else:
        next_q = f"下一题：结合{job_role}岗位，请讲一次你主导的复杂问题排查，重点说明排查路径与最终证据。"

    return f"{eval_line}\n{fix_line}\n{next_q}"


def _seed_query(job_role: str, stage: str, resume_data: dict[str, Any], last_user_answer: str) -> str:
    ans = (last_user_answer or "").strip()
    if ans:
        return ans
    kws = (rag_resume.extract_resume_keywords(resume_data or {}, top_n=5) or {}).get("keywords") or []
    if kws:
        return f"{job_role} {stage} {' '.join(kws[:3])}"
    return f"{job_role} {stage} 面试题"


def _scope_filter(knowledge_scope: str, job_role: str) -> str | None:
    scope = (knowledge_scope or "").strip().lower()
    role = (job_role or "").strip().lower()
    if scope in ["java", "backend", "java-backend"] or "java" in role:
        return "java"
    if scope in ["network", "net"] or "网络" in job_role:
        return "网络"
    if scope in ["llm", "aigc"] or "大模型" in job_role:
        return "大模型"
    return None


def _is_repeated_question(question: str, asked_questions: list[str]) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    q_core = q.replace("第一个问题：", "").replace("下一题：", "").strip()
    for old in asked_questions or []:
        o = (old or "").replace("第一个问题：", "").replace("下一题：", "").strip()
        if not o:
            continue
        if q_core in o or o in q_core:
            return True
        a = set(re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", q_core))
        b = set(re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", o))
        if a and b and len(a & b) / max(1, len(a | b)) >= 0.75:
            return True
    return False


def _alternative_question(job_role: str, stage: str, turn_count: int) -> str:
    pools = {
        "tech": [
            "请你解释一下你最熟悉的中间件底层原理，并说出两个常见故障场景与排查步骤。",
            "如果线上接口RT突然抖动，你会如何分层定位（应用、缓存、数据库、网络）？",
            "请说说你做过的一次高并发优化，具体改了哪些点，收益如何量化？",
        ],
        "project": [
            "请挑一个你主导的项目，讲清业务目标、技术方案、权衡取舍与复盘结果。",
            "同样功能如果重做一次，你会删掉哪些复杂设计？为什么？",
            "请描述一次跨团队联调问题，你如何定位责任边界并推动修复上线？",
        ],
        "closing": [
            "请总结你在该岗位最有竞争力的三项能力，并说明各自的证据。",
            "如果明天入职该岗位，你的前两周技术落地计划是什么？",
            "请说一个你最想继续深挖的技术方向和学习路线。",
        ],
    }
    stage_key = stage if stage in pools else "tech"
    arr = pools[stage_key]
    idx = max(0, int(turn_count or 1) - 1) % len(arr)
    return f"我是{job_role}岗位的面试官，接下来由我来进行面试。第一个问题：{arr[idx]}" if int(turn_count or 1) == 1 else f"下一题：{arr[idx]}"


def _non_project_question(job_role: str, stage: str, turn_count: int) -> str:
    pools = {
        "tech": [
            "请你讲讲 JVM 内存模型，以及你如何定位和处理一次内存泄漏问题。",
            "如果数据库出现慢查询，你会如何从索引、SQL、连接池和锁竞争四个层面定位？",
            "请解释缓存击穿、穿透、雪崩的差异，并给出可落地的治理方案。",
        ],
        "project": [
            "请解释你最熟悉的核心技术栈底层原理，并说明在生产环境中的关键参数调优思路。",
            "谈谈你对系统可观测性的理解：日志、指标、链路追踪如何协同定位线上问题？",
            "当系统容量逼近上限时，你会如何做容量评估、扩容方案设计与发布风险控制？",
        ],
        "closing": [
            "如果让你给初级工程师做一次技术复盘培训，你会如何组织方法论与案例？",
            "请说说你未来半年最想补齐的三项技术能力，以及可执行学习计划。",
            "你如何平衡代码质量、交付速度与稳定性？请给出你的决策原则。",
        ],
    }
    stage_key = stage if stage in pools else "tech"
    arr = pools[stage_key]
    idx = max(0, int(turn_count or 1) - 1) % len(arr)
    return f"我是{job_role}岗位的面试官，接下来由我来进行面试。第一个问题：{arr[idx]}" if int(turn_count or 1) == 1 else f"下一题：{arr[idx]}"


def _is_project_heavy_question(text: str) -> bool:
    q = (text or "").strip()
    if not q:
        return False
    keys = ["项目", "你的项目", "项目中", "落地", "复盘", "上线"]
    return any(k in q for k in keys)


async def _retrieve_context_advanced(
    job_role: str,
    stage: str,
    resume_data: dict[str, Any],
    last_user_answer: str,
    knowledge_scope: str = "",
    question_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace = ["🔍 正在基于你的简历匹配知识库..."]
    retrieval = {
        "rewrites": [],
        "topSource": "",
        "topScore": 0.0,
        "rerankSource": "none",
        "hitCount": 0,
    }
    try:
        policy = question_policy or {}
        kws = (rag_resume.extract_resume_keywords(resume_data or {}, top_n=8) or {}).get("keywords") or []
        mode = str(policy.get("mode") or "balanced")
        project_keys = [k for k in kws if any(x in k.lower() for x in ["项目", "project", "系统", "system"]) ]
        show_key = kws[0] if kws else ""
        if mode == "project-lite" and project_keys:
            show_key = next((k for k in kws if k not in project_keys), show_key)
        if show_key:
            trace.append(f"💡 发现简历中的 {show_key} 亮点，正在检索底层原理...")

        query = _seed_query(job_role=job_role, stage=stage, resume_data=resume_data, last_user_answer=last_user_answer)
        rw = await rag_rewrite.rewrite_query(query=query, job_role=job_role, keywords=kws)
        rewrites = rw.get("rewrites") or [query]
        retrieval["rewrites"] = rewrites

        merged: dict[str, dict] = {}
        scope_filter = _scope_filter(knowledge_scope, job_role)
        for q in rewrites:
            for h in rag_kb.retrieve_chunks(q, top_k=RAG_TOP_K_RETRIEVE, source_filter=scope_filter):
                doc_id = h.get("docId")
                if not doc_id:
                    continue
                old = merged.get(doc_id)
                if (not old) or (h.get("score", 0) > old.get("score", 0)):
                    merged[doc_id] = h

        hits = list(merged.values())
        hits.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        retrieval["hitCount"] = len(hits)
        retrieval["knowledgeScope"] = knowledge_scope
        retrieval["sourceFilter"] = scope_filter or ""

        rr = await rag_rerank.rerank_chunks(query=query, chunks=hits[:RAG_TOP_K_RETRIEVE], top_k=RAG_TOP_K_RERANK)
        reranked = rr.get("chunks") or []
        retrieval["rerankSource"] = rr.get("source", "unknown")

        final_hits = reranked if reranked else hits[:RAG_TOP_K_RERANK]
        if final_hits:
            retrieval["topSource"] = final_hits[0].get("source", "")
            retrieval["topScore"] = float(final_hits[0].get("score", 0.0))
            trace.append("🧠 已完成查询改写与重排序，正在生成针对性问题...")
            trace.append("📚 已命中知识库片段，优先围绕你的项目进行追问。")
        else:
            trace.append("🧠 知识库命中较弱，正在结合通用模型知识生成问题。")

        context = [
            f"[{x.get('headerPath', '')}] {str(x.get('content', ''))[:260]}"
            for x in final_hits
            if str(x.get("content", "")).strip()
        ]
        return {"context": context, "trace": trace, "retrieval": retrieval}
    except Exception:
        trace.append("🧠 检索链路暂不可用，已切换到模型直出模式。")
        return {"context": [], "trace": trace, "retrieval": retrieval}


async def _call_deepseek(
    prompt_messages: list[dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 180,
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions")

    if not api_key:
        print("[interview_agent] DEEPSEEK_API_KEY 未配置，使用兜底问题")
        return "评价：你的回答信息不足。\n纠正：请补充技术方案、关键指标与最终效果。\n下一题：请你结合最近一个项目，说明你是如何定位并解决一次线上性能瓶颈的？"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    candidates = [model_name, "deepseek-chat", "deepseek-reasoner", "deepseek-v3"]
    # 去重，保留顺序
    seen = set()
    candidates = [m for m in candidates if not (m in seen or seen.add(m))]

    async with httpx.AsyncClient(timeout=25.0) as client:
        for model in candidates:
            payload = {
                "model": model,
                "messages": prompt_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                resp = await client.post(base_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                body = e.response.text[:200] if e.response is not None else ""
                print(
                    f"[interview_agent] DeepSeek HTTP error: model={model} "
                    f"status={e.response.status_code if e.response else 'NA'} body={body}"
                )
                # 模型不可用时，尝试下一个
                if "Model Not Exist" in body or "model_not_found" in body.lower():
                    continue
                break
            except Exception as e:
                print(f"[interview_agent] DeepSeek 调用异常: model={model} {type(e).__name__}: {e}")
                break

    return "评价：你的回答较笼统。\n纠正：请给出具体技术方案、关键指标和最终效果。\n下一题：请描述一次你主导的性能优化，并说明你如何验证优化有效。"


def _map_role(role: str) -> str:
    role = (role or "").strip().lower()
    if role in ["human", "user"]:
        return "user"
    if role in ["ai", "assistant"]:
        return "assistant"
    return "system"


def _normalize_first_question(raw_text: str, job_role: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        text = "请你先做一个简短自我介绍，并说明你与该岗位最匹配的项目经历。"

    lines = [x.strip() for x in text.splitlines() if x.strip()]
    candidate = lines[-1] if lines else text
    candidate = re.sub(r"^我是.*?岗位的面试官，接下来由我来进行面试。", "", candidate).strip()
    for prefix in ["下一题：", "问题：", "第一个问题：", "第一题：", "评价：", "纠正："]:
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix) :].strip()
    if not candidate:
        candidate = "请你先做一个简短自我介绍，并说明你与该岗位最匹配的项目经历。"

    return f"我是{job_role}岗位的面试官，接下来由我来进行面试。第一个问题：{candidate}"


async def _check_stage(state: InterviewState) -> InterviewState:
    turn = int(state.get("turn_count", 1))
    if turn <= 2:
        stage: Literal["intro", "tech", "project", "closing"] = "tech"
    elif turn <= 5:
        stage = "project"
    elif turn <= 8:
        stage = "tech"
    else:
        stage = "closing"
    state["stage"] = stage
    return state


async def _generate_question(state: InterviewState) -> InterviewState:
    retrieved_pack = await _retrieve_context_advanced(
        job_role=state["job_role"],
        stage=state["stage"],
        resume_data=state.get("resume_data", {}),
        last_user_answer=state.get("last_user_answer", ""),
        knowledge_scope=state.get("knowledge_scope", ""),
        question_policy=state.get("question_policy") or {},
    )
    retrieved = retrieved_pack.get("context") or []
    state["retrieved_context"] = retrieved
    state["trace"] = retrieved_pack.get("trace") or []
    state["retrieval"] = retrieved_pack.get("retrieval") or {}

    template = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("user", USER_PROMPT),
        ]
    )
    messages = template.format_messages(
        job_role=state["job_role"],
        stage=state["stage"],
        turn_count=state["turn_count"],
        question_policy=state.get("question_policy") or {},
        resume_data=state.get("resume_data", {}),
        history=state.get("history", [])[-6:],
        last_user_answer=state.get("last_user_answer", ""),
        is_vague=state.get("is_vague", False),
        retrieved_context=retrieved,
    )
    prompt_messages = [{"role": _map_role(m.type), "content": m.content} for m in messages]

    policy = state.get("question_policy") or {}
    rnd = str(policy.get("randomness") or "medium").lower()
    temp = 0.6 if rnd == "high" else (0.25 if rnd == "low" else 0.4)
    question = await _call_deepseek(prompt_messages, temperature=temp)

    last_answer = (state.get("last_user_answer") or "").strip()
    if last_answer:
        # 当模型不可用或返回过于模板化兜底文本时，使用本地规则生成“基于回答内容”的反馈
        if ("你的回答信息不足" in question or "你的回答较笼统" in question) and len(last_answer) >= 18:
            question = _local_feedback_from_answer(last_answer, state.get("job_role") or "通用技术")

    if int(state.get("turn_count", 1)) == 1 and not (state.get("last_user_answer") or "").strip():
        question = _normalize_first_question(question, state.get("job_role") or "通用技术")

    asked = state.get("asked_questions") or []
    policy = state.get("question_policy") or {}
    avoid_repeat = bool(policy.get("avoid_repeat", True))
    mode = str(policy.get("mode") or "balanced").lower()

    if mode == "project-lite" and _is_project_heavy_question(question):
        question = _non_project_question(
            job_role=state.get("job_role") or "通用技术岗",
            stage=state.get("stage") or "tech",
            turn_count=int(state.get("turn_count", 1)),
        )

    if avoid_repeat and _is_repeated_question(question, asked):
        if mode == "project-lite":
            question = _non_project_question(
                job_role=state.get("job_role") or "通用技术岗",
                stage=state.get("stage") or "tech",
                turn_count=int(state.get("turn_count", 1)),
            )
        else:
            question = _alternative_question(
                job_role=state.get("job_role") or "通用技术岗",
                stage=state.get("stage") or "tech",
                turn_count=int(state.get("turn_count", 1)),
            )

    state["next_question"] = question
    return state


def _build_graph():
    graph = StateGraph(InterviewState)
    graph.add_node("check_stage", _check_stage)
    graph.add_node("generate_question", _generate_question)
    graph.add_edge(START, "check_stage")
    graph.add_edge("check_stage", "generate_question")
    graph.add_edge("generate_question", END)
    return graph.compile()


INTERVIEW_GRAPH = _build_graph()


async def start_question(
    user_id: str,
    job_role: str,
    resume_data: dict[str, Any],
    question_policy: dict[str, Any] | None = None,
    knowledge_scope: str = "",
    asked_questions: list[str] | None = None,
) -> dict[str, Any]:
    init_state: InterviewState = {
        "user_id": user_id,
        "job_role": job_role,
        "resume_data": resume_data or {},
        "turn_count": 1,
        "stage": "intro",
        "history": [],
        "last_user_answer": "",
        "is_vague": False,
        "retrieved_context": [],
        "question_policy": question_policy or {},
        "knowledge_scope": knowledge_scope or "",
        "asked_questions": asked_questions or [],
        "trace": [],
        "retrieval": {},
        "next_question": "",
    }
    state = await INTERVIEW_GRAPH.ainvoke(init_state)
    return {
        "stage": state["stage"],
        "turn_count": state["turn_count"],
        "question": state["next_question"],
        "trace": state.get("trace") or [],
        "retrieval": state.get("retrieval") or {},
    }


async def next_question(
    user_id: str,
    job_role: str,
    resume_data: dict[str, Any],
    turn_count: int,
    history: list[dict[str, str]],
    user_answer: str,
    question_policy: dict[str, Any] | None = None,
    knowledge_scope: str = "",
    asked_questions: list[str] | None = None,
) -> dict[str, Any]:
    state_in: InterviewState = {
        "user_id": user_id,
        "job_role": job_role,
        "resume_data": resume_data or {},
        "turn_count": max(1, int(turn_count)),
        "stage": "intro",
        "history": history,
        "last_user_answer": user_answer,
        "is_vague": _is_vague_answer(user_answer),
        "retrieved_context": [],
        "question_policy": question_policy or {},
        "knowledge_scope": knowledge_scope or "",
        "asked_questions": asked_questions or [],
        "trace": [],
        "retrieval": {},
        "next_question": "",
    }
    state = await INTERVIEW_GRAPH.ainvoke(state_in)
    return {
        "stage": state["stage"],
        "turn_count": state["turn_count"],
        "question": state["next_question"],
        "is_vague": state["is_vague"],
        "trace": state.get("trace") or [],
        "retrieval": state.get("retrieval") or {},
    }


async def closing_summary(job_role: str, history: list[dict[str, str]]) -> dict[str, Any]:
    _ = history
    summary_prompt = [
        {
            "role": "system",
            "content": "你是严谨的技术面试官，请用100字以内给出总结。",
        },
        {
            "role": "user",
            "content": f"岗位: {job_role}。请给出本场面试总结，并输出一个0-100分总分。",
        },
    ]
    summary = await _call_deepseek(summary_prompt)
    return {
        "summary": summary,
        "finalScore": 84,
        "dimensions": {
            "tech": 86,
            "logic": 83,
            "expression": 85,
            "stability": 82,
        },
    }


async def evaluate_checkpoint_feedback(job_role: str, user_answer: str) -> str:
    text = (user_answer or "").strip()
    if not text:
        return "评价：你本轮回答信息较少，建议补充关键技术依据与可验证结果。"

    # 优先使用稳定本地规则，保证时延与稳定性
    local = _local_feedback_from_answer(text, job_role)
    lines = [x.strip() for x in local.splitlines() if x.strip()]
    if not lines:
        return "评价：你的回答有一定基础，建议继续加强结构化表达与证据支撑。"
    if lines[0].startswith("评价："):
        if len(lines) > 1 and lines[1].startswith("纠正："):
            return f"{lines[0]}\n{lines[1]}"
        return lines[0]
    return f"评价：{lines[0]}"


def _extract_json_block(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    block = match.group(0)
    try:
        obj = json.loads(block)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _clamp_score(value: Any, default: int = 75) -> int:
    try:
        score = int(float(value))
    except Exception:
        score = default
    return max(0, min(100, score))


def _to_list3(value: Any, defaults: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(x).strip() for x in value if str(x).strip()]
    elif isinstance(value, str):
        items = [x.strip() for x in re.split(r"[\n；;。]", value) if x.strip()]
    else:
        items = []
    if not items:
        items = list(defaults)
    while len(items) < 3:
        items.append(items[-1])
    return items[:3]


async def analyze_interview_report(job_role: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    def _score_route_decision() -> dict[str, Any]:
        user_answers = [
            str(m.get("content", ""))
            for m in (history or [])
            if str(m.get("role", "")).lower() in ["user", "human"] and str(m.get("content", "")).strip()
        ]
        query = f"{job_role} {' '.join(user_answers[-6:])}".strip()
        if not query:
            return {
                "score_path": "web",
                "similarity": 0.0,
                "threshold": float(SIMILARITY_THRESHOLD),
                "hits": [],
                "reason": "no_query",
                "query": query,
            }
        try:
            hits = rag_kb.retrieve_chunks(query, top_k=5)
            sim = float(hits[0].get("score", 0.0)) if hits else 0.0
            path = "kb" if sim >= float(SIMILARITY_THRESHOLD) else "web"
            return {
                "score_path": path,
                "similarity": sim,
                "threshold": float(SIMILARITY_THRESHOLD),
                "hits": hits,
                "reason": "threshold_compare",
                "query": query,
            }
        except Exception:
            return {
                "score_path": "web",
                "similarity": 0.0,
                "threshold": float(SIMILARITY_THRESHOLD),
                "hits": [],
                "reason": "kb_unavailable",
                "query": query,
            }

    decision = _score_route_decision()
    evidence = [
        {
            "source": h.get("source", ""),
            "headerPath": h.get("headerPath", ""),
            "score": h.get("score", 0.0),
            "content": str(h.get("content", ""))[:260],
        }
        for h in (decision.get("hits") or [])[:3]
    ]

    web_sources = []
    web_answer = ""
    if decision["score_path"] == "kb":
        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "你是一位严厉的技术专家。请优先依据给定知识库片段进行评分。"
                    "从技术深度、逻辑严密性、岗位匹配度、表达清晰度进行0-100评分。"
                    "必须输出严格 JSON，不要输出任何多余文字。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"岗位: {job_role}\n"
                    f"知识库片段: {json.dumps(evidence, ensure_ascii=False)}\n"
                    f"对话记录(JSON): {json.dumps(history, ensure_ascii=False)}\n\n"
                    "请输出 JSON，字段必须包含：\n"
                    "total_score, tech_score, logic_score, match_score, expression_score,\n"
                    "summary, strengths, weaknesses, suggestions\n"
                    "其中 strengths/weaknesses/suggestions 必须都是长度为3的字符串数组。"
                ),
            },
        ]
    else:
        web = await tavily_search(query=decision.get("query", f"{job_role} 面试评分参考"), max_results=5)
        web_sources = web.get("results") or []
        web_answer = str(web.get("answer") or "")
        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "你是一位正在学习新知识的学习型技术考官。"
                    "当使用联网资料（Tavily）评分时，你要先快速吸收资料中的新观点，再保持专业、克制、"
                    "基于证据地给出评价。"
                    "请结合联网资料与整场面试对话，从技术深度、逻辑严密性、岗位匹配度、表达清晰度进行0-100评分。"
                    "必须输出严格 JSON，不要输出任何多余文字。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"岗位: {job_role}\n"
                    f"联网资料: {json.dumps(web_sources, ensure_ascii=False)}\n"
                    f"对话记录(JSON): {json.dumps(history, ensure_ascii=False)}\n\n"
                    "请输出 JSON，字段必须包含：\n"
                    "total_score, tech_score, logic_score, match_score, expression_score,\n"
                    "summary, strengths, weaknesses, suggestions\n"
                    "其中 strengths/weaknesses/suggestions 必须都是长度为3的字符串数组。"
                ),
            },
        ]

    raw = await _call_deepseek(prompt_messages, temperature=0.2, max_tokens=700)
    parsed = _extract_json_block(raw) or {}

    tech = _clamp_score(parsed.get("tech_score", parsed.get("tech", 80)), default=80)
    logic = _clamp_score(parsed.get("logic_score", parsed.get("logic", 78)), default=78)
    match = _clamp_score(parsed.get("match_score", parsed.get("match", 79)), default=79)
    expression = _clamp_score(parsed.get("expression_score", parsed.get("expression", 77)), default=77)

    total_default = round(tech * 0.35 + logic * 0.25 + match * 0.25 + expression * 0.15)
    total = _clamp_score(parsed.get("total_score", parsed.get("finalScore", total_default)), default=total_default)

    summary = str(parsed.get("summary") or "具备一定技术基础，建议加强回答结构化与量化表达。")[:120]
    strengths = _to_list3(
        parsed.get("strengths"),
        ["能覆盖核心技术点", "沟通表达较清晰", "具备一定项目实践"],
    )
    weaknesses = _to_list3(
        parsed.get("weaknesses"),
        ["底层原理展开不足", "复杂场景推理不够严密", "量化指标支撑不足"],
    )
    suggestions = _to_list3(
        parsed.get("suggestions"),
        ["按STAR模板重写3个项目案例", "补齐核心技术栈底层原理", "每个项目准备2-3个量化指标"],
    )

    return {
        "total_score": total,
        "tech_score": tech,
        "logic_score": logic,
        "match_score": match,
        "expression_score": expression,
        "score_path": decision.get("score_path", "web"),
        "score_route_meta": {
            "similarity": round(float(decision.get("similarity", 0.0)), 6),
            "threshold": float(decision.get("threshold", SIMILARITY_THRESHOLD)),
            "reason": decision.get("reason", "unknown"),
        },
        "evidence_chunks": evidence,
        "web_sources": web_sources,
        "web_answer": web_answer,
        "summary": summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "raw": raw,
    }

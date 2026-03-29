# 模拟面试 API 对接文档（V2.0）

> 用途：前端「模拟面试对话页」与后端大语言模型考官能力对接
> 前端页面：/pages/interview/interview_chat
> 联调基线：`http://127.0.0.1:3000/api/v1`
> 更新日期：2026-03-29

---

## 1. 总体约定

- Base URL：`http://127.0.0.1:3000/api/v1`
- Content-Type：`application/json`
- 鉴权：`Authorization: Bearer <token>`（必填）
- 响应格式：统一 `code/message/data`
- 会话模式：前端持有 `sessionId`，每轮问答传回后端

### 1.1 统一响应结构

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 1.2 错误码

| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数校验失败 |
| 4010 | 未登录或 token 失效 |
| 4040 | 会话不存在 |
| 4090 | 会话已结束 |
| 4290 | 请求过快/超限 |
| 5000 | 服务端异常 |

---

## 2. 面试流程说明（核心）

### 2.1 发言顺序规则

| 发言序号 | 内容要求 | 触发条件 |
|---|---|---|
| 发言 1（首轮） | **只有问题**，无点评 | start 接口返回 |
| 发言 2~10 | **点评 + 问题** | 每轮 answer 返回 |
| 发言 11 | **只有点评**，无问题 | 第 10 题回答完毕后，触发弹窗 |
| 发言 12（继续后首轮） | **只有问题**，无点评 | decision=continue 返回 |
| 发言 13~16 | **点评 + 问题** | 每轮 answer 返回 |
| 发言 17 | **只有点评**，无问题 | 第 15 题回答完毕后，触发弹窗 |
| 发言 18（再继续） | **只有问题**，无点评 | decision=continue 返回 |
| ... | ... | 以此类推 |

### 2.2 流程图

```
┌─────────────────────────────────────────────────────────────┐
│ 初始阶段（10题）                                             │
│                                                             │
│  发言1: 问题1（start返回）                                    │
│  考生回答1                                                   │
│  发言2: 点评1 + 问题2                                        │
│  考生回答2                                                   │
│  ...                                                        │
│  发言10: 点评9 + 问题10                                      │
│  考生回答10                                                  │
│  发言11: 点评10（无问题）→ 弹窗：继续问答 / 结束面试            │
└─────────────────────────────────────────────────────────────┘
                            ↓ 选择"继续问答"
┌─────────────────────────────────────────────────────────────┐
│ 继续阶段（新增5题，共10题）                                   │
│                                                             │
│  发言12: 问题11（decision返回，只有问题）                      │
│  考生回答11                                                  │
│  发言13: 点评11 + 问题12                                     │
│  考生回答12                                                  │
│  ...                                                        │
│  发言16: 点评15 + 问题16                                      │
│  考生回答16                                                  │
│  发言17: 点评16（无问题）→ 弹窗：继续问答 / 结束面试            │
└─────────────────────────────────────────────────────────────┘
                            ↓ 选择"继续问答"
┌─────────────────────────────────────────────────────────────┐
│ 再继续阶段（再新增5题，共20题）                                │
│                                                             │
│  发言18: 问题17（decision返回，只有问题）                      │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 前端判断逻辑（已实现）

前端根据以下字段判断如何展示：

| 字段 | 类型 | 说明 |
|---|---|---|
| `awaitChoice` | boolean | true 时弹出继续/结束按钮 |
| `mustChoose` | boolean | 强制决策点，与 awaitChoice 效果相同 |
| `phase` | string | 为 "checkpoint" 时触发决策 |
| `status` | string | 为 "checkpoint" 时触发决策 |
| `decisionOptions` | array | 决策选项，如 ["end", "continue"] |

---

## 3. 接口定义

## 3.1 开始面试

- Method：`POST`
- URL：`/interview/start`
- Auth：是

### Request Body

```json
{
  "job_role": "前端开发工程师",
  "resume": {
    "name": "张三",
    "workYears": "3-5年",
    "techStack": "Vue3, TypeScript, Node.js",
    "directions": ["前端", "后端"],
    "projects": [
      {
        "name": "电商后台系统",
        "responsibility": "前端架构设计",
        "challengeSolution": "解决了首屏加载慢的问题",
        "quantResult": "首屏加载从 3s 优化到 1.2s"
      }
    ]
  },
  "question_policy": {
    "mode": "balanced",
    "randomness": "high",
    "avoid_repeat": true,
    "diversify_topics": true
  },
  "knowledge_scope": "general"
}
```

### Success Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260329_0001",
    "currentRound": 1,
    "totalRounds": 10,
    "question": "你好，欢迎来到前端开发工程师模拟面试。请先做一个 1 分钟自我介绍。"
  }
}
```

### 字段说明

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| sessionId | string | 是 | 会话 ID |
| currentRound | int | 是 | 当前轮次，从 1 开始 |
| totalRounds | int | 是 | 总轮次，初始为 10 |
| question | string | 是 | **首轮只需要问题**，不需要点评 |

### 兼容字段

| 推荐字段 | 兼容字段 |
|---|---|
| sessionId | session_id |
| currentRound | round, current_round |
| totalRounds | total_rounds |
| question | firstQuestion |

---

## 3.2 提交回答

- Method：`POST`
- URL：`/interview/answer`
- Auth：是

### Request Body

```json
{
  "sessionId": "is_20260329_0001",
  "job_role": "前端开发工程师",
  "round": 1,
  "answer": "我有 3 年前端经验，主要使用 Vue3 和 TypeScript...",
  "question_policy": {
    "mode": "balanced",
    "randomness": "high",
    "avoid_repeat": true,
    "diversify_topics": true,
    "max_project_followups": 2
  },
  "knowledge_scope": "general",
  "asked_questions": ["你好，欢迎...", "请先做自我介绍"]
}
```

### Success Response（常规回答，第 2~9 题）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answeredRound": 1,
    "currentRound": 2,
    "totalRounds": 10,
    "review": "你的自我介绍结构清晰，技术栈提到了 Vue3 和 TS，很好。建议可以补充一下项目规模和你的具体贡献。",
    "nextQuestion": "你提到做过性能优化，能具体讲讲你是如何定位和解决一个线上性能问题的吗？",
    "finished": false
  }
}
```

### Success Response（阶段末尾回答，第 10/15/20 题）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answeredRound": 10,
    "currentRound": 10,
    "totalRounds": 10,
    "review": "整体表现不错，技术深度可以，建议加强系统设计方面的准备。",
    "nextQuestion": null,
    "finished": false,
    "awaitChoice": true
  }
}
```

### 字段说明

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| review | string | 否 | **点评文本**，前端先显示点评再显示下一题 |
| nextQuestion | string | 否 | **下一题**，第 10/15/20 题时返回 null |
| awaitChoice | boolean | 否 | true 时前端弹出继续/结束按钮 |
| decisionOptions | array | 否 | 决策选项，如 ["end", "continue"] |

### 重要规则

1. **第 1 题返回**：只有 `question`，不需要 `review`
2. **第 2~9 题返回**：必须同时有 `review` + `nextQuestion`
3. **第 10/15/20 题返回**：
   - 必须有 `review`
   - `nextQuestion` 必须为 `null` 或不返回
   - 必须设置 `awaitChoice: true`

### 兼容字段

| 推荐字段 | 兼容字段 |
|---|---|
| review | comment, feedback, summary |
| nextQuestion | question, reply |
| awaitChoice | mustChoose, phase==="checkpoint" |
| decisionOptions | decision_options |

### ⚠️ 后端 LLM 输出解析规范（必须实现）

后端 LLM（DeepSeek）输出格式为：
```
评价：...（1句）
纠正：...（可无，若回答正确可写"无明显错误"）
下一题：...
```

**后端必须解析这个输出，分成两个字段返回：**

```python
# next_question 函数返回值必须包含：
{
    "stage": state["stage"],
    "turn_count": state["turn_count"],
    "review": "评价：...纠正：...",      # 包含"评价"和"纠正"部分
    "next_question": "下一题：...",     # 只有下一题，不包含评价和纠正
    "is_vague": state["is_vague"],
    "trace": state.get("trace") or [],
    "retrieval": state.get("retrieval") or {},
}
```

**解析逻辑示例（Python）：**

```python
def parse_llra_output(raw_output: str, job_role: str) -> dict:
    """解析 LLM 输出，分离 review 和 next_question"""
    lines = raw_output.split('\n')
    review_parts = []
    next_question = ""

    for line in lines:
        line = line.strip()
        if line.startswith("评价："):
            review_parts.append(line)
        elif line.startswith("纠正："):
            review_parts.append(line)
        elif line.startswith("下一题："):
            next_question = line
        elif line.startswith("无明显错误"):
            review_parts.append("纠正：无明显错误")

    review = "\n".join(review_parts) if review_parts else ""
    if not next_question:
        # 兜底：如果解析失败，至少返回原始内容
        next_question = raw_output

    return {
        "review": review,
        "next_question": next_question
    }
```

**关键点：**
- `review` 字段包含"评价"和"纠正"，前端会先显示这部分
- `next_question` 字段只有"下一题：..."，前端会单独显示这道题
- **严禁**把"评价+纠正+下一题"全部放在 `question` 字段中返回

---

## 3.3 提交决策

- Method：`POST`
- URL：`/interview/decision`
- Auth：是

### Request Body

```json
{
  "sessionId": "is_20260329_0001",
  "job_role": "前端开发工程师",
  "decision": "continue",
  "question_policy": {
    "mode": "balanced",
    "randomness": "high",
    "avoid_repeat": true,
    "diversify_topics": true
  },
  "knowledge_scope": "general",
  "asked_questions": ["问题1...", "问题2..."]
}
```

### Success Response（继续问答）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260329_0001",
    "decision": "continue",
    "currentRound": 11,
    "totalRounds": 15,
    "nextQuestion": "我们继续深入讨论。请讲一个你在项目中遇到的最大技术挑战是什么，你是如何解决的？",
    "awaitChoice": false
  }
}
```

### Success Response（结束面试）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260329_0001",
    "decision": "end",
    "message": "好的，本次面试到此结束。我将为你生成评估报告。"
  }
}
```

### 重要规则

1. **decision=continue 返回**：
   - `nextQuestion` **只需要问题**，不需要 review/点评
   - `totalRounds` 更新为 15（继续5题后的总数）
   - `awaitChoice` 必须为 false

2. **decision=end 返回**：
   - 返回确认消息即可

---

## 3.4 结束面试

- Method：`POST`
- URL：`/interview/end`
- Auth：是

### Request Body

```json
{
  "sessionId": "is_20260329_0001",
  "job_role": "前端开发工程师"
}
```

### Success Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260329_0001",
    "status": "finished",
    "summary": "整体表现良好，技术深度适中，表达结构清晰。"
  }
}
```

---

## 3.5 生成分析报告

- Method：`POST`
- URL：`/interview/analyze`
- Auth：是

### Request Body

```json
{
  "sessionId": "is_20260329_0001",
  "job_role": "前端开发工程师"
}
```

### Success Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "report_001",
    "sessionId": "is_20260329_0001",
    "finalScore": 84,
    "summary": "整体回答结构较清晰，项目细节可再深入，建议补充量化结果。",
    "strengths": ["表达清晰", "回答结构完整"],
    "weaknesses": ["量化指标不足", "深度追问略保守"],
    "suggestions": ["复习性能优化实战案例", "准备 STAR 项目叙述模板"],
    "dimensions": {
      "tech": 82,
      "logic": 80,
      "match": 85,
      "expression": 84,
      "stability": 79
    }
  }
}
```

### 兼容字段

| 推荐字段 | 兼容字段 |
|---|---|
| id | reportId, report_id |
| finalScore | totalScore, total_score, score |
| summary | comment, feedback |
| strengths | highlights |
| weaknesses | improvements |
| suggestions | advices |

---

## 4. 岗位枚举

- 前端开发工程师
- Java 开发工程师
- 网络工程师
- 大模型应用开发工程师

---

## 5. 联调示例

### 5.1 开始面试

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/start' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"job_role":"前端开发工程师"}'
```

### 5.2 提交回答（常规）

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/answer' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "sessionId":"is_20260329_0001",
    "job_role":"前端开发工程师",
    "round":1,
    "answer":"我有3年前端经验..."
  }'
```

### 5.3 提交回答（第 10 题，触发决策）

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/answer' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "sessionId":"is_20260329_0001",
    "job_role":"前端开发工程师",
    "round":10,
    "answer":"以上就是我的回答..."
  }'
```

### 5.4 提交决策（继续）

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/decision' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "sessionId":"is_20260329_0001",
    "job_role":"前端开发工程师",
    "decision":"continue"
  }'
```

### 5.5 结束面试

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/end' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"sessionId":"is_20260329_0001","job_role":"前端开发工程师"}'
```

---

## 6. 验收清单（后端）

| 序号 | 验收项 | 说明 |
|---|---|---|
| 1 | start 接口返回首题只有问题 | 不需要 review |
| 2 | answer 接口第 2~9 题同时返回 review + nextQuestion | 缺一不可 |
| 3 | answer 接口第 10/15/20 题只返回 review，nextQuestion 为 null | 触发弹窗 |
| 4 | decision=continue 返回只有 nextQuestion | 不需要 review |
| 5 | decision=continue 时 totalRounds 更新 | 10→15→20→... |
| 6 | 字段兼容 | session_id, round, total_rounds 等 |
| 7 | 错误码正确 | 4010, 4040, 4090 |
| 8 | **LLM 输出解析** | 必须将 LLM 输出的"评价+纠正"解析到 `review` 字段，"下一题"解析到 `next_question` 字段 |

---

## 7. 近期更新（2026-03-29）

### 需求变更说明

面试流程调整为：

1. **首轮发言**（发言1）：只有问题，无点评
2. **常规发言**（发言2~10）：点评 + 问题
3. **决策发言**（发言11、17、23...）：只有点评，触发弹窗
4. **继续后首轮**（发言12、18...）：只有问题，无点评
5. **继续后常规**（发言13~16、19~22...）：点评 + 问题

每轮 `totalRounds` 递增规则：10 → 15 → 20 → 25 ...

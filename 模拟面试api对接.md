# 模拟面试 API 对接文档（V1.1）

> 用途：支持前端“模拟面试对话页”与后端大语言模型考官能力对接。  
> 前端页面：/pages/interview/interview_chat  
> 联调基线：`http://127.0.0.1:3000/api/v1`

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

### 1.2 错误码建议

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

## 2. 会话状态模型（建议）

集合建议：`interview_sessions`

```json
{
  "_id": "ObjectId",
  "sessionId": "is_20260321_0001",
  "userId": "u_10001",
  "job_role": "前端开发工程师",
  "status": "active",
  "currentRound": 3,
  "totalRounds": 10,
  "messages": [
    { "role": "ai", "content": "请先做一个自我介绍", "ts": "2026-03-21T10:00:00+08:00" },
    { "role": "user", "content": "你好，我是...", "ts": "2026-03-21T10:00:20+08:00" }
  ],
  "scores": {
    "tech": 82,
    "logic": 78,
    "expression": 80,
    "stability": 76
  },
  "createdAt": "2026-03-21T10:00:00+08:00",
  "updatedAt": "2026-03-21T10:03:00+08:00"
}
```

---

## 3. 接口定义（前端当前已接）

## 3.1 开始面试

- Method：`POST`
- URL：`/interview/start`
- Auth：是

### Request Body

```json
{
  "job_role": "前端开发工程师"
}
```

### 推荐岗位枚举（含新增）

- 前端开发工程师
- Java 开发工程师
- 网络工程师
- 大模型应用开发工程师

### Success Response（推荐）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260321_0001",
    "currentRound": 1,
    "totalRounds": 10,
    "question": "你好，欢迎来到前端开发岗位模拟面试。请先做一个 1 分钟自我介绍。"
  }
}
```

### 兼容字段（前端已容错）

- `session_id`（可替代 `sessionId`）
- `round`（可替代 `currentRound`）
- `total_rounds`（可替代 `totalRounds`）
- `firstQuestion`（可替代 `question`）

---

## 3.2 提交回答并获取下一题

- Method：`POST`
- URL：`/interview/answer`
- Auth：是

### Request Body

```json
{
  "sessionId": "is_20260321_0001",
  "job_role": "前端开发工程师",
  "round": 1,
  "answer": "我有 3 年前端经验，主栈是 Vue3 和 TypeScript..."
}
```

### Success Response（推荐）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "currentRound": 2,
    "totalRounds": 10,
    "nextQuestion": "请你讲一个性能优化的真实案例，并说明你如何量化收益。",
    "finished": false,
    "instantFeedback": {
      "keyword": ["结构清晰", "案例偏少"],
      "scoreHint": 81
    }
  }
}
```

### 兼容字段（前端已容错）

- `round`（可替代 `currentRound`）
- `total_rounds`（可替代 `totalRounds`）
- `question` / `reply`（可替代 `nextQuestion`）

---

## 3.3 结束面试

- Method：`POST`
- URL：`/interview/end`
- Auth：是

### Request Body

```json
{
  "sessionId": "is_20260321_0001",
  "job_role": "前端开发工程师"
}
```

### Success Response（推荐）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260321_0001",
    "status": "finished",
    "summary": "表达清晰，技术细节较扎实，建议补充更多业务结果量化。",
    "finalScore": 84,
    "dimensions": {
      "tech": 86,
      "logic": 83,
      "expression": 85,
      "stability": 82
    }
  }
}
```

---

## 3.4 阶段节点选择（第 10/15/20 ... 题）

- Method：`POST`
- URL：`/interview/decision`
- Auth：是

### 场景说明

- 当后端返回 `awaitChoice=true`（或文案提示“结束/继续”）时，前端进入节点选择态。
- 考生可通过两种方式选择：
  1) 点击按钮；
  2) 直接输入文本并发送。

### 文本判定规则（前端已实现）

- 若考生回复包含 `结束面试 / 结束问答 / 结束 / end` -> 判定为 `decision=end`。
- 若考生回复包含 `继续问答 / 继续面试 / 继续 / continue` -> 判定为 `decision=continue`。
- 其他文本提示“请输入继续问答或结束面试”，不调用决策接口。

### Request Body

```json
{
  "sessionId": "is_20260321_0001",
  "job_role": "前端开发工程师",
  "decision": "continue"
}
```

### Success Response（继续问答）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "decision": "continue",
    "currentRound": 11,
    "totalRounds": 15,
    "nextQuestion": "好的，我们继续。请说明你做过的一个复杂故障排查案例。",
    "finished": false
  }
}
```

### Success Response（结束面试）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "decision": "end",
    "status": "finished",
    "question": "好的，本次面试到此结束，我将为你生成评估报告。",
    "finished": true
  }
}
```

---

## 4. 推荐扩展接口（第二阶段）

## 4.1 获取面试报告

- Method：`GET`
- URL：`/interview/report?sessionId=is_20260321_0001`
- Auth：是

## 4.2 获取会话消息（断线恢复）

- Method：`GET`
- URL：`/interview/session?sessionId=is_20260321_0001`
- Auth：是

---

## 5. 大模型出题策略建议（给后端）

1. 题目生成维度
- 岗位核心能力（技术深度/问题定位/表达结构）
- 简历驱动追问（基于 `techStack` 和 `projects`）
- 渐进难度（前 3 题基础，4-7 题深入，8-10 题综合）

2. 输出结构规范（建议 JSON）

```json
{
  "question": "...",
  "intent": "考察点",
  "difficulty": 3,
  "expected_keywords": ["...", "..."],
  "rubric": {
    "tech": 0.4,
    "logic": 0.3,
    "expression": 0.2,
    "stability": 0.1
  }
}
```

3. 安全与稳定
- 对用户输入长度做限制（例如 2~3000 字）
- 对提示词注入做清洗
- 大模型超时兜底返回固定追问，避免前端卡死

---

## 6. 前端当前行为说明（已实现）

前端已接入并调用：
- `POST /interview/start`
- `POST /interview/answer`
- `POST /interview/end`

若接口异常，前端会自动切换“本地模拟追问”，以保证页面可用。

当前建议：
- `start` 后持久化 `sessionId`（优先 `sessionId`，兼容 `session_id`）。
- `answer` 后读取题目字段优先级：`nextQuestion` -> `question` -> `reply`。
- 每轮 UI 显示轮次：`currentRound || round` 与 `totalRounds || total_rounds`。
- 新增节点选择优先级：
  1) 若 `awaitChoice === true`：必须先展示“结束/继续”按钮，不要自动跳转。
  2) 若用户在输入框回复“结束面试/继续问答”，前端自动转换为 `decision=end/continue` 并调用 `POST /interview/decision`。
  3) 用户点击按钮同样调用 `POST /interview/decision`（或在 `/interview/answer` 里传 `decision`）。
  4) 选择 `continue` 后，后端需把 `totalRounds` 从 `10` 扩展为 `15`（再下一节点扩展到 `20`，以此类推）。
  5) 选择 `end` 后，后端返回结束态，前端再调用 `/interview/end` + `/interview/analyze` 进入报告页。
  6) 仅当 `finished === true` 且 `awaitChoice !== true` 时，才引导调用 `/interview/end`。
- 严禁使用 `currentRound >= totalRounds` 作为自动结束条件（会误伤第10题节点选择）。

---

## 7. 联调示例

### 7.1 开始面试

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/start' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"job_role":"前端开发工程师"}'
```

### 7.2 提交回答

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/answer' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "sessionId":"is_20260321_0001",
    "job_role":"前端开发工程师",
    "round":1,
    "answer":"我负责前端性能优化..."
  }'
```

### 7.3 结束面试

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/end' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"sessionId":"is_20260321_0001","job_role":"前端开发工程师"}'
```

---

## 8. 验收清单（后端）

- [x] `/interview/start` 可返回首题 + 会话 ID
- [x] `/interview/answer` 可基于历史轮次生成下一题
- [x] `/interview/end` 可返回总结与分项评分
- [x] 所有接口返回统一 `code/message/data`
- [x] token 校验失败返回 `4010`
- [x] 接口异常时返回可读 `message`，便于前端提示

以上文档可直接交给后端同学落地“LLM 面试官”接口。

---

## 9. 当前后端已落地情况（基于本仓库）

已实现接口：
- `POST /api/v1/interview/start`
- `POST /api/v1/interview/answer`
- `POST /api/v1/interview/chat`（与 `answer` 同逻辑，兼容）
- `POST /api/v1/interview/end`

已实现能力：
- LangGraph 工作流：`check_stage -> generate_question`
- 会话持久化：`interview_sessions`（Mongo，内存回退）
- 会话状态字段：`sessionId/status/currentRound/totalRounds/messages/stage`
- 模糊回答判定与追问策略（短答/含“记不清”等关键词）

当前技术实现文件：
- `services/interview_agent.py`
- `routes/interview.py`
- `services/store.py`
- `app.py`

---

## 10. DeepSeek 云端配置（已预留）

设置以下环境变量即可启用云端模型：

```bash
export DEEPSEEK_API_KEY='你的key'
export DEEPSEEK_MODEL='deepseek-v3'
# 可选，默认即该地址
export DEEPSEEK_BASE_URL='https://api.deepseek.com/v1/chat/completions'
```

说明：
- 未配置 `DEEPSEEK_API_KEY` 时，后端会返回兜底问题，不会让前端卡死。
- 后续接入岗位题库/知识图谱时，只需实现 `services/interview_agent.py` 里的检索占位函数。

---

## 11. 前端是否需要改代码？（结论）

需要做**小幅调整**，不是重构。

### 必改项

1. 保证请求地址统一：
- `BASE_URL = http://127.0.0.1:3000/api/v1`

2. `start` 成功后保存会话 ID：
- 优先取 `data.sessionId`，兜底 `data.session_id`

3. `answer` 返回题目解析兼容：
- 按顺序读取 `data.nextQuestion || data.question || data.reply`

4. 轮次字段兼容：
- `currentRound || round`
- `totalRounds || total_rounds`

5. 结束条件处理（与前端现状一致）：
- 优先判断 `awaitChoice`：若 `awaitChoice === true`，必须先展示“结束/继续”按钮，禁止自动跳转
- 若 `finished === true` 且 `awaitChoice !== true`，前端只提示“请点击结束面试生成报告”，不会自动调用 `/interview/end`，需用户主动点击
- 禁止使用 `currentRound >= totalRounds` 作为自动结束条件

6. 错误处理：
- `code === 4010`：跳登录
- `code === 4040`：提示“会话不存在，请重新开始”
- `code === 4090`：提示“会话已结束”

### 可选优化

- 优先调用 `/interview/chat`（后端已兼容，当前等价于 `/interview/answer`）。
- 添加“重试本轮”按钮（网络抖动时不丢会话）。

以上即前端需要同步的改动清单。

---

## 12. 新增岗位后的后端操作说明

新增“大模型应用开发工程师”后，后端建议同步做以下操作：

1. 更新岗位列表来源（`/interview/jobs`）
- 若岗位从数据库读取：向 `jobs` 集合新增一条：

```json
{ "id": "j_004", "name": "大模型应用开发工程师" }
```

- 若岗位写死在代码中：在岗位枚举常量中追加该项。

2. 更新出题模板/提示词路由
- 在 LLM prompt 里新增该岗位的能力维度（如：RAG、Agent、模型评测、推理优化、生产化落地）。

3.（可选）更新首页热岗
- `/dashboard/home` 的 `hotJobs` 中可新增该岗位，保证首页与岗位选择一致。

4. 验证
- `GET /api/v1/interview/jobs` 返回包含 `大模型应用开发工程师`。
- 该岗位调用 `/interview/start` 能正常返回首题。
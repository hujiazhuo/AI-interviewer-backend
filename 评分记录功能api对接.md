# 评分记录功能 API 对接文档（V1）

> 用途：支持“评分记录页 + 报告详情页 + 面试结束生成报告”完整链路。  
> 前端页面：
> - `/pages/interview/records`
> - `/pages/interview/report_detail`
> - `/pages/interview/interview_chat`（结束后生成报告）
>
> 联调基线：`http://127.0.0.1:3000/api/v1`

---

## 1. 基础约定

- Base URL：`http://127.0.0.1:3000/api/v1`
- Content-Type：`application/json`
- 鉴权：`Authorization: Bearer <token>`（必填）
- 响应格式：统一 `code/message/data`

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
| 4040 | 记录/报告不存在 |
| 4090 | 会话已结束或状态冲突 |
| 5000 | 服务端异常 |

---

## 2. 功能链路

1. 用户在面试聊天页点击“结束面试”
2. 前端调用：`POST /interview/end`
3. 前端调用：`POST /interview/analyze`（兼容旧路径 `/analyze`）
4. 后端返回 `reportId`
5. 前端跳转报告详情：`/pages/interview/report?id=<reportId>`
6. 报告页调用：`GET /interview/report?id=<reportId>`（兼容旧路径 `/report?id=...`）
7. 首页/记录页调用：`GET /interview/records?limit=3`（兼容旧路径 `/records`）

---

## 3. 接口定义

## 3.1 获取评分记录列表

- Method：`GET`
- URL：`/interview/records`
- Auth：是
- Query（可选）：
  - `limit`：返回条数（如 `3` / `50`）
  - `page`：页码（可选）
  - `pageSize`：分页大小（可选）

### Success Response（推荐）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "records": [
      {
        "id": "rpt_20260322_001",
        "job_role": "前端开发工程师",
        "score": 84,
        "currentRound": 10,
        "totalRounds": 10,
        "createdAt": "2026-03-22T10:30:00+08:00"
      },
      {
        "id": "rpt_20260321_013",
        "job_role": "大模型应用开发工程师",
        "score": 88,
        "currentRound": 10,
        "totalRounds": 10,
        "createdAt": "2026-03-21T18:10:00+08:00"
      }
    ],
    "total": 2
  }
}
```

### 前端兼容字段（已适配）

每条记录可兼容读取：
- `id || recordId || reportId || sessionId`
- `job || job_role`
- `score || finalScore || totalScore`
- `date || createdAt`
- `currentRound || round`
- `totalRounds || total_rounds`

---

## 3.2 获取报告详情

- Method：`GET`
- URL：`/interview/report?id=<reportId>`
- Auth：是

### Success Response（推荐）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "rpt_20260322_001",
    "job_role": "前端开发工程师",
    "finalScore": 84,
    "summary": "表达清晰，技术细节较扎实，建议补充更多业务量化结果。",
    "dimensions": {
      "tech": 86,
      "logic": 83,
      "match": 82,
      "expression": 85,
      "stability": 82
    },
    "strengths": ["表达结构清晰", "项目拆解有条理"],
    "weaknesses": ["量化结果偏少", "风险评估不够充分"],
    "suggestions": [
      "补充性能优化案例的前后指标",
      "准备系统设计中容量评估的推导过程",
      "强化复杂故障定位叙述"
    ],
    "messages": [
      { "role": "ai", "content": "请做一个简短自我介绍" },
      { "role": "user", "content": "你好，我有3年前端经验..." }
    ],
    "createdAt": "2026-03-22T10:30:00+08:00"
  }
}
```

### 前端兼容字段（已适配）

- 总分：`finalScore || score`
- 亮点：`strengths || highlights`
- 待改进：`weaknesses || improvements`

---

## 3.3 结束面试

- Method：`POST`
- URL：`/interview/end`
- Auth：是

### Request Body

```json
{
  "sessionId": "is_20260322_0001",
  "job_role": "前端开发工程师"
}
```

### Success Response（示例）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260322_0001",
    "status": "finished"
  }
}
```

---

## 3.4 生成深度报告（结束后调用）

- Method：`POST`
- URL：`/interview/analyze`
- Auth：是

> 兼容旧路径：`POST /analyze`

### Request Body

```json
{
  "sessionId": "is_20260322_0001",
  "job_role": "前端开发工程师"
}
```

### Success Response（推荐）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "rpt_20260322_001",
    "reportId": "rpt_20260322_001",
    "sessionId": "is_20260322_0001",
    "status": "processing"
  }
}
```

> 前端可读取：`id || reportId || report_id || sessionId`
>
> 说明：`/interview/analyze` 为异步任务，通常 1~10 秒完成。前端拿到 `reportId` 后调用
> `GET /interview/report?id=<reportId>` 轮询，直到 `status=ready`。

### 报告评分字段（已落地）

- `total_score`：总分（0-100）
- `tech_score`：技术深度
- `logic_score`：逻辑严密性
- `match_score`：岗位匹配度
- `expression_score`：表达清晰度
- `summary`：一句话总结
- `strengths`：3 条优势
- `weaknesses`：3 条短板
- `suggestions`：3 条提升建议
- `chat_history`：完整对话 JSON

---

## 3.5 删除评分记录（新增）

- Method：`DELETE`
- URL：`/interview/records?id=<reportId>`
- Auth：是

> 兼容实现可选：
> - `DELETE /interview/records/:id`
> - `POST /interview/records/delete`（body: `{ "id": "..." }`）

### Success Response（推荐）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "rpt_20260322_001",
    "deleted": true
  }
}
```

---

## 4. 数据库模型建议

### 4.1 评分记录（可与报告同表或拆分）

集合建议：`interview_reports`

```json
{
  "_id": "ObjectId",
  "id": "rpt_20260322_001",
  "userId": "u_10001",
  "sessionId": "is_20260322_0001",
  "job_role": "前端开发工程师",
  "finalScore": 84,
  "summary": "...",
  "dimensions": {
    "tech": 86,
    "logic": 83,
    "match": 82,
    "expression": 85,
    "stability": 82
  },
  "strengths": ["..."],
  "weaknesses": ["..."],
  "suggestions": ["..."],
  "messages": [{ "role": "ai", "content": "..." }],
  "createdAt": "2026-03-22T10:30:00+08:00",
  "updatedAt": "2026-03-22T10:31:00+08:00"
}
```

### 4.2 索引建议

- `userId + createdAt` 复合索引（记录列表）
- `id` 唯一索引（报告详情查询）
- `sessionId` 索引（会话追踪）

---

## 5. 与前端页面映射关系

1. 首页评分卡（最近 3 条）
- 取 `/interview/records?limit=3`
- 展示：岗位 + 分数
- 点击跳转：`/pages/interview/records`

2. 评分记录页
- 取 `/interview/records?limit=50`
- 展示：岗位、分数、时间、轮次
- 点击记录跳：`/pages/interview/report_detail?id=<id>`

3. 报告详情页
- 取 `/interview/report?id=<id>`
- 展示：总分、雷达图、AI 总评、优劣势、建议、对话回顾

---

## 6. 联调示例

### 6.1 获取记录

```bash
curl 'http://127.0.0.1:3000/api/v1/interview/records?limit=3' \
  -H 'Authorization: Bearer <token>'
```

### 6.2 结束会话

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/end' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"sessionId":"is_20260322_0001","job_role":"前端开发工程师"}'
```

### 6.3 生成报告

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/analyze' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"sessionId":"is_20260322_0001","job_role":"前端开发工程师"}'
```

### 6.4 获取报告详情

```bash
curl 'http://127.0.0.1:3000/api/v1/interview/report?id=rpt_20260322_001' \
  -H 'Authorization: Bearer <token>'
```

---

## 7. 后端验收清单

- [ ] `/interview/records` 返回记录列表（至少含 id/job_role/score/createdAt）
- [ ] `/interview/report?id=` 返回完整报告结构
- [ ] `/interview/end` 可正常结束会话
- [ ] `/interview/analyze` 可返回 reportId
- [ ] 统一响应结构 `code/message/data`
- [ ] 鉴权失败返回 `4010`
- [ ] 记录列表按时间倒序

以上文档可直接交由后端落地“评分记录与报告”对接。

---

## 8. 前端对接必做项（需要）

是的，前端还有对接项，以下为必须完成：

1. 面试结束后跳转评分页
- 在面试页点击“结束面试”后，按顺序调用：
  - `POST /interview/end`
  - `POST /interview/analyze`
- 从 analyze 响应读取 `reportId`，立即跳转详情页并携带参数：
  - `/pages/interview/report_detail?id=<reportId>`

2. 详情页轮询异步评分结果
- 初次进入详情页即请求：`GET /interview/report?id=<reportId>`
- 当 `status=processing` 时显示“正在生成评分报告”，并每 1 秒轮询一次（建议最多 15 次）
- 当 `status=ready` 时停止轮询并渲染报告
- 当 `status=failed` 时展示失败态与“重试分析”按钮

3. 首页评分记录卡片联动
- 首页评分记录模块请求：`GET /interview/records?limit=3`
- 点击卡片跳转：`/pages/interview/records`

4. 评分记录页联动
- 页面加载请求：`GET /interview/records?limit=50`
- 渲染字段：岗位、分数、时间、轮次
- 点击某条记录跳转：`/pages/interview/report_detail?id=<id>`

5. 字段兼容读取（前端必须）
- 记录 id：`id || recordId || reportId || sessionId`
- 分数：`score || finalScore || totalScore`
- 亮点：`strengths || highlights`
- 待改进：`weaknesses || improvements`

6. 登录态失效处理
- 任一接口返回 `4010`：清理本地 token，跳转登录页

7. 删除无效评分记录
- 在评分记录列表每项提供“删除”按钮（需二次确认）
- 调用：`DELETE /interview/records?id=<id>`（或兼容路径）
- 删除成功后本地移除该条并刷新首页评分汇总
# 升级 RAG API 对接文档（V2）

> 目标：落地“可进化”的模拟面试引擎（Advanced RAG + 双路径评分 + 联网补全）
>
> 适用前端页面：
> - `/pages/interview/interview_chat`
> - `/pages/interview/records`
> - `/pages/interview/report_detail`
>
> 当前项目联调基线：`http://127.0.0.1:3000/api/v1`

---

## 0. 重要说明（先看）

1. **知识库目录名**
  - 当前仓库目录已统一为 `knowledge/`。
  - 后端配置请固定指向该目录，避免扫描路径不一致。

2. **Tavily Key 安全要求**
   - 不要把 key 写入代码或提交到 git。
   - 使用环境变量：`TAVILY_API_KEY`。
   - 你给的 key 建议立即在 Tavily 控制台轮换一次后再用于正式演示。

3. **对接目标**
   - 不是只改接口名，而是把“出题-评分-进化”闭环的数据结构一次性定清楚。

---

## 1. 总体能力与链路

### 1.1 系统能力

- 高级入库：Markdown 分层切分（`MarkdownHeaderTextSplitter`）+ Chroma 持久化。
- 智能出题：简历关键词 + 查询改写 + 知识库检索 + 重排序。
- 双路径评分：
  - 路径 A（命中高）：依据本地知识库评分；
  - 路径 B（命中低）：联网（Tavily）+ LLM 评分。
- 知识进化：路径 B 的“新题+参考答案”回写知识库并重新向量化。

### 1.2 LangGraph 状态机建议

`START -> LOAD_RESUME -> REWRITE_QUERY -> RETRIEVE -> RERANK -> GENERATE_QUESTION -> ANSWER_EVAL -> ROUTE_SCORE(A/B) -> BUILD_REPORT -> WRITEBACK(optional) -> NEXT_ROUND/END`

---

## 2. 基础约定

- Base URL：`http://127.0.0.1:3000/api/v1`
- Content-Type：`application/json`
- Auth：`Authorization: Bearer <token>`（必填）
- 响应结构统一：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 2.1 错误码建议

| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数错误 |
| 4010 | 未登录或 token 失效 |
| 4040 | 资源不存在（session/report/doc） |
| 4090 | 状态冲突（会话已结束等） |
| 4220 | LLM 输出不可解析 |
| 4290 | 频率限制 |
| 5000 | 服务端异常 |
| 5031 | 向量库不可用 |
| 5032 | Tavily 不可用 |

---

## 3. 配置中心（阈值可调）

建议后端提供配置读取（`config.yaml` + 热更新可选）：

```yaml
rag:
  similarity_threshold: 0.80
  top_k_retrieve: 10
  top_k_rerank: 3
  enable_tavily_fallback: true
  writeback_on_web_mode: true
  writeback_min_score: 0.65
knowledge:
  dir: "./knowledge"
  collection_name: "interview_kb"
```

### 3.0 当前落地状态（第 1 步已完成）

当前后端已先落地环境变量配置基线（便于快速联调，后续再补 `config.yaml` 与管理接口）：

- `TAVILY_API_KEY`
- `TAVILY_BASE_URL`
- `SIMILARITY_THRESHOLD`
- `RAG_TOP_K_RETRIEVE`
- `RAG_TOP_K_RERANK`
- `ENABLE_TAVILY_FALLBACK`
- `WRITEBACK_ON_WEB_MODE`
- `KNOWLEDGE_DIR`
- `RAG_COLLECTION_NAME`
- `RAG_PERSIST_DIR`

说明：所有变量均通过 `.env.local/.env` 加载，不在代码中硬编码密钥。

### 3.1 获取当前配置（建议新增）

- Method：`GET`
- URL：`/rag/config`

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "similarity_threshold": 0.8,
    "top_k_retrieve": 10,
    "top_k_rerank": 3,
    "enable_tavily_fallback": true,
    "writeback_on_web_mode": true
  }
}
```

> 当前已落地：`GET /rag/config`，用于前端与联调脚本读取实时阈值与策略开关。

---

## 4. 知识库构建接口

### 4.0 当前落地状态（第 2 步已完成）

已完成：

- 使用 `MarkdownHeaderTextSplitter` 进行按标题层级切分。
- 使用 Chroma 持久化向量库存储（`RAG_PERSIST_DIR`）。
- 已提供两个后端接口：
  - `POST /rag/knowledge/rebuild`
  - `POST /rag/knowledge/ingest`

说明：当前向量 embedding 先使用后端内置哈希向量（轻量可运行版本），后续第 4/6 步会切换到更强 embedding + 重排序链路。

## 4.1 全量重建索引

- Method：`POST`
- URL：`/rag/knowledge/rebuild`
- 说明：扫描 `knowledge/` 下 md，分层切分后重建 Chroma。

### Request

```json
{
  "force": true,
  "source_dir": "./knowledge"
}
```

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "files": 28,
    "chunks": 1460,
    "collection": "interview_kb",
    "costMs": 3240
  }
}
```

## 4.2 增量入库

- Method：`POST`
- URL：`/rag/knowledge/ingest`

### Request

```json
{
  "paths": ["./knowledge/java/redis.md", "./knowledge/system/design.md"]
}
```

## 4.3 检索调试（便于联调）

- Method：`POST`
- URL：`/rag/knowledge/retrieve`

### Request

```json
{
  "query": "Redis 持久化和主从复制",
  "topK": 10,
  "with_rerank": true
}
```

### Response（示例）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "rewrites": [
      "Redis 面试题 持久化 RDB AOF",
      "Redis 主从复制 原理 一致性",
      "Redis 哨兵 故障转移 面试"
    ],
    "hits": [
      {
        "docId": "java_redis_001",
        "score": 0.86,
        "rerankScore": 0.93,
        "source": "knowledge/java/redis.md",
        "headerPath": "Redis > 持久化",
        "content": "..."
      }
    ]
  }
}
```

### 4.4 当前落地状态（第 5 步已完成）

已实现“进阶检索 + 二次重排序”联调接口：

- `POST /rag/knowledge/retrieve`

当前后端流程：

1. 先调用查询改写生成 3 条检索词；
2. 用 3 条改写词分别检索 Chroma；
3. 合并去重后按 `score` 排序；
4. 可选触发二次重排序（LLM rerank，失败自动降级到词法重排）；
5. 返回 `hits` 与 `reranked` 两份结果，便于前端调试展示。

---

## 5. 面试会话与智能出题

### 5.2 当前落地状态（第 6 步已完成）

已把“进阶检索结果”接入实际出题链路（`/interview/start` 与 `/interview/answer`）：

- 每轮出题会执行：简历关键词提取 -> 查询改写 -> 检索 -> 重排序 -> 生成问题。
- 接口响应新增：
  - `trace`：前端可直接展示的思考轨迹文案；
  - `retrieval`：检索依据摘要（`rewrites/topSource/topScore/rerankSource/hitCount`）。

说明：若检索链路不可用，会自动回退到模型直出，不影响主流程可用性。

#### 前端策略参数（已对齐）

后端已支持从 `start/answer` 读取以下字段并生效：

- `question_policy.mode`：`balanced | project-lite | project-deep`
- `question_policy.randomness`：`low | medium | high`
- `question_policy.avoid_repeat`
- `knowledge_scope`：`java | network | llm | general`
- `asked_questions`：最近题目列表（用于去重）

效果：减少过度项目追问、增强题目随机性、降低同岗位重复题。

### 5.0 当前落地状态（第 3 步已完成）

已新增“简历关键词提取器”接口（仅提取与输出，不改评分链路）：

- `POST /rag/resume/keywords`

可从请求体 `resume` 直接提取；若未传 `resume`，默认读取当前登录用户已保存简历。

#### Request

```json
{
  "topN": 20,
  "resume": {
    "techStack": "Java, Redis, MySQL",
    "projects": [
      {
        "name": "订单系统",
        "highlights": "削峰填谷、缓存优化"
      }
    ]
  }
}
```

#### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "keywords": ["Redis", "MySQL", "订单系统"],
    "weighted": [
      {"term": "Redis", "weight": 5.4}
    ],
    "totalCandidates": 18,
    "source": "body"
  }
}
```

### 5.1 当前落地状态（第 4 步已完成）

已新增查询改写接口（LLM 改写为 3 条检索词，失败自动降级）：

- `POST /rag/query/rewrite`

#### Request

```json
{
  "query": "我用过消息队列",
  "job_role": "Java后端开发工程师",
  "keywords": ["Kafka", "RocketMQ", "分布式事务"]
}
```

> `keywords` 可选；若不传，后端会优先从当前用户已保存简历中提取关键词。

#### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "query": "我用过消息队列",
    "job_role": "Java后端开发工程师",
    "keywords": ["Kafka", "RocketMQ"],
    "rewrites": [
      "消息队列面试题 Java后端开发工程师",
      "RocketMQ 与 Kafka 区别",
      "分布式事务中的消息可靠性"
    ],
    "source": "llm"
  }
}
```

## 5.1 开始面试（增强）

- Method：`POST`
- URL：`/interview/start`

### Request

```json
{
  "job_role": "Java后端开发工程师",
  "resume": {
    "workYears": "3年",
    "techStack": ["Java", "Redis", "MySQL"],
    "projects": [
      { "name": "订单系统", "highlights": "削峰填谷、缓存优化" }
    ]
  }
}
```

### Response（必须返回可视化轨迹）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "is_20260326_0001",
    "currentRound": 1,
    "totalRounds": 10,
    "question": "请讲讲你在订单系统中如何用 Redis 抗住高并发。",
    "trace": [
      "🔍 正在基于你的简历匹配知识库...",
      "💡 发现简历中的 Redis 亮点，正在检索底层原理..."
    ],
    "retrieval": {
      "rewrites": ["Redis 高并发 面试题", "缓存击穿雪崩穿透", "Redis + MySQL 一致性"],
      "topSource": "knowledge/java/redis.md",
      "topScore": 0.84
    }
  }
}
```

## 5.2 提交回答（增强）

- Method：`POST`
- URL：`/interview/answer`

### Request

```json
{
  "sessionId": "is_20260326_0001",
  "job_role": "Java后端开发工程师",
  "round": 1,
  "answer": "..."
}
```

### Response（支持前端思考轨迹显示）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answeredRound": 1,
    "nextQuestionRound": 2,
    "totalRounds": 10,
    "nextQuestion": "如果 Redis 挂了，你如何保证业务可用？",
    "finished": false,
    "trace": [
      "🧠 正在判断该题是否命中知识库阈值...",
      "📚 命中知识库，下一题将深入高可用设计"
    ],
    "routeHint": "kb"
  }
}
```

### 5.3 轮次节点选择（新增）

后端已支持“10题首轮 + 每次续问5题”的循环：

- 当考生回答到第 `10/15/20/...` 题时，后端先返回本题评价，再提示考生选择；
- 选择 `end`：结束面试，5 秒后进入评分环节；
- 选择 `continue`：继续问答，系统追加 5 题并继续循环。

节点响应（`POST /interview/answer`）示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answeredRound": 10,
    "awaitChoice": true,
    "decisionOptions": ["end", "continue"],
    "decisionDelayMs": 5000,
    "question": "评价：...\n纠正：...\n本次面试已到阶段节点。你可以选择...",
    "finished": false
  }
}
```

提交选择支持两种方式：

1) `POST /interview/decision`

```json
{
  "sessionId": "is_20260326_0001",
  "decision": "continue"
}
```

2) 兼容 `POST /interview/answer`

```json
{
  "sessionId": "is_20260326_0001",
  "decision": "end"
}
```

---

## 6. 双路径评分与报告

### 6.0 当前落地状态（第 7 步已完成）

已新增“双路径评分判定器”（阈值分流）：

- 根据对话内容检索知识库并计算最高相似度；
- 当 `similarity >= SIMILARITY_THRESHOLD`：走 `kb` 路径（参考本地知识库片段评分）；
- 当 `similarity < SIMILARITY_THRESHOLD`：走 `web` 路径（当前先用通用模型评分，下一步接入 Tavily）。

报告新增字段：

- `scorePath`：`kb | web | pending`
- `scoreRouteMeta`：`similarity/threshold/reason`
- `evidenceChunks`：评分依据片段列表

### 6.1 当前落地状态（第 8 步已完成）

已接入 Tavily 联网评分路径（`web` 分支）：

- 当 `scorePath=web` 时，后端会调用 Tavily 搜索实时参考资料；
- 将联网结果作为评分上下文传给 LLM；
- 在报告详情中返回 `webSources`（title/url/content/score），用于前端“评分溯源”展示。

### 6.2 当前落地状态（第 9 步已完成）

已实现知识库“自进化写回”（web 路径）：

- 当 `scorePath=web` 时，将本轮新问题 + 联网参考内容追加写入 `knowledge/evolution_kb.md`；
- 写回后自动触发 `rag/knowledge/ingest` 等价能力进行增量向量化；
- 报告详情新增：
  - `growthNote`：系统成长提示文案；
  - `evolution`：写回结果（`written/reason/file/fingerprint/ingest`）。

并新增写回质量控制：

- 写回策略已放宽：默认尽量写回，不再因短回答/低分来源频繁拦截；
- 低质量样本通过 `lowConfidence=true` 标记，供后续筛选；
- 增量入库失败时自动回滚 Markdown 文件，避免污染知识库。

当前联调建议（测试阶段）：

- `WRITEBACK_ON_WEB_MODE=true`
- `EVOLUTION_KB_FILE=evolution_kb.md`

## 6.1 结束会话

- Method：`POST`
- URL：`/interview/end`

## 6.2 触发分析（异步）

- Method：`POST`
- URL：`/interview/analyze`

### Request

```json
{
  "sessionId": "is_20260326_0001",
  "job_role": "Java后端开发工程师"
}
```

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "rpt_20260326_0001",
    "status": "processing"
  }
}
```

## 6.3 获取报告（核心字段）

- Method：`GET`
- URL：`/interview/report?id=<reportId>`

### Response（ready）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "rpt_20260326_0001",
    "status": "ready",
    "job_role": "Java后端开发工程师",
    "total_score": 86,
    "tech_score": 88,
    "logic_score": 84,
    "match_score": 87,
    "expression_score": 82,
    "stability_score": 86,
    "summary": "...",
    "strengths": ["..."],
    "weaknesses": ["..."],
    "suggestions": ["..."],
    "chat_history": [{ "role": "ai", "content": "..." }],
    "questions": [
      {
        "round": 1,
        "question": "...",
        "answer": "...",
        "score": 82,
        "scoreRoute": "kb",
        "similarity": 0.86,
        "threshold": 0.8,
        "evidence": {
          "type": "kb",
          "kbSnippets": [
            {
              "source": "knowledge/java/redis.md",
              "headerPath": "Redis > 缓存击穿",
              "content": "..."
            }
          ],
          "webSources": []
        }
      },
      {
        "round": 2,
        "question": "...",
        "answer": "...",
        "score": 79,
        "scoreRoute": "web",
        "similarity": 0.62,
        "threshold": 0.8,
        "evidence": {
          "type": "web",
          "kbSnippets": [],
          "webSources": [
            {
              "title": "Redis Best Practices",
              "url": "https://...",
              "snippet": "..."
            }
          ]
        },
        "evolution": {
          "writeback": true,
          "topic": "Redis 高可用主从切换",
          "targetFile": "knowledge/evolution_kb.md"
        }
      }
    ],
    "growthSummary": "本次面试中，AI 通过联网学习了 Redis 高可用切换策略，并已同步至你的个人专属知识库。"
  }
}
```

### Response（processing / failed）

```json
{
  "code": 0,
  "message": "ok",
  "data": { "id": "rpt_20260326_0001", "status": "processing" }
}
```

```json
{
  "code": 0,
  "message": "ok",
  "data": { "id": "rpt_20260326_0001", "status": "failed", "reason": "rerank timeout" }
}
```

---

## 7. 评分记录（含删除）

## 7.1 获取列表

- Method：`GET`
- URL：`/interview/records?limit=50`

## 7.2 删除记录

- Method：`DELETE`
- URL：`/interview/records?id=<reportId>`

---

## 8. 前端字段对接清单（必须）

## 8.1 interview_chat.vue

1. 渲染 `trace[]`（思考轨迹）
2. 轮次推进优先使用：`nextQuestionRound`（已改过）
3. 提问后显示 `routeHint`（`kb/web`）可选标签
4. 当 `awaitChoice=true` 时展示“结束/继续”按钮，并按 `decisionDelayMs` 处理 5 秒延时响应
5. 提交选择可调用：`/interview/decision`（推荐）或 `/interview/answer`（兼容）

## 8.2 report_detail.vue

1. 每题显示 `scoreRoute`：
   - `kb`：依据本地官方知识库
   - `web`：依据全网实时搜索
2. 渲染 `evidence.kbSnippets` 或 `evidence.webSources`
3. 页面尾部展示 `growthSummary`
4. 长文本建议分段渲染 + loading skeleton

## 8.3 index.vue（雷达与记录）

1. 仅使用真实 records/report 数据汇总
2. 删除无效记录后需重新拉取列表并重算雷达图

---

## 9. Tavily 联网策略（后端）

1. 相似度判定：
   - 若 `similarity > similarity_threshold` -> 路径 A（知识库评分）
   - 否则 -> 路径 B（Tavily + LLM）

2. Tavily 调用参数建议：
   - `max_results`: 3~5
   - 优先技术站点（官方文档、知名技术博客）

3. 回写规则：
   - 仅在路径 B 且结果质量通过时写回
  - 统一追加到 `knowledge/evolution_kb.md`（不改动原始岗位题库，避免污染）
  - 追加 markdown 模板：

```md
## [技术点] Redis 高可用主从切换

### 面试题
...

### 参考答案（来自联网归纳）
...

### 来源
- https://...
- https://...
```

4. 前端改动要求：
  - 本次仅后端实现变更，前端无需新增字段即可正常联调。
  - 现有 `reportDetail.evolution` 与 `growthNote` 展示逻辑可继续复用。

---

## 10. 联调示例

### 10.1 触发知识库重建

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/rag/knowledge/rebuild' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"force":true,"source_dir":"./knowledge"}'
```

### 10.2 启动面试（含简历）

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/interview/start' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "job_role":"Java后端开发工程师",
    "resume":{"techStack":["Java","Redis"],"projects":[{"name":"订单系统"}]}
  }'
```

### 10.3 获取报告

```bash
curl 'http://127.0.0.1:3000/api/v1/interview/report?id=rpt_20260326_0001' \
  -H 'Authorization: Bearer <token>'
```

---

## 11. 答辩亮点（可直接放 PPT）

1. 闭环进化：
   - 系统通过“面试 -> 联网 -> 入库 -> 再检索”自动迭代知识库。
2. 双模打分：
   - 高命中走知识库保权威，低命中走联网保前沿。
3. 深度 RAG：
   - 查询改写 + 二次精排，显著降低传统 RAG 检索偏差。

---

## 12. 最小上线验收（Checklist）

- [ ] `knowledge/` 目录可被后端扫描
- [ ] `/rag/knowledge/rebuild` 可成功返回 chunks 数
- [ ] `/interview/start` 返回 `trace`
- [ ] `/interview/answer` 返回 `nextQuestionRound`
- [ ] `/interview/report` 返回 `questions[].scoreRoute + evidence + growthSummary`
- [ ] 低相似度场景可走 Tavily 分支
- [ ] 路径 B 可写回 md 并支持增量向量化
- [ ] 删除评分记录后首页雷达图可重算

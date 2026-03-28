# 简历功能 API 对接文档（V1）

> 用途：支持“简历内容填写页”保存到数据库，并回传首页简历完整度。  
> 前端页面：/pages/resume/resume_edit  
> 联调基线：`http://127.0.0.1:3000/api/v1`

---

## 1. 总体约定

- Base URL：`http://127.0.0.1:3000/api/v1`
- Content-Type：`application/json`
- 鉴权：`Authorization: Bearer <token>`（必填）
- 时间格式：ISO 8601（例如 `2026-03-21T10:30:00+08:00`）

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
| 4040 | 简历不存在 |
| 5000 | 服务端异常 |

---

## 2. 数据模型（建议）

集合名建议：`resumes`

```json
{
  "_id": "ObjectId",
  "userId": "u_10001",
  "name": "张三",
  "targetJobIndustry": "大模型应用开发工程师·互联网",
  "workYears": "1-3年",
  "interviewTypes": ["技术面", "项目面"],
  "techStack": "Python, FastAPI, Vue3, LangChain",
  "mastery": "Python-掌握, LangChain-熟悉, Vue3-掌握",
  "directions": ["大模型应用", "后端"],
  "projects": [
    {
      "name": "智能问答系统",
      "responsibility": "负责后端架构、知识库检索与接口设计",
      "challengeSolution": "针对召回噪声问题引入重排序模型并优化分块策略",
      "quantResult": "准确率提升 18%，平均响应时延降低 32%"
    }
  ],
  "completeness_score": 86,
  "isDraft": false,
  "createdAt": "2026-03-21T10:30:00+08:00",
  "updatedAt": "2026-03-21T10:45:00+08:00"
}
```

说明：
- 每个 `userId` 建议只保留 1 条主简历（更新覆盖）。
- 如需要历史版本，可额外增加 `resume_versions` 集合。

---

## 3. 接口定义

## 3.1 保存简历（主接口）

- Method：`POST`
- URL：`/resume/save`
- Auth：是

### Request Body

```json
{
  "name": "张三",
  "targetJobIndustry": "大模型应用开发工程师·互联网",
  "workYears": "1-3年",
  "interviewTypes": ["技术面", "项目面"],
  "techStack": "Python, FastAPI, Vue3, LangChain",
  "mastery": "Python-掌握, LangChain-熟悉, Vue3-掌握",
  "directions": ["大模型应用", "后端"],
  "projects": [
    {
      "name": "智能问答系统",
      "responsibility": "负责后端架构、知识库检索与接口设计",
      "challengeSolution": "针对召回噪声问题引入重排序模型并优化分块策略",
      "quantResult": "准确率提升 18%，平均响应时延降低 32%"
    }
  ],
  "completeness_score": 86
}
```

### Success Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "resumeId": "r_10001",
    "userId": "u_10001",
    "completeness_score": 86,
    "updatedAt": "2026-03-21T10:45:00+08:00"
  }
}
```

### Fail Response（参数错误）

```json
{
  "code": 4001,
  "message": "参数校验失败",
  "data": null
}
```

### 后端处理建议

- 依据 token 解析 `userId`。
- 使用 `upsert`：
  - 已存在该用户简历则更新。
  - 不存在则新建。
- `completeness_score` 建议后端再计算一次（避免前端伪造），前端传值作为参考。

---

## 3.2 获取我的简历（用于回填编辑页）

- Method：`GET`
- URL：`/resume/my`
- Auth：是

### Success Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "name": "张三",
    "targetJobIndustry": "大模型应用开发工程师·互联网",
    "workYears": "1-3年",
    "interviewTypes": ["技术面", "项目面"],
    "techStack": "Python, FastAPI, Vue3, LangChain",
    "mastery": "Python-掌握, LangChain-熟悉, Vue3-掌握",
    "directions": ["大模型应用", "后端"],
    "projects": [
      {
        "name": "智能问答系统",
        "responsibility": "负责后端架构、知识库检索与接口设计",
        "challengeSolution": "针对召回噪声问题引入重排序模型并优化分块策略",
        "quantResult": "准确率提升 18%，平均响应时延降低 32%"
      }
    ],
    "completeness_score": 86,
    "updatedAt": "2026-03-21T10:45:00+08:00"
  }
}
```

### 无数据时建议返回

```json
{
  "code": 0,
  "message": "ok",
  "data": null
}
```

---

## 3.3（可选）保存草稿

> 前端目前已做本地草稿。若要云端草稿，可增加该接口。

- Method：`POST`
- URL：`/resume/draft/save`
- Auth：是

Request 同 `/resume/save`，仅增加：

```json
{
  "isDraft": true
}
```

---

## 4. 与首页联动要求

首页接口 `/dashboard/home` 返回中需包含：

```json
{
  "resume": {
    "completion": 82,
    "completeness_score": 86
  }
}
```

前端兼容逻辑：
- 优先读取 `resume.completeness_score`
- 兜底 `resume.completion`

---

## 5. 前端当前已对接字段（请后端保持一致）

- `name`
- `targetJobIndustry`
- `workYears`
- `interviewTypes`（数组）
- `techStack`
- `mastery`
- `directions`（数组）
- `projects`（数组，元素包含 `name/responsibility/challengeSolution/quantResult`）
- `completeness_score`

---

## 6. 联调示例

### 6.1 保存简历

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/resume/save' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "name":"张三",
    "targetJobIndustry":"大模型应用开发工程师·互联网",
    "workYears":"1-3年",
    "interviewTypes":["技术面","项目面"],
    "techStack":"Python,FastAPI,Vue3,LangChain",
    "mastery":"Python-掌握,LangChain-熟悉,Vue3-掌握",
    "directions":["大模型应用","后端"],
    "projects":[{
      "name":"智能问答系统",
      "responsibility":"负责后端架构、知识库检索与接口设计",
      "challengeSolution":"重排序+分块优化",
      "quantResult":"准确率提升18%"
    }],
    "completeness_score":86
  }'
```

### 6.2 获取我的简历

```bash
curl 'http://127.0.0.1:3000/api/v1/resume/my' \
  -H 'Authorization: Bearer <token>'
```

---

## 7. 落地建议（后端）

- `resumes.userId` 建唯一索引。
- `updatedAt` 每次写入更新。
- 对数组字段做类型校验（防止字符串误传）。
- 对 `projects` 至少保留 1 条空模板或允许空数组（按业务决定）。
- 便于后续 AI 提问，可额外预处理字段：
  - `keywords`（从技术栈/项目自动抽取）
  - `risk_points`（表述模糊点）

以上即为简历功能数据库持久化的对接契约。
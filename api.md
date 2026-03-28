# AI全真模拟面试与能力提升平台 - 前后端接口文档（V1.1）

> 说明：本文档用于前后端联调。当前后端已支持 MongoDB 持久化（登录注册、Token、岗位列表、首页聚合数据、简历诊断记录）。

## 1. 基础约定

- Base URL：`/api/v1`
- 本地联调地址：`http://127.0.0.1:3000/api/v1`
- 数据格式：`application/json`
- 鉴权方式：`Authorization: Bearer <token>`（登录后接口需要）
- 时间格式：ISO 8601（如 `2026-03-20T10:00:00+08:00`）

### 1.1 统一响应结构

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

- `code = 0` 表示成功
- 非 0 表示失败（见错误码）

### 1.2 通用错误码

| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数校验失败 |
| 4002 | 用户名或密码错误 |
| 4003 | 用户名已存在 |
| 4010 | 未登录或 token 失效 |
| 5000 | 服务端异常 |

### 1.3 MongoDB 连接与环境变量

后端默认使用以下连接串：

```text
mongodb://root:K6F659ndB2y8fj89@test-db-mongodb.ns-qrpnjool.svc:27017
```

可通过环境变量覆盖：

- `MONGODB_URI`：MongoDB 连接串
- `MONGODB_DB`：数据库名（默认 `interview_platform`）

示例：

```bash
export MONGODB_URI='mongodb://root:K6F659ndB2y8fj89@test-db-mongodb.ns-qrpnjool.svc:27017'
export MONGODB_DB='interview_platform'
bash entrypoint.sh
```

### 1.4 当前持久化集合（后端实现）

- `users`：用户信息
- `tokens`：登录 token（含过期时间）
- `jobs`：岗位列表
- `dashboard_home`：首页聚合数据（按 `userId`）
- `resume_diagnosis`：简历诊断历史
- `counters`：自增序列（用户 ID）

---

## 2. 认证模块（登录/注册）

### 2.1 用户注册

- Method：`POST`
- Path：`/auth/register`
- Auth：否

#### Request Body

```json
{
  "username": "lin",
  "password": "123456"
}
```

#### Response `data`

```json
{
  "userId": "u_10002",
  "username": "lin"
}
```

#### 前端注意

- 表单字段为 `username` + `password`
- 建议前端做最小长度校验，减少 4001

---

### 2.2 用户登录

- Method：`POST`
- Path：`/auth/login`
- Auth：否

#### Request Body

```json
{
  "username": "lin",
  "password": "123456"
}
```

#### Response `data`

```json
{
  "token": "jwt-token",
  "refreshToken": "refresh-token",
  "expiresIn": 7200,
  "user": {
    "userId": "u_10001",
    "username": "lin",
    "nickname": "林同学",
    "avatar": "https://xxx/avatar.png"
  }
}
```

#### 前端注意

- 保存 `token`：`uni.setStorageSync('token', token)`
- 后续请求统一加 Header：`Authorization: Bearer ${token}`

---

## 3. 首页模块（Dashboard）

> 首页建议只请求一次聚合接口，降低前端组装成本。

### 3.1 获取主页面聚合数据

- Method：`GET`
- Path：`/dashboard/home`
- Auth：是

#### Response `data`

```json
{
  "profile": {
    "nickname": "林同学",
    "avatar": "https://xxx/avatar.png",
    "interviewLevel": "面试达人",
    "todayPracticeMinutes": 102
  },
  "nextPractice": {
    "targetTime": "2026-03-20T18:30:00+08:00",
    "remainingMinutes": 388
  },
  "resume": {
    "completion": 82,
    "lastDiagnosis": {
      "matchPercent": 86,
      "summary": "项目亮点较好，建议补充性能优化细节"
    }
  },
  "recentScores": [
    { "id": "s_001", "job": "前端开发", "score": 89, "date": "2026-03-18" },
    { "id": "s_002", "job": "Java 开发", "score": 84, "date": "2026-03-16" },
    { "id": "s_003", "job": "网络工程师", "score": 87, "date": "2026-03-12" }
  ],
  "radar": {
    "labels": ["技术", "表达", "逻辑", "心理", "稳健"],
    "values": [88, 82, 90, 80, 86]
  },
  "hotJobs": [
    { "name": "Java 开发工程师", "heat": 98 },
    { "name": "前端开发工程师", "heat": 95 },
    { "name": "网络工程师", "heat": 91 }
  ],
  "todayReadings": [
    { "id": "r_001", "title": "高并发场景下的缓存一致性", "weakness": "逻辑表达", "minutes": 15 },
    { "id": "r_002", "title": "Vue 组件性能优化 Checklist", "weakness": "技术深度", "minutes": 12 }
  ]
}
```

---

### 3.2 AI 简历诊断（按钮触发）

- Method：`POST`
- Path：`/resume/diagnosis`
- Auth：是

#### Request Body

```json
{
  "targetJob": "前端开发工程师"
}
```

#### Response `data`

```json
{
  "matchPercent": 86,
  "keywords": ["项目经验", "性能优化", "沟通表达"],
  "suggestions": [
    "补充量化结果（如首屏耗时降低xx%）",
    "增加复杂问题排查案例"
  ]
}
```

> 说明：该接口会将诊断记录写入 `resume_diagnosis`，并同步更新首页 `resume.lastDiagnosis`。

---

### 3.3 岗位选择列表

- Method：`GET`
- Path：`/interview/jobs`
- Auth：是

#### Response `data`

```json
[
  { "id": "j_001", "name": "前端开发工程师" },
  { "id": "j_002", "name": "Java 开发工程师" },
  { "id": "j_003", "name": "网络工程师" }
]
```

---

## 4. 前端对接流程（建议）

1. 登录页：调用 `/auth/login`，保存 `token`
2. 注册页：调用 `/auth/register`
3. 首页：`onLoad`/`onShow` 调用 `/dashboard/home`
4. 简历诊断按钮：调用 `/resume/diagnosis`
5. 岗位页：页面加载时调用 `/interview/jobs`

---

## 5. 联调示例（可直接复制）

### 5.1 登录

```bash
curl -X POST 'http://127.0.0.1:3000/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"username":"lin","password":"123456"}'
```

### 5.2 带 token 拉取首页

```bash
curl 'http://127.0.0.1:3000/api/v1/dashboard/home' \
  -H 'Authorization: Bearer <token>'
```

---

## 6. 最小可用接口清单（MVP）

- `POST /auth/register`
- `POST /auth/login`
- `GET /dashboard/home`
- `POST /resume/diagnosis`
- `GET /interview/jobs`

以上 5 个接口已可支撑当前前端原型页面完整联调。
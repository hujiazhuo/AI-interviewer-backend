# AI 全真模拟面试平台 - 前后端对接文档（当前功能整合版）

> 版本：V1.3  
> 用途：可直接同步给前端联调。  
> 说明：当前仓库存在两套后端实现，已在本文档明确区分。

---

## 1. 当前对接基线（请前端先按这个）

- 默认联调服务（主线）：`hello.py` 多文件版（`app.py + routes + services`）
- 统一端口：`3000`
- Base URL：`http://127.0.0.1:3000/api/v1`
- 鉴权：`Authorization: Bearer <token>`（通过 `/auth/login` 获取）

> 你们前端现在优先对接主线接口（第 4 章 A）。

---

## 2. 统一响应结构（主线接口）

### 成功

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 失败

```json
{
  "code": 4001,
  "message": "参数校验失败",
  "data": null
}
```

### 错误码

| code | message | 说明 |
|---|---|---|
| 0 | ok | 成功 |
| 4001 | 参数校验失败 | 参数缺失或为空 |
| 4002 | 用户名或密码错误 | 登录失败 |
| 4003 | 用户名已存在 | 注册重复 |
| 4010 | 未登录或 token 失效 | 未携带 token 或 token 失效 |
| 5000 | 服务端异常 | 未知错误 |

---

## 3. 健康检查与启动

### 启动（主线）

```bash
cd /home/devbox/project
APP_PORT=3000 bash entrypoint.sh
```

### 健康检查

```bash
curl -i http://127.0.0.1:3000/health
```

---

## 4. 接口总览

### A. 主线接口（前端当前使用）

1. `POST /auth/register`
2. `POST /auth/login`
3. `GET /dashboard/home`
4. `POST /resume/diagnosis`
5. `GET /interview/jobs`
6. `GET /health` / `GET /`

### B. 新增 FastAPI 功能（已实现第一部分）

1. `GET /user/dashboard`（完整路径：`/api/v1/user/dashboard`）

> FastAPI 这条接口目前为“新增能力验证版”，默认由 `uvicorn fastapi_app.main:app` 运行，认证 token 规则与主线不同（见第 6 章）。

---

## 5. 主线接口详细定义（A）

## 5.1 注册

- Method：`POST`
- URL：`/api/v1/auth/register`
- Headers：`Content-Type: application/json`

Request:

```json
{ "username": "lin", "password": "123456" }
```

Success:

```json
{
  "code": 0,
  "message": "ok",
  "data": { "userId": "u_10002", "username": "lin" }
}
```

Fail:

```json
{ "code": 4001, "message": "参数校验失败", "data": null }
```

```json
{ "code": 4003, "message": "用户名已存在", "data": null }
```

---

## 5.2 登录

- Method：`POST`
- URL：`/api/v1/auth/login`
- Headers：`Content-Type: application/json`

Request:

```json
{ "username": "lin", "password": "123456" }
```

Success:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
}
```

Fail:

```json
{ "code": 4002, "message": "用户名或密码错误", "data": null }
```

---

## 5.3 首页聚合

- Method：`GET`
- URL：`/api/v1/dashboard/home`
- Headers：`Authorization: Bearer <token>`

Success（示例字段）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "profile": {
      "nickname": "林同学",
      "avatar": "https://xxx/avatar.png",
      "interviewLevel": "面试达人",
      "todayPracticeMinutes": 102
    },
    "resume": { "completion": 82 },
    "recentScores": [],
    "radar": { "labels": ["技术", "表达", "逻辑", "心理", "稳健"], "values": [88, 82, 90, 80, 86] },
    "hotJobs": []
  }
}
```

Fail:

```json
{ "code": 4010, "message": "未登录或 token 失效", "data": null }
```

---

## 5.4 简历诊断

- Method：`POST`
- URL：`/api/v1/resume/diagnosis`
- Headers：
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>`

Request:

```json
{ "targetJob": "前端开发工程师" }
```

Success:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "matchPercent": 86,
    "keywords": ["项目经验", "性能优化", "沟通表达"],
    "suggestions": ["补充量化结果（如首屏耗时降低xx%）", "增加复杂问题排查案例"]
  }
}
```

---

## 5.5 岗位列表

- Method：`GET`
- URL：`/api/v1/interview/jobs`
- Headers：`Authorization: Bearer <token>`

Success:

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    { "id": "j_001", "name": "前端开发工程师" },
    { "id": "j_002", "name": "Java 开发工程师" },
    { "id": "j_003", "name": "网络工程师" }
  ]
}
```

---

## 6. 新增 FastAPI 接口（B）

## 6.1 Dashboard（FastAPI 版）

- Method：`GET`
- URL：`/api/v1/user/dashboard`
- 认证方式：`Authorization: Bearer user:<id>`（示例：`Bearer user:1`）

Success:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user": {
      "user_id": 1,
      "name": "林同学",
      "interview_level": "面试达人",
      "today_practice_minutes": 102
    },
    "resume": { "completion": 82 },
    "recent_interviews": [],
    "radar": { "labels": ["技术", "表达", "逻辑", "心理", "稳健"], "values": [88, 82, 90, 80, 86] },
    "hot_jobs": []
  }
}
```

Fail（FastAPI 默认风格）：

```json
{ "detail": "用户未登录" }
```

```json
{ "detail": "token 无效" }
```

> 注意：FastAPI 新接口当前与主线 token 体系不同，前端若切换到这条接口，需要单独处理 token 规则。

---

## 7. 前端请求建议

1. 主线联调请固定用：`http://127.0.0.1:3000/api/v1`
2. 登录后保存 `token`，所有主线鉴权接口统一带 `Authorization`
3. 响应处理建议：
   - 若返回包含 `code`：按主线规则处理（`code === 0` 成功）
   - 若返回包含 `detail`：按 FastAPI 错误处理

---

## 8. 前端请求封装示例（兼容主线 + FastAPI）

```js
const BASE_URL = 'http://127.0.0.1:3000/api/v1';

async function request(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  const data = await res.json();

  // 主线风格
  if (typeof data.code !== 'undefined') {
    if (data.code === 0) return data.data;
    if (data.code === 4010) {
      localStorage.removeItem('token');
      throw new Error('未登录或 token 失效');
    }
    throw new Error(data.message || '请求失败');
  }

  // FastAPI 风格
  if (!res.ok) throw new Error(data.detail || '请求失败');
  return data;
}
```

---

## 9. 运行与配置补充

- MongoDB：
  - `MONGODB_URI`
  - `MONGODB_DB`（默认 `interview_platform`）
- 端口：
  - `APP_PORT`（启动脚本）
  - `PORT`（服务端监听）
  - 默认均为 `3000`

> 手机/模拟器调试请把 `127.0.0.1` 替换成开发机局域网 IP。

---

## 10. 联调顺序（建议）

### 主线

1. `POST /auth/login`
2. `GET /dashboard/home`
3. `GET /interview/jobs`
4. `POST /resume/diagnosis`

### 新增 FastAPI（可选）

1. 准备 token：`Bearer user:1`
2. `GET /user/dashboard`

以上为当前“已实现功能 + 新增功能”的整合版对接文档。

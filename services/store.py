from datetime import datetime, timedelta, timezone

from config import MONGODB_DB, MONGODB_URI
from utils.time_utils import now_iso

try:
    from pymongo import MongoClient, ReturnDocument
except Exception:
    MongoClient = None
    ReturnDocument = None


class MongoStore:
    def __init__(self, uri, db_name):
        self.enabled = False
        self.client = None
        self.db = None
        self.users = None
        self.tokens = None
        self.counters = None
        self.jobs = None
        self.dashboard_home = None
        self.resume_diagnosis = None
        self.resumes = None
        self.interview_sessions = None
        self.interview_reports = None

        if MongoClient is None:
            print("pymongo 未安装，使用内存数据")
            return

        try:
            self.client = MongoClient(
                uri,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
                socketTimeoutMS=3000,
            )
            self.client.admin.command("ping")
            self.db = self.client[db_name]
            self.users = self.db["users"]
            self.tokens = self.db["tokens"]
            self.counters = self.db["counters"]
            self.jobs = self.db["jobs"]
            self.dashboard_home = self.db["dashboard_home"]
            self.resume_diagnosis = self.db["resume_diagnosis"]
            self.resumes = self.db["resumes"]
            self.interview_sessions = self.db["interview_sessions"]
            self.interview_reports = self.db["interview_reports"]

            self.users.create_index("username", unique=True)
            self.tokens.create_index("token", unique=True)
            self.tokens.create_index("expiresAt")
            self.jobs.create_index("id", unique=True)
            self.dashboard_home.create_index("userId", unique=True)
            self.resume_diagnosis.create_index([("userId", 1), ("createdAt", -1)])
            self.resumes.create_index("userId", unique=True)
            self.interview_sessions.create_index("sessionId", unique=True)
            self.interview_sessions.create_index([("userId", 1), ("updatedAt", -1)])
            self.interview_reports.create_index("id", unique=True)
            self.interview_reports.create_index("sessionId")
            self.interview_reports.create_index([("userId", 1), ("createdAt", -1)])

            self._ensure_seed_user()
            self._ensure_seed_jobs()
            self._ensure_seed_dashboard_home("u_10001")
            self.enabled = True
            print(f"MongoDB 已连接: {uri} / db={db_name}")
        except Exception as e:
            print(f"MongoDB 连接失败，回退内存数据: {e}")

    def _default_dashboard_home(self, user):
        nickname = user.get("nickname") or user["username"]
        avatar = user.get("avatar") or ""
        return {
            "profile": {
                "nickname": nickname,
                "avatar": avatar,
                "interviewLevel": "面试达人",
                "todayPracticeMinutes": 102,
            },
            "nextPractice": {
                "targetTime": now_iso(),
                "remainingMinutes": 388,
            },
            "resume": {
                "completion": 82,
                "completeness_score": 82,
                "lastDiagnosis": {
                    "matchPercent": 86,
                    "summary": "项目亮点较好，建议补充性能优化细节",
                },
            },
            "recentScores": [
                {"id": "s_001", "job": "前端开发", "score": 89, "date": "2026-03-18"},
                {"id": "s_002", "job": "Java 开发", "score": 84, "date": "2026-03-16"},
                {"id": "s_003", "job": "网络工程师", "score": 87, "date": "2026-03-12"},
            ],
            "radar": {
                "labels": ["技术", "表达", "逻辑", "心理", "稳健"],
                "values": [88, 82, 90, 80, 86],
            },
            "hotJobs": [
                {"name": "Java后端开发工程师", "heat": 98},
                {"name": "网络工程师", "heat": 91},
                {"name": "大模型应用开发工程师", "heat": 93},
            ],
            "todayReadings": [
                {
                    "id": "r_001",
                    "title": "高并发场景下的缓存一致性",
                    "weakness": "逻辑表达",
                    "minutes": 15,
                },
                {
                    "id": "r_002",
                    "title": "Vue 组件性能优化 Checklist",
                    "weakness": "技术深度",
                    "minutes": 12,
                },
            ],
        }

    def _ensure_seed_user(self):
        if not self.users.find_one({"username": "lin"}):
            self.users.insert_one(
                {
                    "userId": "u_10001",
                    "username": "lin",
                    "password": "123456",
                    "nickname": "林同学",
                    "avatar": "https://xxx/avatar.png",
                }
            )

    def _ensure_seed_jobs(self):
        seeds = [
            {"id": "j_002", "name": "Java后端开发工程师"},
            {"id": "j_003", "name": "网络工程师"},
            {"id": "j_004", "name": "大模型应用开发工程师"},
        ]
        for item in seeds:
            self.jobs.update_one({"id": item["id"]}, {"$set": item}, upsert=True)

    def _ensure_seed_dashboard_home(self, user_id):
        user = self.users.find_one({"userId": user_id}, {"_id": 0})
        if not user:
            return
        if not self.dashboard_home.find_one({"userId": user_id}):
            self.dashboard_home.insert_one(
                {
                    "userId": user_id,
                    "data": self._default_dashboard_home(user),
                    "updatedAt": datetime.now(timezone.utc),
                }
            )

    def _next_user_id(self):
        self.counters.update_one(
            {"_id": "user_seq"},
            {"$setOnInsert": {"value": 10001}},
            upsert=True,
        )
        doc = self.counters.find_one_and_update(
            {"_id": "user_seq"},
            {"$inc": {"value": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return f"u_{doc['value']}"

    def find_user_by_username(self, username):
        return self.users.find_one({"username": username}, {"_id": 0})

    def create_user(self, username, password):
        user_id = self._next_user_id()
        doc = {
            "userId": user_id,
            "username": username,
            "password": password,
            "nickname": username,
            "avatar": "https://xxx/avatar.png",
        }
        self.users.insert_one(doc)
        self._ensure_seed_dashboard_home(user_id)
        return doc

    def save_token(self, token, user_id, expires_in):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        self.tokens.insert_one(
            {
                "token": token,
                "userId": user_id,
                "expiresAt": expires_at,
            }
        )

    def find_user_by_token(self, token):
        item = self.tokens.find_one({"token": token})
        if not item:
            return None
        expires_at = item.get("expiresAt")
        if expires_at:
            if expires_at.tzinfo is None:
                if expires_at < datetime.utcnow():
                    return None
            else:
                if expires_at < datetime.now(timezone.utc):
                    return None
        return self.users.find_one({"userId": item["userId"]}, {"_id": 0})

    def get_jobs(self):
        return list(self.jobs.find({}, {"_id": 0}).sort("id", 1))

    def get_dashboard_home(self, user):
        user_id = user["userId"]
        doc = self.dashboard_home.find_one({"userId": user_id}, {"_id": 0, "data": 1})
        if not doc:
            self._ensure_seed_dashboard_home(user_id)
            doc = self.dashboard_home.find_one({"userId": user_id}, {"_id": 0, "data": 1})
        payload = doc["data"] if doc else self._default_dashboard_home(user)
        resume = self.get_resume(user_id)
        if payload.get("resume") is None:
            payload["resume"] = {}
        if resume:
            score = int(resume.get("completeness_score") or 0)
            payload["resume"]["completion"] = score
            payload["resume"]["completeness_score"] = score
        else:
            payload["resume"].setdefault("completion", 0)
            payload["resume"].setdefault("completeness_score", payload["resume"]["completion"])
        return payload

    def save_resume_diagnosis(self, user_id, target_job, result):
        self.resume_diagnosis.insert_one(
            {
                "userId": user_id,
                "targetJob": target_job,
                "result": result,
                "createdAt": datetime.now(timezone.utc),
            }
        )
        self.dashboard_home.update_one(
            {"userId": user_id},
            {
                "$set": {
                    "data.resume.lastDiagnosis": {
                        "matchPercent": result["matchPercent"],
                        "summary": "；".join(result["suggestions"][:1]) or "建议继续补充项目细节",
                    },
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    def _next_resume_id(self):
        self.counters.update_one(
            {"_id": "resume_seq"},
            {"$setOnInsert": {"value": 10000}},
            upsert=True,
        )
        doc = self.counters.find_one_and_update(
            {"_id": "resume_seq"},
            {"$inc": {"value": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return f"r_{doc['value']}"

    def save_resume(self, user_id, payload, is_draft=False):
        now = now_iso()
        old = self.resumes.find_one({"userId": user_id}, {"_id": 0, "resumeId": 1, "createdAt": 1})
        resume_id = old.get("resumeId") if old else self._next_resume_id()
        created_at = old.get("createdAt") if old else now

        doc = {
            "resumeId": resume_id,
            "userId": user_id,
            "name": payload.get("name", ""),
            "targetJobIndustry": payload.get("targetJobIndustry", ""),
            "workYears": payload.get("workYears", ""),
            "interviewTypes": payload.get("interviewTypes", []),
            "techStack": payload.get("techStack", ""),
            "mastery": payload.get("mastery", ""),
            "directions": payload.get("directions", []),
            "projects": payload.get("projects", []),
            "completeness_score": int(payload.get("completeness_score", 0)),
            "isDraft": bool(is_draft),
            "createdAt": created_at,
            "updatedAt": now,
        }
        self.resumes.update_one({"userId": user_id}, {"$set": doc}, upsert=True)
        self.dashboard_home.update_one(
            {"userId": user_id},
            {
                "$set": {
                    "data.resume.completion": doc["completeness_score"],
                    "data.resume.completeness_score": doc["completeness_score"],
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        return {
            "resumeId": resume_id,
            "userId": user_id,
            "completeness_score": doc["completeness_score"],
            "updatedAt": now,
        }

    def get_resume(self, user_id):
        return self.resumes.find_one({"userId": user_id}, {"_id": 0})

    def create_interview_session(self, session):
        doc = dict(session)
        self.interview_sessions.insert_one(doc)
        return doc

    def get_interview_session(self, session_id, user_id):
        return self.interview_sessions.find_one(
            {"sessionId": session_id, "userId": user_id}, {"_id": 0}
        )

    def update_interview_session(self, session_id, user_id, updates):
        updates = dict(updates)
        updates["updatedAt"] = now_iso()
        self.interview_sessions.update_one(
            {"sessionId": session_id, "userId": user_id},
            {"$set": updates},
        )
        return self.get_interview_session(session_id, user_id)

    def create_interview_report(self, report):
        doc = dict(report)
        self.interview_reports.update_one(
            {"id": doc["id"], "userId": doc["userId"]},
            {"$set": doc},
            upsert=True,
        )
        return self.get_interview_report(doc["id"], doc["userId"])

    def get_interview_report(self, report_id, user_id):
        return self.interview_reports.find_one({"id": report_id, "userId": user_id}, {"_id": 0})

    def get_interview_report_by_session(self, session_id, user_id):
        return self.interview_reports.find_one(
            {"sessionId": session_id, "userId": user_id}, {"_id": 0}
        )

    def update_interview_report(self, report_id, user_id, updates):
        updates = dict(updates)
        updates["updatedAt"] = now_iso()
        self.interview_reports.update_one(
            {"id": report_id, "userId": user_id},
            {"$set": updates},
            upsert=False,
        )
        return self.get_interview_report(report_id, user_id)

    def list_interview_reports(self, user_id, limit=20, page=1, page_size=None):
        if page_size is None:
            page_size = limit
        page = max(1, int(page or 1))
        page_size = max(1, min(100, int(page_size or 20)))
        skip = (page - 1) * page_size

        cursor = (
            self.interview_reports.find({"userId": user_id}, {"_id": 0})
            .sort("createdAt", -1)
            .skip(skip)
            .limit(page_size)
        )
        records = list(cursor)
        total = self.interview_reports.count_documents({"userId": user_id})
        return records, total

    def delete_interview_report(self, report_id, user_id):
        result = self.interview_reports.delete_one({"id": report_id, "userId": user_id})
        return result.deleted_count > 0


class MemoryStore:
    def __init__(self):
        self.users_by_username = {
            "lin": {
                "userId": "u_10001",
                "username": "lin",
                "password": "123456",
                "nickname": "林同学",
                "avatar": "https://xxx/avatar.png",
            }
        }
        self.tokens = {}
        self.user_seq = 10001
        self.resume_seq = 10000
        self.resumes = {}
        self.interview_sessions = {}
        self.interview_reports = {}

    def _default_dashboard_home(self, user):
        return {
            "profile": {
                "nickname": user.get("nickname") or user["username"],
                "avatar": user.get("avatar") or "",
                "interviewLevel": "面试达人",
                "todayPracticeMinutes": 102,
            },
            "nextPractice": {
                "targetTime": now_iso(),
                "remainingMinutes": 388,
            },
            "resume": {
                "completion": 82,
                "completeness_score": 82,
                "lastDiagnosis": {
                    "matchPercent": 86,
                    "summary": "项目亮点较好，建议补充性能优化细节",
                },
            },
            "recentScores": [
                {"id": "s_001", "job": "前端开发", "score": 89, "date": "2026-03-18"},
                {"id": "s_002", "job": "Java 开发", "score": 84, "date": "2026-03-16"},
                {"id": "s_003", "job": "网络工程师", "score": 87, "date": "2026-03-12"},
            ],
            "radar": {
                "labels": ["技术", "表达", "逻辑", "心理", "稳健"],
                "values": [88, 82, 90, 80, 86],
            },
            "hotJobs": [
                {"name": "Java后端开发工程师", "heat": 98},
                {"name": "网络工程师", "heat": 91},
                {"name": "大模型应用开发工程师", "heat": 93},
            ],
            "todayReadings": [
                {
                    "id": "r_001",
                    "title": "高并发场景下的缓存一致性",
                    "weakness": "逻辑表达",
                    "minutes": 15,
                },
                {
                    "id": "r_002",
                    "title": "Vue 组件性能优化 Checklist",
                    "weakness": "技术深度",
                    "minutes": 12,
                },
            ],
        }

    def find_user_by_username(self, username):
        return self.users_by_username.get(username)

    def create_user(self, username, password):
        self.user_seq += 1
        user_id = f"u_{self.user_seq}"
        user = {
            "userId": user_id,
            "username": username,
            "password": password,
            "nickname": username,
            "avatar": "https://xxx/avatar.png",
        }
        self.users_by_username[username] = user
        return user

    def save_token(self, token, user_id, expires_in):
        self.tokens[token] = {
            "userId": user_id,
            "expiresAt": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        }

    def find_user_by_token(self, token):
        item = self.tokens.get(token)
        if not item:
            return None
        if item["expiresAt"] < datetime.now(timezone.utc):
            return None
        for user in self.users_by_username.values():
            if user["userId"] == item["userId"]:
                return user
        return None

    def get_jobs(self):
        return [
            {"id": "j_002", "name": "Java后端开发工程师"},
            {"id": "j_003", "name": "网络工程师"},
            {"id": "j_004", "name": "大模型应用开发工程师"},
        ]

    def get_dashboard_home(self, user):
        payload = self._default_dashboard_home(user)
        resume = self.get_resume(user["userId"])
        if resume:
            score = int(resume.get("completeness_score") or 0)
            payload["resume"]["completion"] = score
            payload["resume"]["completeness_score"] = score
        return payload

    def save_resume_diagnosis(self, user_id, target_job, result):
        return None

    def save_resume(self, user_id, payload, is_draft=False):
        old = self.resumes.get(user_id)
        if old:
            resume_id = old["resumeId"]
            created_at = old["createdAt"]
        else:
            self.resume_seq += 1
            resume_id = f"r_{self.resume_seq}"
            created_at = now_iso()

        doc = {
            "resumeId": resume_id,
            "userId": user_id,
            "name": payload.get("name", ""),
            "targetJobIndustry": payload.get("targetJobIndustry", ""),
            "workYears": payload.get("workYears", ""),
            "interviewTypes": payload.get("interviewTypes", []),
            "techStack": payload.get("techStack", ""),
            "mastery": payload.get("mastery", ""),
            "directions": payload.get("directions", []),
            "projects": payload.get("projects", []),
            "completeness_score": int(payload.get("completeness_score", 0)),
            "isDraft": bool(is_draft),
            "createdAt": created_at,
            "updatedAt": now_iso(),
        }
        self.resumes[user_id] = doc
        return {
            "resumeId": resume_id,
            "userId": user_id,
            "completeness_score": doc["completeness_score"],
            "updatedAt": doc["updatedAt"],
        }

    def get_resume(self, user_id):
        return self.resumes.get(user_id)

    def create_interview_session(self, session):
        self.interview_sessions[session["sessionId"]] = dict(session)
        return self.interview_sessions[session["sessionId"]]

    def get_interview_session(self, session_id, user_id):
        session = self.interview_sessions.get(session_id)
        if not session:
            return None
        if session.get("userId") != user_id:
            return None
        return session

    def update_interview_session(self, session_id, user_id, updates):
        session = self.get_interview_session(session_id, user_id)
        if not session:
            return None
        session.update(dict(updates))
        session["updatedAt"] = now_iso()
        return session

    def create_interview_report(self, report):
        key = f"{report['userId']}::{report['id']}"
        self.interview_reports[key] = dict(report)
        return self.interview_reports[key]

    def get_interview_report(self, report_id, user_id):
        return self.interview_reports.get(f"{user_id}::{report_id}")

    def get_interview_report_by_session(self, session_id, user_id):
        for item in self.interview_reports.values():
            if item.get("userId") == user_id and item.get("sessionId") == session_id:
                return item
        return None

    def update_interview_report(self, report_id, user_id, updates):
        doc = self.get_interview_report(report_id, user_id)
        if not doc:
            return None
        doc.update(dict(updates))
        doc["updatedAt"] = now_iso()
        return doc

    def list_interview_reports(self, user_id, limit=20, page=1, page_size=None):
        if page_size is None:
            page_size = limit
        page = max(1, int(page or 1))
        page_size = max(1, min(100, int(page_size or 20)))

        rows = [x for x in self.interview_reports.values() if x.get("userId") == user_id]
        rows.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        return rows[start:end], total

    def delete_interview_report(self, report_id, user_id):
        key = f"{user_id}::{report_id}"
        if key not in self.interview_reports:
            return False
        del self.interview_reports[key]
        return True


mongo = MongoStore(MONGODB_URI, MONGODB_DB)
memory = MemoryStore()


def store_enabled():
    return mongo.enabled


def find_user_by_username(username):
    return mongo.find_user_by_username(username) if store_enabled() else memory.find_user_by_username(username)


def create_user(username, password):
    return mongo.create_user(username, password) if store_enabled() else memory.create_user(username, password)


def save_token(token, user_id, expires_in):
    if store_enabled():
        mongo.save_token(token, user_id, expires_in)
    else:
        memory.save_token(token, user_id, expires_in)


def find_user_by_token(token):
    return mongo.find_user_by_token(token) if store_enabled() else memory.find_user_by_token(token)


def get_jobs():
    return mongo.get_jobs() if store_enabled() else memory.get_jobs()


def get_dashboard_home(user):
    return mongo.get_dashboard_home(user) if store_enabled() else memory.get_dashboard_home(user)


def save_resume_diagnosis(user_id, target_job, result):
    if store_enabled():
        mongo.save_resume_diagnosis(user_id, target_job, result)


def save_resume(user_id, payload, is_draft=False):
    if store_enabled():
        return mongo.save_resume(user_id, payload, is_draft=is_draft)
    return memory.save_resume(user_id, payload, is_draft=is_draft)


def get_resume(user_id):
    return mongo.get_resume(user_id) if store_enabled() else memory.get_resume(user_id)


def create_interview_session(session):
    if store_enabled():
        return mongo.create_interview_session(session)
    return memory.create_interview_session(session)


def get_interview_session(session_id, user_id):
    if store_enabled():
        return mongo.get_interview_session(session_id, user_id)
    return memory.get_interview_session(session_id, user_id)


def update_interview_session(session_id, user_id, updates):
    if store_enabled():
        return mongo.update_interview_session(session_id, user_id, updates)
    return memory.update_interview_session(session_id, user_id, updates)


def create_interview_report(report):
    if store_enabled():
        return mongo.create_interview_report(report)
    return memory.create_interview_report(report)


def get_interview_report(report_id, user_id):
    if store_enabled():
        return mongo.get_interview_report(report_id, user_id)
    return memory.get_interview_report(report_id, user_id)


def get_interview_report_by_session(session_id, user_id):
    if store_enabled():
        return mongo.get_interview_report_by_session(session_id, user_id)
    return memory.get_interview_report_by_session(session_id, user_id)


def update_interview_report(report_id, user_id, updates):
    if store_enabled():
        return mongo.update_interview_report(report_id, user_id, updates)
    return memory.update_interview_report(report_id, user_id, updates)


def list_interview_reports(user_id, limit=20, page=1, page_size=None):
    if store_enabled():
        return mongo.list_interview_reports(user_id, limit=limit, page=page, page_size=page_size)
    return memory.list_interview_reports(user_id, limit=limit, page=page, page_size=page_size)


def delete_interview_report(report_id, user_id):
    if store_enabled():
        return mongo.delete_interview_report(report_id, user_id)
    return memory.delete_interview_report(report_id, user_id)

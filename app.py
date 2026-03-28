import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from config import BASE_PATH, SERVER_HOST, SERVER_PORT
from routes import auth, dashboard, interview, rag, resume, system
from services import store
from utils.response import err


def parse_json_body(handler):
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        return None
    raw = handler.rfile.read(content_length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


class ApiHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _require_auth(self):
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        return store.find_user_by_token(token)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = parse_json_body(self) or {}

        if path == f"{BASE_PATH}/auth/register":
            status, payload = auth.register(body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/auth/login":
            status, payload = auth.login(body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/resume/diagnosis":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = resume.diagnosis(user, body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/resume/save":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = resume.save(user, body, is_draft=False)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/resume/draft/save":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = resume.save(user, body, is_draft=True)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/interview/start":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.start(user, body)
            self._send_json(payload, status)
            return

        if path in [f"{BASE_PATH}/interview/answer", f"{BASE_PATH}/interview/chat"]:
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.answer(user, body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/interview/decision":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.decision(user, body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/interview/end":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.end(user, body)
            self._send_json(payload, status)
            return

        if path in [f"{BASE_PATH}/interview/analyze", f"{BASE_PATH}/analyze", "/analyze"]:
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.analyze(user, body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/rag/knowledge/rebuild":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = rag.knowledge_rebuild(body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/rag/knowledge/ingest":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = rag.knowledge_ingest(body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/rag/resume/keywords":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = rag.resume_keywords(user, body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/rag/query/rewrite":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = rag.query_rewrite(user, body)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/rag/knowledge/retrieve":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = rag.knowledge_retrieve(user, body)
            self._send_json(payload, status)
            return

        if path in [f"{BASE_PATH}/interview/records/delete", f"{BASE_PATH}/records/delete", "/records/delete"]:
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.delete_record(user, body=body)
            self._send_json(payload, status)
            return

        self._send_json(err(5000, "服务端异常"), status=404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parsed.query

        if path == f"{BASE_PATH}/dashboard/home":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = dashboard.home(user)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/interview/jobs":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.jobs()
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/interview/session":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.session(user, query)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/rag/config":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = rag.config_view()
            self._send_json(payload, status)
            return

        if path in [f"{BASE_PATH}/interview/records", f"{BASE_PATH}/records", "/records"]:
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.records(user, query)
            self._send_json(payload, status)
            return

        if path in [f"{BASE_PATH}/interview/report", f"{BASE_PATH}/report", "/report"]:
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.report(user, query=query)
            self._send_json(payload, status)
            return

        report_prefix = f"{BASE_PATH}/interview/report/"
        if path.startswith(report_prefix):
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            report_id = path[len(report_prefix) :]
            status, payload = interview.report(user, report_id=report_id)
            self._send_json(payload, status)
            return

        if path == f"{BASE_PATH}/resume/my":
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = resume.my_resume(user)
            self._send_json(payload, status)
            return

        if path in ["/", "/health"]:
            status, payload = system.health()
            self._send_json(payload, status)
            return

        self._send_json(err(5000, "服务端异常"), status=404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parsed.query

        if path in [f"{BASE_PATH}/interview/records", f"{BASE_PATH}/records", "/records"]:
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            status, payload = interview.delete_record(user, query=query)
            self._send_json(payload, status)
            return

        records_prefix = f"{BASE_PATH}/interview/records/"
        if path.startswith(records_prefix):
            user = self._require_auth()
            if not user:
                self._send_json(err(4010, "未登录或 token 失效"), status=401)
                return
            record_id = path[len(records_prefix) :]
            status, payload = interview.delete_record(user, report_id=record_id)
            self._send_json(payload, status)
            return

        self._send_json(err(5000, "服务端异常"), status=404)


def run(server_class=ThreadingHTTPServer, handler_class=ApiHandler):
    server_address = (SERVER_HOST, SERVER_PORT)
    httpd = server_class(server_address, handler_class)
    print(f"Server started at http://{SERVER_HOST}:{SERVER_PORT}")
    httpd.serve_forever()

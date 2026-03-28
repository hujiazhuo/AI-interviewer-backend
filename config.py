import os


def _load_env_file(path: str):
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except Exception:
        # 配置文件读取失败时忽略，保持进程可启动
        pass


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ["1", "true", "yes", "on", "y"]


def _to_int(value: str | None, default: int, min_value: int | None = None) -> int:
    try:
        iv = int((value or "").strip())
    except Exception:
        iv = default
    if min_value is not None:
        iv = max(min_value, iv)
    return iv


def _to_float(value: str | None, default: float, min_value: float | None = None) -> float:
    try:
        fv = float((value or "").strip())
    except Exception:
        fv = default
    if min_value is not None:
        fv = max(min_value, fv)
    return fv


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_load_env_file(os.path.join(ROOT_DIR, ".env.local"))
_load_env_file(os.path.join(ROOT_DIR, ".env"))

BASE_PATH = "/api/v1"
TOKEN_EXPIRE_SECONDS = 7200

SERVER_HOST = os.getenv("HOST", "0.0.0.0")
try:
    SERVER_PORT = int(os.getenv("PORT", "3000"))
except ValueError:
    SERVER_PORT = 3000

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://root:K6F659ndB2y8fj89@test-db-mongodb.ns-qrpnjool.svc:27017",
)
MONGODB_DB = os.getenv("MONGODB_DB", "interview_platform")

# ===== RAG / Tavily Config (Step-1 基线) =====
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "./knowledge")
RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "interview_kb")
RAG_PERSIST_DIR = os.getenv("RAG_PERSIST_DIR", "./data/chroma")

SIMILARITY_THRESHOLD = _to_float(os.getenv("SIMILARITY_THRESHOLD", "0.80"), 0.80, min_value=0.0)
RAG_TOP_K_RETRIEVE = _to_int(os.getenv("RAG_TOP_K_RETRIEVE", "10"), 10, min_value=1)
RAG_TOP_K_RERANK = _to_int(os.getenv("RAG_TOP_K_RERANK", "3"), 3, min_value=1)

ENABLE_TAVILY_FALLBACK = _to_bool(os.getenv("ENABLE_TAVILY_FALLBACK", "true"), True)
WRITEBACK_ON_WEB_MODE = _to_bool(os.getenv("WRITEBACK_ON_WEB_MODE", "true"), True)
WRITEBACK_MIN_WEB_SCORE = _to_float(os.getenv("WRITEBACK_MIN_WEB_SCORE", "0.65"), 0.65, min_value=0.0)
WRITEBACK_MIN_ANSWER_LEN = _to_int(os.getenv("WRITEBACK_MIN_ANSWER_LEN", "20"), 20, min_value=1)
EVOLUTION_KB_FILE = os.getenv("EVOLUTION_KB_FILE", "evolution_kb.md").strip() or "evolution_kb.md"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com/search")

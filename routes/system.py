from utils.response import ok
from utils.time_utils import today_str


def health():
    return 200, ok({"status": "running", "date": today_str()})

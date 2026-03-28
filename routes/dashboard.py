from services import store
from utils.response import ok


def home(user):
    payload = store.get_dashboard_home(user)
    if payload.get("profile"):
        payload["profile"]["nickname"] = user.get("nickname") or user["username"]
        payload["profile"]["avatar"] = user.get("avatar") or ""
    return 200, ok(payload)

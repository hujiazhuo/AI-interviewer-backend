import secrets

from config import TOKEN_EXPIRE_SECONDS
from services import store
from utils.response import err, ok


def register(body):
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()

    if not username or not password:
        return 400, err(4001, "参数校验失败")

    try:
        if store.find_user_by_username(username):
            return 400, err(4003, "用户名已存在")
        created = store.create_user(username, password)
        return 200, ok({"userId": created["userId"], "username": username})
    except Exception as e:
        print(f"register error: {e}")
        return 500, err(5000, "服务端异常")


def login(body):
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()

    if not username or not password:
        return 400, err(4001, "参数校验失败")

    user = store.find_user_by_username(username)
    if not user or user.get("password") != password:
        return 400, err(4002, "用户名或密码错误")

    token = secrets.token_urlsafe(24)
    refresh_token = secrets.token_urlsafe(24)
    store.save_token(token, user["userId"], TOKEN_EXPIRE_SECONDS)

    return 200, ok(
        {
            "token": token,
            "refreshToken": refresh_token,
            "expiresIn": TOKEN_EXPIRE_SECONDS,
            "user": {
                "userId": user["userId"],
                "username": user["username"],
                "nickname": user.get("nickname") or user["username"],
                "avatar": user.get("avatar") or "",
            },
        }
    )

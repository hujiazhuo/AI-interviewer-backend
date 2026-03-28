from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db_session
from .models import User


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="用户未登录")

    token = authorization.split(" ", 1)[1].strip()
    if not token.startswith("user:"):
        raise HTTPException(status_code=401, detail="token 无效")

    try:
        user_id = int(token.split(":", 1)[1])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="token 无效") from exc

    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

"""公共依赖：当前用户。"""
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import BizError
from core.security import decode_token
from models.models import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_database),
) -> User:
    if credentials is None:
        raise BizError(10002, status_code=401)
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise BizError(10002, status_code=401)
    user_id = payload.get("sub")
    if not user_id:
        raise BizError(10002, status_code=401)
    user = await db.get(User, int(user_id))
    if user is None or user.is_deleted or user.status != 1:
        raise BizError(10002, status_code=401)
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_database),
) -> Optional[User]:
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return await db.get(User, int(user_id))


async def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """管理员权限：仅 role_type == 'admin' 可访问后台。"""
    if user.role_type != "admin":
        raise BizError(10003, "无后台管理权限")
    return user

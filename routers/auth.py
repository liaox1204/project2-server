"""认证路由：注册 + 账号密码登录（手机号 + 密码）。"""
import re

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.security import hash_password, verify_password, create_access_token, create_refresh_token
from crud.user import get_user_by_phone, ensure_profile
from models.models import User
from schemas.news import RegisterReq, LoginReq

router = APIRouter(prefix="/auth", tags=["auth"])


def _validate_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if not re.fullmatch(r"1\d{10}", phone):
        raise BizError(20001, "请输入正确的手机号")
    return phone


def _validate_password(password: str) -> str:
    if not password or not (6 <= len(password) <= 20):
        raise BizError(10001, "密码长度需为 6-20 位")
    return password


def _build_token(user: User):
    return {
        "access_token": create_access_token(user.id, user.role_type),
        "refresh_token": create_refresh_token(user.id, user.role_type),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "phone": user.phone, "role_type": user.role_type},
    }


@router.post("/register")
async def register(req: RegisterReq, db: AsyncSession = Depends(get_database)):
    phone = _validate_phone(req.phone)
    password = _validate_password(req.password)

    if req.role_type not in ("elder", "family"):
        raise BizError(10001, "请选择身份（父母或子女）")

    existing = await get_user_by_phone(db, phone)
    if existing is not None:
        raise BizError(20003, "该手机号已注册，请直接登录")

    user = User(
        role_type=req.role_type,
        name=req.name.strip() or phone[-4:],
        phone=phone,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()
    await ensure_profile(db, user.id)
    await db.commit()
    await db.refresh(user)
    return ok(_build_token(user), "注册成功")


@router.post("/login")
async def login(req: LoginReq, db: AsyncSession = Depends(get_database)):
    phone = _validate_phone(req.phone)
    password = req.password or ""

    user = await get_user_by_phone(db, phone)
    if user is None or not verify_password(password, user.password_hash):
        raise BizError(20002, "手机号或密码错误")

    if user.status != 1 or user.is_deleted:
        raise BizError(10002, "账号不可用")

    await db.refresh(user)
    return ok(_build_token(user), "登录成功")

"""用户 CRUD。"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import User, ElderProfile


async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    res = await db.execute(select(User).where(User.phone == phone))
    return res.scalar_one_or_none()


async def get_profile(db: AsyncSession, user_id: int) -> Optional[ElderProfile]:
    res = await db.execute(select(ElderProfile).where(ElderProfile.user_id == user_id))
    return res.scalar_one_or_none()


async def ensure_profile(db: AsyncSession, user_id: int) -> ElderProfile:
    profile = await get_profile(db, user_id)
    if profile is None:
        profile = ElderProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
    return profile

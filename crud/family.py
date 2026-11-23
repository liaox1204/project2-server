"""亲情绑定 CRUD。"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import FamilyRelation
from crud.common import gen_invite_code


async def get_relation(db: AsyncSession, elder_user_id: int, family_user_id: int) -> Optional[FamilyRelation]:
    res = await db.execute(
        select(FamilyRelation).where(
            FamilyRelation.elder_user_id == elder_user_id,
            FamilyRelation.family_user_id == family_user_id,
        )
    )
    return res.scalar_one_or_none()


async def get_relation_by_code(db: AsyncSession, invite_code: str) -> Optional[FamilyRelation]:
    res = await db.execute(select(FamilyRelation).where(FamilyRelation.invite_code == invite_code))
    return res.scalar_one_or_none()


async def list_family_members(db: AsyncSession, elder_user_id: int):
    res = await db.execute(
        select(FamilyRelation).where(
            FamilyRelation.elder_user_id == elder_user_id,
            FamilyRelation.status == 1,
        )
    )
    return res.scalars().all()


async def list_elders_of_family(db: AsyncSession, family_user_id: int):
    res = await db.execute(
        select(FamilyRelation).where(
            FamilyRelation.family_user_id == family_user_id,
            FamilyRelation.status == 1,
        )
    )
    return res.scalars().all()

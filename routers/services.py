"""服务目录路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_user
from models.models import User, Service

router = APIRouter(prefix="/services", tags=["services"])


@router.get("")
async def list_services(city: str = Query(""), service_type: str = Query(""),
                        user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    q = select(Service).where(Service.status == 1)
    if city:
        q = q.where(Service.city == city)
    if service_type:
        q = q.where(Service.service_type == service_type)
    q = q.order_by(Service.id.asc())
    services = (await db.execute(q)).scalars().all()
    items = [{
        "id": s.id, "service_code": s.service_code, "service_type": s.service_type,
        "title": s.title, "description": s.description, "price": float(s.price),
        "price_unit": s.price_unit, "city": s.city, "need_family_confirm": s.need_family_confirm,
    } for s in services]
    return ok(items)


@router.get("/{service_id}")
async def get_service(service_id: int, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_database)):
    s = await db.get(Service, service_id)
    if s is None or s.status != 1:
        raise BizError(40001)
    return ok({
        "id": s.id, "service_code": s.service_code, "service_type": s.service_type,
        "title": s.title, "description": s.description, "price": float(s.price),
        "price_unit": s.price_unit, "city": s.city, "need_family_confirm": s.need_family_confirm,
    })

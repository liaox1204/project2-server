"""一键求助路由。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_user
from crud.common import gen_event_no
from models.models import User, EmergencyEvent, Notification
from schemas.news import SOSTReq

router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.post("/sos")
async def sos(req: SOSTReq, user: User = Depends(get_current_user),
              db: AsyncSession = Depends(get_database)):
    ev = EmergencyEvent(
        event_no=gen_event_no(), elder_user_id=user.id, event_type=req.event_type or "sos",
        level=req.level or 2, source=req.source, lng=req.lng, lat=req.lat,
        address=req.address, detail=req.detail, status="open",
    )
    db.add(ev)
    db.add(Notification(
        to_user_id=user.id, biz_type="emergency", title="紧急求助已发出",
        content="平台和您的家人已收到求助，请保持电话畅通。", biz_ref_id=0,
    ))
    await db.commit()
    return ok({"event_no": ev.event_no}, "求助已发出")


@router.get("/my")
async def my_events(user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_database)):
    res = await db.execute(
        select(EmergencyEvent).where(EmergencyEvent.elder_user_id == user.id)
        .order_by(EmergencyEvent.created_at.desc())
    )
    events = res.scalars().all()
    items = [{
        "event_no": e.event_no, "event_type": e.event_type, "level": e.level,
        "status": e.status, "address": e.address, "detail": e.detail or "",
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M"),
    } for e in events]
    return ok(items)

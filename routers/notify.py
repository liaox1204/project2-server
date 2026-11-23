"""通知路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok
from core.deps import get_current_user
from models.models import User, Notification

router = APIRouter(prefix="/notify", tags=["notify"])


@router.get("/list")
async def list_notifications(user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_database)):
    res = await db.execute(
        select(Notification).where(Notification.to_user_id == user.id)
        .order_by(Notification.created_at.desc()).limit(50)
    )
    items = [{
        "id": n.id, "biz_type": n.biz_type, "title": n.title, "content": n.content,
        "read_at": n.read_at.strftime("%Y-%m-%d %H:%M") if n.read_at else "",
        "created_at": n.created_at.strftime("%Y-%m-%d %H:%M"),
    } for n in res.scalars().all()]
    return ok(items)

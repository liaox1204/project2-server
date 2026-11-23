"""提醒路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_user
from models.models import User, Reminder
from schemas.news import ReminderCreateReq, ReminderUpdateReq

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("")
async def create_reminder(req: ReminderCreateReq, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_database)):
    rem = Reminder(
        elder_user_id=user.id, reminder_type=req.reminder_type, title=req.title,
        content=req.content, trigger_at=req.trigger_at, trigger_cron=req.trigger_cron,
        notify_family=req.notify_family,
    )
    db.add(rem)
    await db.commit()
    await db.refresh(rem)
    return ok({"id": rem.id}, "提醒已创建")


@router.patch("/{reminder_id}")
async def update_reminder(reminder_id: int, req: ReminderUpdateReq,
                          user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_database)):
    rem = await db.get(Reminder, reminder_id)
    if rem is None or rem.elder_user_id != user.id:
        raise BizError(60001)
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(rem, field, value)
    await db.commit()
    return ok(None, "提醒已更新")


@router.post("/{reminder_id}/done")
async def done_reminder(reminder_id: int, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    rem = await db.get(Reminder, reminder_id)
    if rem is None or rem.elder_user_id != user.id:
        raise BizError(60001)
    rem.status = 0  # 完成
    await db.commit()
    return ok(None, "已完成打卡")


@router.get("")
async def list_reminders(user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_database)):
    res = await db.execute(
        select(Reminder).where(Reminder.elder_user_id == user.id).order_by(Reminder.created_at.desc())
    )
    rems = res.scalars().all()
    items = [{
        "id": r.id, "reminder_type": r.reminder_type, "title": r.title, "content": r.content,
        "trigger_at": r.trigger_at.strftime("%Y-%m-%d %H:%M") if r.trigger_at else "",
        "status": r.status, "notify_family": r.notify_family,
    } for r in rems]
    return ok(items)

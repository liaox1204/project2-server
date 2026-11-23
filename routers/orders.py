"""订单路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from config.settings import settings
from core.response import ok, BizError
from core.deps import get_current_user
from crud.common import gen_order_no
from models.models import User, Order, Service
from schemas.news import OrderDraftReq

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/draft")
async def create_draft(req: OrderDraftReq, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_database)):
    svc = await db.get(Service, req.service_id)
    if svc is None or svc.status != 1:
        raise BizError(40001)
    order = Order(
        order_no=gen_order_no("D"), elder_user_id=user.id, service_id=svc.id,
        provider_id=svc.provider_id, status="draft", amount=svc.price,
        scheduled_time=req.scheduled_time, address_snapshot=req.address,
        contact_snapshot=f"{req.contact_name} {req.contact_phone}".strip(),
        source="manual", remark=req.remark,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    need_confirm = float(svc.price) > settings.ORDER_CONFIRM_AMOUNT_THRESHOLD or bool(svc.need_family_confirm)
    return ok({
        "order_no": order.order_no, "amount": float(order.amount),
        "status": order.status, "need_confirm": need_confirm,
    }, "草稿已创建")


@router.post("/{order_no}/confirm")
async def confirm_order(order_no: str, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    order = await _get_order(db, order_no, user)
    if order.status != "draft":
        raise BizError(40003, "当前订单状态不可确认")
    order.status = "paid"
    order.payment_status = "paid"
    await db.commit()
    return ok({"order_no": order.order_no, "status": order.status}, "订单已确认")


@router.post("/{order_no}/cancel")
async def cancel_order(order_no: str, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_database)):
    order = await _get_order(db, order_no, user)
    if order.status in ("finished", "cancelled", "refunded"):
        raise BizError(40003, "当前订单状态不可取消")
    order.status = "cancelled"
    await db.commit()
    return ok({"order_no": order.order_no, "status": order.status}, "订单已取消")


@router.get("")
async def list_orders(user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_database)):
    res = await db.execute(
        select(Order).where(Order.elder_user_id == user.id).order_by(Order.created_at.desc())
    )
    orders = res.scalars().all()
    items = []
    for o in orders:
        svc = await db.get(Service, o.service_id)
        items.append({
            "order_no": o.order_no, "status": o.status, "amount": float(o.amount),
            "service_title": svc.title if svc else "",
            "scheduled_time": o.scheduled_time.strftime("%Y-%m-%d %H:%M") if o.scheduled_time else "",
            "payment_status": o.payment_status,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M"),
        })
    return ok(items)


@router.get("/{order_no}")
async def get_order(order_no: str, user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_database)):
    order = await _get_order(db, order_no, user)
    svc = await db.get(Service, order.service_id)
    return ok({
        "order_no": order.order_no, "status": order.status, "amount": float(order.amount),
        "service_title": svc.title if svc else "", "payment_status": order.payment_status,
        "address": order.address_snapshot, "scheduled_time": order.scheduled_time.strftime("%Y-%m-%d %H:%M") if order.scheduled_time else "",
        "remark": order.remark, "created_at": order.created_at.strftime("%Y-%m-%d %H:%M"),
    })


async def _get_order(db: AsyncSession, order_no: str, user: User) -> Order:
    res = await db.execute(select(Order).where(Order.order_no == order_no))
    order = res.scalar_one_or_none()
    if order is None or order.elder_user_id != user.id:
        raise BizError(40002)
    return order

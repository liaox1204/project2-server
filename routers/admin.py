"""后台管理路由：看板统计 + 用户/订单/服务/求助事件管理（仅 admin）。"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_admin
from models.models import User, Order, Service, EmergencyEvent, HealthRecord, FamilyRelation

router = APIRouter(prefix="/admin", tags=["admin"])

# 订单状态中文映射
ORDER_STATUS = {
    "draft": "草稿", "pending_confirm": "待确认", "paid": "已支付",
    "accepted": "已接单", "on_service": "服务中", "finished": "已完成",
    "cancelled": "已取消", "refunded": "已退款", "abnormal": "异常",
}
SERVICE_TYPES = {
    "escort_medical": "陪诊", "cleaning": "家政", "buy_medicine": "买药",
    "pickup": "取快递", "repair": "维修",
}
EVENT_TYPES = {
    "sos": "紧急求助", "fall": "跌倒", "long_silent": "长期未活动",
    "payment_risk": "支付风险", "scam_report": "诈骗举报",
}


# ============ 看板统计 ============
@router.get("/dashboard")
async def dashboard(admin: User = Depends(get_current_admin),
                    db: AsyncSession = Depends(get_database)):
    async def count(model, *where):
        q = select(func.count()).select_from(model)
        if where:
            q = q.where(*where)
        return (await db.execute(q)).scalar() or 0

    total_users = await count(User, User.is_deleted == 0)
    total_elders = await count(User, User.role_type == "elder", User.is_deleted == 0)
    total_orders = await count(Order)
    total_services = await count(Service, Service.status == 1)
    open_emergencies = await count(EmergencyEvent, EmergencyEvent.status == "open")
    abnormal_health = await count(HealthRecord, HealthRecord.abnormal_flag == 2)
    today = datetime.now().date()
    today_orders = await count(Order, func.date(Order.created_at) == today)

    return ok({
        "total_users": total_users,
        "total_elders": total_elders,
        "total_orders": total_orders,
        "total_services": total_services,
        "open_emergencies": open_emergencies,
        "abnormal_health": abnormal_health,
        "today_orders": today_orders,
    })


# ============ 用户管理 ============
@router.get("/users")
async def list_users(keyword: str = Query(""), role_type: str = Query(""),
                     page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                     admin: User = Depends(get_current_admin),
                     db: AsyncSession = Depends(get_database)):
    q = select(User).where(User.is_deleted == 0)
    if role_type:
        q = q.where(User.role_type == role_type)
    if keyword:
        q = q.where(or_(User.phone.like(f"%{keyword}%"), User.name.like(f"%{keyword}%")))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    users = (await db.execute(q.order_by(User.id.desc()).offset((page - 1) * size).limit(size))).scalars().all()
    items = [{
        "id": u.id, "name": u.name, "phone": u.phone, "role_type": u.role_type,
        "status": u.status, "created_at": u.created_at.strftime("%Y-%m-%d %H:%M"),
    } for u in users]
    return ok({"total": total, "items": items})


@router.post("/users/{user_id}/status")
async def toggle_user_status(user_id: int, status: int,
                             admin: User = Depends(get_current_admin),
                             db: AsyncSession = Depends(get_database)):
    """启用/冻结用户。status: 1正常 2冻结。"""
    user = await db.get(User, user_id)
    if user is None:
        raise BizError(10005, "用户不存在")
    if user.role_type == "admin":
        raise BizError(10003, "不能操作管理员账号")
    user.status = status
    await db.commit()
    return ok(None, "已更新")


# ============ 订单管理 ============
@router.get("/orders")
async def list_orders(status: str = Query(""), keyword: str = Query(""),
                      page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                      admin: User = Depends(get_current_admin),
                      db: AsyncSession = Depends(get_database)):
    q = select(Order)
    if status:
        q = q.where(Order.status == status)
    if keyword:
        q = q.where(Order.order_no.like(f"%{keyword}%"))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    orders = (await db.execute(q.order_by(Order.id.desc()).offset((page - 1) * size).limit(size))).scalars().all()

    items = []
    for o in orders:
        svc = await db.get(Service, o.service_id)
        elder = await db.get(User, o.elder_user_id)
        items.append({
            "order_no": o.order_no, "status": o.status, "status_text": ORDER_STATUS.get(o.status, o.status),
            "amount": float(o.amount), "service_title": svc.title if svc else "",
            "elder_name": elder.name if elder else "", "elder_phone": elder.phone if elder else "",
            "scheduled_time": o.scheduled_time.strftime("%Y-%m-%d %H:%M") if o.scheduled_time else "",
            "payment_status": o.payment_status, "source": o.source,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M"),
        })
    return ok({"total": total, "items": items})


@router.post("/orders/{order_no}/status")
async def update_order_status(order_no: str, status: str,
                              admin: User = Depends(get_current_admin),
                              db: AsyncSession = Depends(get_database)):
    """更新订单状态。"""
    order = (await db.execute(select(Order).where(Order.order_no == order_no))).scalar_one_or_none()
    if order is None:
        raise BizError(40002)
    if status not in ORDER_STATUS:
        raise BizError(10001, "无效的订单状态")
    order.status = status
    await db.commit()
    return ok(None, "已更新")


# ============ 服务管理 ============
@router.get("/services")
async def list_services(admin: User = Depends(get_current_admin),
                        db: AsyncSession = Depends(get_database)):
    services = (await db.execute(select(Service).order_by(Service.id.asc()))).scalars().all()
    items = [{
        "id": s.id, "service_code": s.service_code, "service_type": s.service_type,
        "service_type_text": SERVICE_TYPES.get(s.service_type, s.service_type),
        "title": s.title, "description": s.description, "price": float(s.price),
        "price_unit": s.price_unit, "city": s.city, "status": s.status,
        "need_family_confirm": s.need_family_confirm,
    } for s in services]
    return ok(items)


@router.post("/services")
async def create_service(payload: dict, admin: User = Depends(get_current_admin),
                         db: AsyncSession = Depends(get_database)):
    svc = Service(
        service_code=payload.get("service_code", ""),
        service_type=payload.get("service_type", ""),
        title=payload.get("title", ""),
        description=payload.get("description", ""),
        price=float(payload.get("price", 0)),
        price_unit=payload.get("price_unit", "次"),
        city=payload.get("city", ""),
        need_family_confirm=int(payload.get("need_family_confirm", 0)),
        status=int(payload.get("status", 1)),
    )
    if not svc.title or not svc.service_code:
        raise BizError(10001, "服务名称和编码不能为空")
    db.add(svc)
    await db.commit()
    return ok({"id": svc.id}, "已创建")


@router.post("/services/{service_id}/status")
async def toggle_service_status(service_id: int, status: int,
                                admin: User = Depends(get_current_admin),
                                db: AsyncSession = Depends(get_database)):
    svc = await db.get(Service, service_id)
    if svc is None:
        raise BizError(40001)
    svc.status = status
    await db.commit()
    return ok(None, "已更新")


# ============ 求助事件管理 ============
@router.get("/emergencies")
async def list_emergencies(status: str = Query(""),
                           page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                           admin: User = Depends(get_current_admin),
                           db: AsyncSession = Depends(get_database)):
    q = select(EmergencyEvent)
    if status:
        q = q.where(EmergencyEvent.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    events = (await db.execute(q.order_by(EmergencyEvent.id.desc()).offset((page - 1) * size).limit(size))).scalars().all()

    items = []
    for e in events:
        elder = await db.get(User, e.elder_user_id)
        items.append({
            "event_no": e.event_no, "event_type": e.event_type,
            "event_type_text": EVENT_TYPES.get(e.event_type, e.event_type),
            "level": e.level, "status": e.status,
            "elder_name": elder.name if elder else "", "elder_phone": elder.phone if elder else "",
            "address": e.address, "detail": e.detail or "",
            "created_at": e.created_at.strftime("%Y-%m-%d %H:%M"),
        })
    return ok({"total": total, "items": items})


@router.post("/emergencies/{event_no}/handle")
async def handle_emergency(event_no: str, status: str, handle_result: str = "",
                           admin: User = Depends(get_current_admin),
                           db: AsyncSession = Depends(get_database)):
    """处理求助事件：状态改 open/handling/closed，可填处理结果。"""
    ev = (await db.execute(select(EmergencyEvent).where(EmergencyEvent.event_no == event_no))).scalar_one_or_none()
    if ev is None:
        raise BizError(80001)
    ev.status = status
    ev.handle_result = handle_result
    if status == "closed":
        ev.closed_at = datetime.now()
    if status == "handling":
        ev.handled_at = datetime.now()
        ev.handler_id = admin.id
    await db.commit()
    return ok(None, "已更新")

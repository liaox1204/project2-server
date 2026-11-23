"""VIP 充值路由（模拟支付，不真实扣款）。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_user
from models.models import User
from schemas.news import VipRechargeReq

router = APIRouter(prefix="/vip", tags=["vip"])

# 套餐：plan -> (名称, 价格, 有效期天数)
PLANS = {
    "month":   ("包月", 10.0, 30),
    "quarter": ("包季", 28.0, 90),
    "year":    ("包年", 98.0, 365),
}


def is_vip_valid(user: User) -> bool:
    """VIP 是否有效（充值过且未过期）。"""
    if not user.is_vip:
        return False
    if user.vip_expire_at is None:
        return False
    return user.vip_expire_at > datetime.now()


def vip_status(user: User) -> dict:
    """返回统一的 VIP 状态。"""
    valid = is_vip_valid(user)
    return {
        "is_vip": 1 if valid else 0,
        "vip_expire_at": user.vip_expire_at.strftime("%Y-%m-%d %H:%M") if user.vip_expire_at else "",
    }


@router.get("/plans")
async def plans(user: User = Depends(get_current_user)):
    """套餐列表。"""
    items = [
        {"plan": k, "name": v[0], "price": v[1], "days": v[2]}
        for k, v in PLANS.items()
    ]
    return ok({"plans": items, "status": vip_status(user)})


@router.post("/recharge")
async def recharge(req: VipRechargeReq, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_database)):
    """模拟充值：根据套餐累加 VIP 有效期。不真实支付。"""
    plan = PLANS.get(req.plan)
    if plan is None:
        raise BizError(10001, "无效的套餐类型")

    name, price, days = plan
    now = datetime.now()
    # 起算时间：未过期则从原到期时间续，否则从现在起算
    base = user.vip_expire_at if (user.vip_expire_at and user.vip_expire_at > now) else now
    user.is_vip = 1
    user.vip_expire_at = base + timedelta(days=days)
    await db.commit()
    await db.refresh(user)

    return ok({
        "plan": name,
        "price": price,
        "is_vip": 1,
        "vip_expire_at": user.vip_expire_at.strftime("%Y-%m-%d %H:%M"),
        "message": f"{name}充值成功（模拟）",
    })

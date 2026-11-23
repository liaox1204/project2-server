"""亲情绑定路由。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_user
from crud.common import gen_invite_code
from crud.user import get_user_by_phone
from crud.family import get_relation, get_relation_by_code, list_family_members
from models.models import User, FamilyRelation
from routers.vip import is_vip_valid
from schemas.news import FamilyInviteReq, FamilyApproveReq, FamilyPermissionReq

router = APIRouter(prefix="/family", tags=["family"])

DEFAULT_PERMISSION = {"health_view": True, "proxy_order": False, "proxy_pay": False,
                      "location_sos": True, "wellness": True}


@router.post("/invite")
async def invite(req: FamilyInviteReq, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_database)):
    """子女发起绑定：传父母手机号。仅子女可发起，且必须是 VIP。"""
    # 1. 必须子女身份发起
    if user.role_type != "family":
        raise BizError(10003, "只有子女账号可以绑定父母")

    # 2. 必须是 VIP
    if not is_vip_valid(user):
        raise BizError(10003, "需要先开通 VIP 才能绑定父母，请先充值")

    elder = await get_user_by_phone(db, req.elder_phone)
    if elder is None:
        raise BizError(20005, "未找到该父母账号")
    if elder.role_type != "elder":
        raise BizError(20005, "对方不是父母账号")

    rel = await get_relation(db, elder.id, user.id)
    if rel and rel.status == 1:
        raise BizError(20004)
    if rel is None:
        rel = FamilyRelation(elder_user_id=elder.id, family_user_id=user.id,
                             relation_type=req.relation_type, invite_code=gen_invite_code())
        db.add(rel)
    else:
        rel.invite_code = gen_invite_code()
        rel.status = 0
        rel.invited_at = datetime.now()
    await db.commit()
    return ok({"invite_code": rel.invite_code}, "邀请已发出，等待父母确认")


@router.post("/approve")
async def approve(req: FamilyApproveReq, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_database)):
    """老人确认绑定（传 invite_code）。"""
    rel = await get_relation_by_code(db, req.invite_code)
    if rel is None:
        raise BizError(20005)
    if rel.elder_user_id != user.id:
        raise BizError(10003, "只能确认自己的绑定")
    rel.status = 1
    rel.approved_at = datetime.now()
    rel.permission_config = DEFAULT_PERMISSION
    await db.commit()
    return ok(None, "绑定成功")


@router.post("/revoke")
async def revoke(req: FamilyPermissionReq | None = None, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_database)):
    """解除绑定。需传 family_user_id。"""
    raise BizError(10001, "请在 /family/{id}/permission 或专用解绑接口操作")


@router.get("/members")
async def members(user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_database)):
    """当前老人已绑定的子女列表。"""
    rels = await list_family_members(db, user.id)
    result = []
    for r in rels:
        fam = await db.get(User, r.family_user_id)
        result.append({"relation_id": r.id, "name": fam.name if fam else "", "phone": fam.phone if fam else "",
                       "relation_type": r.relation_type, "permission_config": r.permission_config})
    return ok(result)


@router.put("/{relation_id}/permission")
async def update_permission(relation_id: int, req: FamilyPermissionReq,
                            user: User = Depends(get_current_user),
                            db: AsyncSession = Depends(get_database)):
    rel = await db.get(FamilyRelation, relation_id)
    if rel is None or rel.elder_user_id != user.id:
        raise BizError(20005)
    rel.permission_config = req.permission_config
    await db.commit()
    return ok(None, "权限已更新")

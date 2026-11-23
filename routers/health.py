"""健康记录路由。"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_user
from crud.health import judge_abnormal
from crud.family import list_elders_of_family, get_relation
from models.models import User, HealthRecord, FamilyRelation
from schemas.news import HealthRecordReq

router = APIRouter(prefix="/health", tags=["health"])

VALID_TYPES = {"blood_pressure", "blood_glucose", "weight", "heart_rate", "temperature"}


async def _check_family_access(db: AsyncSession, family_user: User, elder_user_id: int):
    """校验子女与父母的绑定关系（status=1 生效才可看）。"""
    rel = await get_relation(db, elder_user_id, family_user.id)
    if rel is None or rel.status != 1:
        raise BizError(10003, "未绑定该父母，无法查看健康记录")


@router.post("/records")
async def create_record(req: HealthRecordReq, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    if req.record_type not in VALID_TYPES:
        raise BizError(30001)
    abnormal = judge_abnormal(req.record_type, req.value_json)
    rec = HealthRecord(
        elder_user_id=user.id, record_type=req.record_type, value_json=req.value_json,
        abnormal_flag=abnormal, record_source=req.record_source or "manual",
        recorded_at=req.recorded_at or datetime.now(), remark=req.remark,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return ok({"id": rec.id, "abnormal_flag": abnormal}, "记录成功")


@router.get("/records")
async def list_records(record_type: str = Query(""),
                       page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_database)):
    q = select(HealthRecord).where(HealthRecord.elder_user_id == user.id, HealthRecord.is_deleted == 0)
    if record_type:
        q = q.where(HealthRecord.record_type == record_type)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(HealthRecord.recorded_at.desc()).offset((page - 1) * size).limit(size)
    records = (await db.execute(q)).scalars().all()
    items = [{
        "id": r.id, "record_type": r.record_type, "value_json": r.value_json,
        "abnormal_flag": r.abnormal_flag, "record_source": r.record_source,
        "recorded_at": r.recorded_at.strftime("%Y-%m-%d %H:%M"),
        "remark": r.remark,
    } for r in records]
    return ok({"total": total, "items": items})


@router.get("/trend")
async def trend(record_type: str = Query("blood_pressure"),
                user: User = Depends(get_current_user),
                db: AsyncSession = Depends(get_database)):
    """趋势数据（ECharts 用），返回最近 30 条。"""
    q = select(HealthRecord).where(
        HealthRecord.elder_user_id == user.id, HealthRecord.is_deleted == 0,
        HealthRecord.record_type == record_type,
    ).order_by(HealthRecord.recorded_at.asc()).limit(30)
    records = (await db.execute(q)).scalars().all()
    items = []
    for r in records:
        v = r.value_json or {}
        item = {"time": r.recorded_at.strftime("%m-%d %H:%M")}
        if record_type == "blood_pressure":
            item["systolic"] = v.get("systolic")
            item["diastolic"] = v.get("diastolic")
        else:
            item["value"] = v.get("value")
        items.append(item)
    return ok(items)


# ============ 子女查看父母健康记录 ============
@router.get("/family/elders")
async def family_elders(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    """子女查看已绑定的父母列表（含父母基本信息）。"""
    if user.role_type != "family":
        raise BizError(10003, "只有子女账号可以查看父母健康")
    rels = await list_elders_of_family(db, user.id)
    items = []
    for r in rels:
        elder = await db.get(User, r.elder_user_id)
        if elder:
            items.append({
                "elder_user_id": elder.id,
                "name": elder.name,
                "phone": elder.phone,
                "relation_id": r.id,
            })
    return ok(items)


@router.get("/family/records")
async def family_records(elder_user_id: int = Query(...),
                         record_type: str = Query(""),
                         page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_database)):
    """子女查看某位已绑定父母的健康记录。"""
    if user.role_type != "family":
        raise BizError(10003, "只有子女账号可以查看父母健康")
    await _check_family_access(db, user, elder_user_id)

    q = select(HealthRecord).where(HealthRecord.elder_user_id == elder_user_id, HealthRecord.is_deleted == 0)
    if record_type:
        q = q.where(HealthRecord.record_type == record_type)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(HealthRecord.recorded_at.desc()).offset((page - 1) * size).limit(size)
    records = (await db.execute(q)).scalars().all()
    items = [{
        "id": r.id, "record_type": r.record_type, "value_json": r.value_json,
        "abnormal_flag": r.abnormal_flag, "record_source": r.record_source,
        "recorded_at": r.recorded_at.strftime("%Y-%m-%d %H:%M"),
        "remark": r.remark,
    } for r in records]
    return ok({"total": total, "items": items})


@router.get("/family/trend")
async def family_trend(elder_user_id: int = Query(...),
                       record_type: str = Query("blood_pressure"),
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_database)):
    """子女查看某位父母健康趋势。"""
    if user.role_type != "family":
        raise BizError(10003, "只有子女账号可以查看父母健康")
    await _check_family_access(db, user, elder_user_id)

    q = select(HealthRecord).where(
        HealthRecord.elder_user_id == elder_user_id, HealthRecord.is_deleted == 0,
        HealthRecord.record_type == record_type,
    ).order_by(HealthRecord.recorded_at.asc()).limit(30)
    records = (await db.execute(q)).scalars().all()
    items = []
    for r in records:
        v = r.value_json or {}
        item = {"time": r.recorded_at.strftime("%m-%d %H:%M")}
        if record_type == "blood_pressure":
            item["systolic"] = v.get("systolic")
            item["diastolic"] = v.get("diastolic")
        else:
            item["value"] = v.get("value")
        items.append(item)
    return ok(items)

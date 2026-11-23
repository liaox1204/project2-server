"""用户档案路由。"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from core.response import ok, BizError
from core.deps import get_current_user
from crud.user import ensure_profile
from models.models import User
from schemas.news import ProfileUpdate

router = APIRouter(prefix="/users", tags=["users"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return ok({"id": user.id, "name": user.name, "phone": user.phone,
               "role_type": user.role_type, "avatar": user.avatar or ""})


@router.get("/me/profile")
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_database)):
    profile = await ensure_profile(db, user.id)
    await db.commit()
    return ok({
        "user_id": user.id, "name": user.name, "phone": user.phone,
        "avatar": user.avatar or "",
        "gender": profile.gender, "birth_year": profile.birth_year,
        "province": profile.province, "city": profile.city, "district": profile.district,
        "default_address": profile.default_address,
        "emergency_contact_name": profile.emergency_contact_name,
        "emergency_contact_phone": profile.emergency_contact_phone,
        "chronic_diseases": profile.chronic_diseases, "medicines": profile.medicines,
        "dialect": profile.dialect, "font_scale": profile.font_scale,
        "voice_speed": float(profile.voice_speed) if profile.voice_speed else 0.85,
    })


@router.put("/me/profile")
async def update_profile(req: ProfileUpdate, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_database)):
    profile = await ensure_profile(db, user.id)
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    await db.commit()
    return ok(None, "档案已更新")


@router.post("/me/avatar")
async def upload_avatar(file: UploadFile = File(...),
                        user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    """上传头像：保存到 uploads 目录，avatar 字段存访问路径。"""
    # 校验扩展名
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise BizError(10001, "仅支持 jpg/png/gif/webp 格式图片")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise BizError(10001, "图片大小不能超过 5MB")

    filename = f"avatar_{user.id}_{uuid.uuid4().hex}{suffix}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(content)

    # 删除旧头像
    if user.avatar:
        old_path = UPLOAD_DIR / Path(user.avatar).name
        if old_path.exists():
            try:
                old_path.unlink()
            except Exception:
                pass

    user.avatar = f"/static/{filename}"
    await db.commit()
    return ok({"avatar": user.avatar}, "头像上传成功")

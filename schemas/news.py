"""Pydantic 请求/响应模型."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============ 认证 ============
class SmsCodeReq(BaseModel):
    phone: str


class LoginReq(BaseModel):
    phone: str
    password: str = ""                  # 密码登录


class RegisterReq(BaseModel):
    phone: str
    password: str
    name: str = ""
    role_type: str = "elder"            # elder=父母 / family=子女


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


# ============ 用户档案 ============
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[int] = None
    birth_year: Optional[int] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    default_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    chronic_diseases: Optional[list] = None
    medicines: Optional[list] = None
    dialect: Optional[str] = None
    font_scale: Optional[int] = None
    voice_speed: Optional[float] = None


# ============ 亲情 ============
class FamilyInviteReq(BaseModel):
    elder_phone: str
    relation_type: str = "child"


class FamilyApproveReq(BaseModel):
    invite_code: str


class FamilyPermissionReq(BaseModel):
    permission_config: dict


# ============ VIP 充值 ============
class VipRechargeReq(BaseModel):
    plan: str      # month=包月 / quarter=包季 / year=包年


# ============ 健康 ============
class HealthRecordReq(BaseModel):
    record_type: str                       # blood_pressure/blood_glucose/weight/heart_rate/temperature
    value_json: dict
    recorded_at: Optional[datetime] = None
    remark: str = ""
    record_source: str = "manual"


# ============ 服务与订单 ============
class OrderDraftReq(BaseModel):
    service_id: int
    scheduled_time: Optional[datetime] = None
    address: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    remark: str = ""


# ============ 提醒 ============
class ReminderCreateReq(BaseModel):
    reminder_type: str = "medicine"        # medicine/measure/appointment/activity/wellness
    title: str
    content: str = ""
    trigger_at: Optional[datetime] = None
    trigger_cron: str = ""
    notify_family: int = 0


class ReminderUpdateReq(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    trigger_at: Optional[datetime] = None
    status: Optional[int] = None


# ============ 求助 ============
class SOSTReq(BaseModel):
    event_type: str = "sos"
    level: int = 2
    address: str = ""
    detail: str = ""
    lng: Optional[float] = None
    lat: Optional[float] = None
    source: str = "manual"


# ============ AI ============
class VoiceReq(BaseModel):
    session_id: str = ""
    text: str = ""
    audio_base64: Optional[str] = None
    audio_format: str = "wav"      # 音频格式：wav/webm/mp3/m4a/ogg 等


class ChatReq(BaseModel):
    session_id: str = ""
    text: str


class ConfirmReq(BaseModel):
    session_id: str
    action_id: str
    confirmed: bool = True

"""SQLAlchemy ORM 模型（对应设计文档第 6 章建表）."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, String, Integer, SmallInteger, DECIMAL, JSON, Text,
    DateTime, Date, ForeignKey, Index, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ============ 1. 用户主表 ============
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role_type: Mapped[str] = mapped_column(String(16), default="elder", comment="elder/family/worker/admin")
    name: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    avatar: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1正常 2冻结 3注销")
    is_deleted: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_vip: Mapped[int] = mapped_column(SmallInteger, default=0, comment="是否VIP 0否 1是")
    vip_expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="VIP到期时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_role_status", "role_type", "status"),
    )


# ============ 2. 老人档案 ============
class ElderProfile(Base):
    __tablename__ = "elder_profiles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)
    birth_year: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    gender: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, comment="1男 2女")
    province: Mapped[str] = mapped_column(String(32), default="")
    city: Mapped[str] = mapped_column(String(32), default="")
    district: Mapped[str] = mapped_column(String(32), default="")
    default_address: Mapped[str] = mapped_column(String(255), default="")
    emergency_contact_name: Mapped[str] = mapped_column(String(64), default="")
    emergency_contact_phone: Mapped[str] = mapped_column(String(20), default="")
    chronic_diseases: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    medicines: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    mobility_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    hearing_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    vision_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    dialect: Mapped[str] = mapped_column(String(32), default="")
    font_scale: Mapped[int] = mapped_column(SmallInteger, default=1)
    voice_speed: Mapped[float] = mapped_column(DECIMAL(3, 2), default=0.85)
    hobbies: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ============ 3. 亲情绑定关系 ============
class FamilyRelation(Base):
    __tablename__ = "family_relations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    elder_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    family_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(16), default="child")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="0待确认 1生效 2已解除")
    permission_config: Mapped[dict] = mapped_column(JSON, default=dict)
    amount_limit: Mapped[float] = mapped_column(DECIMAL(12, 2), default=0.00)
    invite_code: Mapped[str] = mapped_column(String(32), default="")
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("uk_pair", "elder_user_id", "family_user_id", unique=True),
    )


# ============ 4. 健康记录 ============
class HealthRecord(Base):
    __tablename__ = "health_records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    elder_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(24), comment="blood_pressure/blood_glucose/weight/heart_rate/temperature")
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    unit: Mapped[str] = mapped_column(String(16), default="")
    abnormal_flag: Mapped[int] = mapped_column(SmallInteger, default=0, comment="0正常 1偏高偏低 2需通知")
    record_source: Mapped[str] = mapped_column(String(16), default="manual", comment="manual/voice/device")
    session_id: Mapped[str] = mapped_column(String(64), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    remark: Mapped[str] = mapped_column(String(255), default="")
    is_deleted: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_user_type_time", "elder_user_id", "record_type", "recorded_at"),
    )


# ============ 5. 服务目录 ============
class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service_code: Mapped[str] = mapped_column(String(32), unique=True)
    service_type: Mapped[str] = mapped_column(String(32), comment="escort_medical/cleaning/buy_medicine/pickup/repair")
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    price: Mapped[float] = mapped_column(DECIMAL(12, 2), default=0.00)
    price_unit: Mapped[str] = mapped_column(String(16), default="次")
    provider_id: Mapped[int] = mapped_column(BigInteger, default=0)
    city: Mapped[str] = mapped_column(String(32), default="")
    service_area: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    need_family_confirm: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_type_city", "service_type", "city", "status"),
    )


# ============ 6. 订单 ============
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True)
    elder_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    family_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    service_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("services.id"))
    provider_id: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    amount: Mapped[float] = mapped_column(DECIMAL(12, 2), default=0.00)
    payment_mode: Mapped[str] = mapped_column(String(16), default="self")
    payment_status: Mapped[str] = mapped_column(String(16), default="unpaid")
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    address_snapshot: Mapped[str] = mapped_column(String(255), default="")
    contact_snapshot: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(16), default="manual", comment="voice/ai/manual")
    ai_session_id: Mapped[str] = mapped_column(String(64), default="")
    remark: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_elder_status", "elder_user_id", "status", "scheduled_time"),
        Index("idx_family_status", "family_user_id", "status"),
    )


# ============ 7. 通用提醒 ============
class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    elder_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    reminder_type: Mapped[str] = mapped_column(String(24), comment="medicine/measure/appointment/activity/wellness")
    title: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(String(255), default="")
    trigger_cron: Mapped[str] = mapped_column(String(64), default="")
    trigger_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notify_family: Mapped[int] = mapped_column(SmallInteger, default=0)
    family_timeout_min: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_trigger", "status", "trigger_at"),
    )


# ============ 8. 求助事件 ============
class EmergencyEvent(Base):
    __tablename__ = "emergency_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_no: Mapped[str] = mapped_column(String(32), unique=True)
    elder_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(24), comment="sos/fall/long_silent/payment_risk/scam_report")
    level: Mapped[int] = mapped_column(SmallInteger, default=1)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    lng: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 6), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 6), nullable=True)
    address: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open")
    handler_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    handle_result: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ============ 9. AI 会话 ============
class AIConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), comment="user/assistant/tool/system")
    content: Mapped[str] = mapped_column(Text)
    asr_text_raw: Mapped[str] = mapped_column(String(512), default="")
    asr_confidence: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)
    intent: Mapped[str] = mapped_column(String(32), default="")
    agent_name: Mapped[str] = mapped_column(String(32), default="")
    risk_level: Mapped[str] = mapped_column(String(16), default="none")
    model_name: Mapped[str] = mapped_column(String(64), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_session", "session_id", "created_at"),
    )


# ============ 10. AI 长期记忆 ============
class UserMemory(Base):
    __tablename__ = "user_memories"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    memory_type: Mapped[str] = mapped_column(String(24), comment="fact/preference/summary")
    key_name: Mapped[str] = mapped_column(String(64), default="")
    content: Mapped[str] = mapped_column(String(512))
    confidence: Mapped[float] = mapped_column(DECIMAL(4, 3), default=0.9)
    visible: Mapped[int] = mapped_column(SmallInteger, default=1)
    source_session: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ============ 11. 通知 ============
class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    to_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    biz_type: Mapped[str] = mapped_column(String(24), default="app")
    title: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(16), default="app")
    biz_ref_id: Mapped[int] = mapped_column(BigInteger, default=0)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

"""AI 主控编排：意图路由 -> 业务执行 -> 确认 gate -> 回复生成。

实现与设计文档 LangGraph 图等同的语义：
- load_context：加载老人档案 + 亲情 + 长期记忆
- router：意图识别 + 槽位
- dispatch：路由到健康/预约/提醒/亲情/安全/客服 子逻辑
- confirm gate：高风险动作生成 pending_action 待确认
- reply：生成口语化回复
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import BizError
from ai.chains.intent import classify
from ai.chains.reply import generate_reply, simple_reply
from ai.guard import screen_input, screen_output, fallback_message, DISCLAIMER
from models.models import (
    User, ElderProfile, FamilyRelation, HealthRecord, Service, Order,
    Reminder, UserMemory, AIConversation, Notification,
)
from crud.health import judge_abnormal
from crud.common import gen_order_no, gen_session_id

# 待确认动作（内存态，简化实现；生产可用 Redis）
_pending_actions: dict = {}


async def _load_context(db: AsyncSession, user: User) -> dict:
    ctx = {"profile": None, "family": [], "memories": []}
    res = await db.execute(select(ElderProfile).where(ElderProfile.user_id == user.id))
    ctx["profile"] = res.scalar_one_or_none()
    res = await db.execute(
        select(FamilyRelation).where(FamilyRelation.elder_user_id == user.id, FamilyRelation.status == 1)
    )
    ctx["family"] = res.scalars().all()
    res = await db.execute(
        select(UserMemory).where(UserMemory.user_id == user.id, UserMemory.visible == 1)
    )
    ctx["memories"] = res.scalars().all()
    return ctx


def _save_conversation(db: AsyncSession, session_id: str, user_id: int, role: str, content: str,
                       intent: str = "", agent: str = "", risk: str = "none"):
    db.add(AIConversation(
        session_id=session_id, user_id=user_id, role=role, content=content,
        intent=intent, agent_name=agent, risk_level=risk,
    ))


async def _record_health(db: AsyncSession, user: User, slots: dict, raw_text: str = "") -> str:
    value_text = slots.get("value_text") or raw_text or ""
    record_type = slots.get("health_type") or _infer_health_type(value_text)
    value_json = _parse_health_value(record_type, value_text)

    # 用户只说了"血糖高/血压高"，但没给具体数值 → 及时提醒去测量并告知数值
    if record_type and not value_json:
        return ("我听到您说" + _HEALTH_LABELS.get(record_type, "健康数据") +
                "有异常。请您现在就测量一下具体数值告诉我（比如" +
                _TYPE_EXAMPLE.get(record_type, "具体数值") +
                "），我会帮您判断是否在正常范围。如感觉不适，请立即就医或联系家人。")

    if not record_type or not value_json:
        return "您说健康数据我没听清，可以告诉我血压、血糖、体重多少。"

    abnormal = judge_abnormal(record_type, value_json)
    is_high, is_low = _judge_direction(record_type, value_json)
    rec = HealthRecord(
        elder_user_id=user.id, record_type=record_type, value_json=value_json,
        abnormal_flag=abnormal, record_source="voice",
    )
    db.add(rec)
    await db.flush()

    label = _HEALTH_LABELS.get(record_type, record_type)

    if abnormal >= 1:
        # 偏高/偏低：给出"提醒"，而非建议
        direction = "偏高" if is_high else ("偏低" if is_low else "异常")
        if abnormal == 2:
            return (f"⚠️ 提醒您：您的{label}{direction}比较明显，属于需要警惕的范围。"
                    f"请立即复测，如有不适请马上就医或联系家人。")
        return (f"⚠️ 提醒您：您的{label}{direction}，已超出正常范围。"
                f"请及时复测，持续异常请尽快就医。")
    return f"记好了，您的{label}今天正常。"


_HEALTH_LABELS = {
    "blood_pressure": "血压", "blood_glucose": "血糖", "weight": "体重",
    "heart_rate": "心率", "temperature": "体温",
}

_TYPE_EXAMPLE = {
    "blood_pressure": "高压120低压80",
    "blood_glucose": "空腹血糖6.0",
    "weight": "体重60公斤",
    "heart_rate": "心率75",
    "temperature": "体温36.5",
}


def _judge_direction(record_type: str, value_json: dict):
    """判断偏高/偏低。返回 (is_high, is_low)。"""
    from crud.health import ABNORMAL_RULES
    rule = ABNORMAL_RULES.get(record_type)
    if not rule:
        return False, False
    try:
        if record_type == "blood_pressure":
            s = float(value_json.get("systolic", 0))
            d = float(value_json.get("diastolic", 0))
            if s == 0 and d == 0:
                return False, False
            high = s >= rule["high"]["systolic"] or d >= rule["high"]["diastolic"]
            low = s <= rule["low"]["systolic"] or d <= rule["low"]["diastolic"]
            return high, low
        value = float(value_json.get("value", 0))
        if value == 0:
            for v in value_json.values():
                try:
                    value = float(v)
                    break
                except (TypeError, ValueError):
                    continue
        if value == 0:
            return False, False
        return value >= rule["high"], value <= rule["low"]
    except (TypeError, ValueError):
        return False, False


def _infer_health_type(text: str) -> str:
    if "血压" in text or "高压" in text or "低压" in text:
        return "blood_pressure"
    if "血糖" in text:
        return "blood_glucose"
    if "体重" in text:
        return "weight"
    if "心率" in text or "心跳" in text:
        return "heart_rate"
    if "体温" in text or "发烧" in text:
        return "temperature"
    return ""


def _parse_health_value(record_type: str, text: str) -> dict:
    import re
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if record_type == "blood_pressure":
        if len(nums) >= 2:
            return {"systolic": int(float(nums[0])), "diastolic": int(float(nums[1]))}
        return {}
    if nums:
        return {"value": float(nums[0])}
    return {}


def _notify_family(db: AsyncSession, elder_user_id: int, biz_type: str, title: str, content: str):
    db.add(Notification(to_user_id=elder_user_id, biz_type=biz_type, title=title, content=content))


async def _query_health(db: AsyncSession, user: User) -> str:
    res = await db.execute(
        select(HealthRecord).where(HealthRecord.elder_user_id == user.id, HealthRecord.is_deleted == 0)
        .order_by(HealthRecord.recorded_at.desc()).limit(5)
    )
    records = res.scalars().all()
    if not records:
        return "您还没有健康记录，可以说“帮我记血压150 90”。"
    lines = []
    for r in records[:3]:
        lines.append(f"{r.recorded_at.strftime('%m月%d日')} 记录：{_describe_health(r)}")
    return "您最近的健康记录是：" + "；".join(lines)


def _describe_health(r: HealthRecord) -> str:
    v = r.value_json or {}
    if r.record_type == "blood_pressure":
        return f"血压{v.get('systolic','?')}/{v.get('diastolic','?')}"
    return f"{r.record_type} {v.get('value','?')}"


async def _booking(db: AsyncSession, user: User, slots: dict, session_id: str) -> dict:
    service_type = slots.get("service_type", "")
    time_text = slots.get("time_text", "")
    location = slots.get("location", "")
    # 查服务目录
    stype_map = {"陪诊": "escort_medical", "家政": "cleaning", "买药": "buy_medicine",
                 "取快递": "pickup", "维修": "repair"}
    code = stype_map.get(service_type, "")
    q = select(Service).where(Service.status == 1)
    if code:
        q = q.where(Service.service_type == code)
    res = await db.execute(q.limit(5))
    services = res.scalars().all()
    if not services:
        return {"reply": f"暂时没找到{service_type or '这个'}服务，您可以说“找服务”看看有哪些。",
                "need_confirm": False}
    svc = services[0]
    # 解析时间
    scheduled = _parse_time(time_text)
    amount = float(svc.price or 0)
    need_confirm = amount > 100 or bool(svc.need_family_confirm)
    # 建草稿
    order = Order(
        order_no=gen_order_no("D"), elder_user_id=user.id, service_id=svc.id,
        provider_id=svc.provider_id, status="draft", amount=amount,
        scheduled_time=scheduled, address_snapshot=location or "",
        source="ai", ai_session_id=session_id, remark="",
    )
    db.add(order)
    await db.flush()
    # 简洁化时间显示（去掉口令词，只保留关键时间信息）
    friendly_time = _friendly_time_text(time_text, scheduled)
    reply = f"我帮您找到“{svc.title}”，{friendly_time}，{location or '按档案地址'}，大概{amount:.0f}元。"
    action = None
    if need_confirm:
        action_id = f"act_{order.order_no}"
        _pending_actions[action_id] = {"order_no": order.order_no, "elder_user_id": user.id}
        action = {"type": "order_confirm", "action_id": action_id,
                  "order_no": order.order_no, "service": svc.title,
                  "amount": amount, "scheduled_time": str(scheduled) if scheduled else ""}
        reply += " 需要您确认一下。"
    else:
        # 低金额直接转待服务（demo 简化：确认即 paid）
        order.status = "paid"
        reply += " 订单已为您安排。"
    await db.flush()
    return {"reply": reply, "need_confirm": need_confirm, "action": action,
            "intent": "service_booking", "agent": "booking_agent"}


def _parse_time(text: str) -> Optional[datetime]:
    from datetime import timedelta
    now = datetime.now()
    if not text:
        return now + timedelta(days=1)
    if "明天" in text:
        base = now + timedelta(days=1)
    elif "后天" in text:
        base = now + timedelta(days=2)
    elif "今天" in text:
        base = now
    else:
        base = now + timedelta(days=1)
    import re
    m = re.search(r"(\d{1,2})[点时:]", text)
    hour = int(m.group(1)) if m else 9
    # 上午/下午/晚上
    if "下午" in text and hour < 12:
        hour += 12
    if "晚上" in text and hour < 18:
        hour += 12
    return base.replace(hour=hour, minute=0, second=0, microsecond=0)


def _friendly_time_text(time_text: str, scheduled: Optional[datetime]) -> str:
    """把时间槽位转成简洁口语，去掉口令词。"""
    if scheduled:
        return scheduled.strftime("%m月%d日 %H:%M")
    # 回退：提取关键词
    for kw in ("明天上午", "明天下午", "后天", "今天", "上午", "下午", "晚上"):
        if kw in time_text:
            return kw
    return "约好时间后"


async def _create_reminder(db: AsyncSession, user: User, slots: dict, text: str) -> str:
    title = text[:30] or "提醒"
    trigger_at = _parse_time(slots.get("time_text", ""))
    db.add(Reminder(
        elder_user_id=user.id, reminder_type="medicine", title=title,
        content=text, trigger_at=trigger_at,
    ))
    await db.flush()
    t = trigger_at.strftime("%m月%d日 %H:%M") if trigger_at else "指定时间"
    return f"好的，我会在{t}提醒您。"


async def _sos(db: AsyncSession, user: User, text: str) -> str:
    from models.models import EmergencyEvent
    from crud.common import gen_event_no
    ev = EmergencyEvent(event_no=gen_event_no(), elder_user_id=user.id,
                        event_type="sos", level=2, source="ai", detail=text,
                        status="open")
    db.add(ev)
    _notify_family(db, user.id, "emergency", "家人求助", "您关心的人发起了紧急求助，请尽快联系。")
    return "我已经帮您发出求助，家人和工作人员会尽快联系您。请保持电话畅通。"


# ============ 主动作入口 ============
async def _core_reply(db: AsyncSession, user: User, text: str, session_id: str = "") -> dict:
    """执行完整流程，返回中间态（含已生成但未流式输出的 reply）。

    返回字段：reply(intent/agent/need_confirm/action)、polish_allowed(bool 是否需要 LLM 润色)
    """
    session_id = session_id or gen_session_id()

    # 输入护栏
    safe, reason = screen_input(text)
    if not safe:
        return {"reply": fallback_message(reason), "need_confirm": False,
                "session_id": session_id, "intent": "unknown", "agent": "guard",
                "polish_allowed": False}

    # 意图识别
    cls = await classify(text)
    intent = cls["intent"]
    slots = cls["slots"] or {}
    confidence = cls["confidence"]

    # 保存用户消息
    _save_conversation(db, session_id, user.id, "user", text, intent=intent, risk="none")

    reply = ""
    need_confirm = False
    action = None
    agent = "support_agent"

    if intent == "sos":
        agent = "safety_agent"
        reply = await _sos(db, user, text)
    elif intent == "safety_alert":
        agent = "safety_agent"
        reply = ("您提到的情况可能有风险，千万别转账、别透露验证码。"
                 "我已经记录，并建议您先和家人或工作人员核实一下。")
    elif intent == "health_record":
        agent = "health_agent"
        reply = await _record_health(db, user, slots, text)
    elif intent == "health_query":
        agent = "health_agent"
        reply = await _query_health(db, user)
    elif intent == "service_booking":
        res = await _booking(db, user, slots, session_id)
        reply = res["reply"]
        need_confirm = res.get("need_confirm", False)
        action = res.get("action")
        agent = res.get("agent", "booking_agent")
    elif intent == "reminder_create":
        agent = "reminder_agent"
        reply = await _create_reminder(db, user, slots, text)
    elif intent == "order_query":
        agent = "support_agent"
        res = await db.execute(
            select(Order).where(Order.elder_user_id == user.id).order_by(Order.created_at.desc()).limit(3)
        )
        orders = res.scalars().all()
        if orders:
            o = orders[0]
            reply = f"您最近的订单“{o.order_no}”当前状态是{o.status}。"
        else:
            reply = "您还没有订单，可以说“帮我预约陪诊”。"
    elif intent == "family_manage":
        agent = "family_agent"
        cnt = (await db.execute(
            select(FamilyRelation).where(FamilyRelation.elder_user_id == user.id, FamilyRelation.status == 1)
        )).scalars().all()
        reply = f"您目前有{len(cnt)}位家人在亲情账户里。您想添加或管理家人可以告诉我。"
    elif intent == "chitchat":
        agent = "support_agent"
        reply = "您好呀！有什么我可以帮您的吗？比如记健康、约服务、设提醒。"
    else:
        agent = "support_agent"
        reply = ("我可以帮您记健康数据、预约服务、设置提醒、查询订单。"
                 "您想办理哪件事呢？")

    # 是否需要 LLM 润色（配了 Key 且不是兜底话术）
    polish_allowed = _should_polish(reply)

    return {
        "reply": reply,
        "intent": intent,
        "agent": agent,
        "need_confirm": need_confirm,
        "action": action,
        "session_id": session_id,
        "polish_allowed": polish_allowed,
        "risk": "medium" if intent in ("sos", "safety_alert") else "none",
    }


async def run_agent(db: AsyncSession, user: User, text: str, session_id: str = "") -> dict:
    core = await _core_reply(db, user, text, session_id)

    reply = core["reply"]
    # 适老化口语化回复（LLM 可用时润色）
    if core["polish_allowed"]:
        polished = await generate_reply(reply)
        if polished:
            reply = polished
    reply = screen_output(reply)

    # 保存助手消息
    _save_conversation(db, core["session_id"], user.id, "assistant", reply,
                       intent=core["intent"], agent=core["agent"], risk=core["risk"])
    await db.commit()

    return {
        "reply": reply,
        "reply_audio_url": "",
        "intent": core["intent"],
        "agent": core["agent"],
        "need_confirm": core["need_confirm"],
        "action": core["action"],
        "session_id": core["session_id"],
        "notify_family": core["intent"] in ("sos", "safety_alert"),
    }


async def run_agent_stream(db: AsyncSession, user: User, text: str, session_id: str = ""):
    """流式执行：先产出基础元信息，再逐块 yield 回复文本。

    生成器 yield 两种对象：
      - dict：首帧元信息（含 intent/agent/need_confirm/action/session_id）
      - str：后续的文本增量
    """
    from ai.llm.provider import chat_stream, llm_available

    core = await _core_reply(db, user, text, session_id)

    # 首帧：元信息
    yield {
        "type": "meta",
        "intent": core["intent"],
        "agent": core["agent"],
        "need_confirm": core["need_confirm"],
        "action": core["action"],
        "session_id": core["session_id"],
        "notify_family": core["intent"] in ("sos", "safety_alert"),
    }

    final_reply = ""
    if core["polish_allowed"] and llm_available():
        # 真实 LLM 流式润色
        got_any = False
        async for piece in chat_stream(
            [{"role": "user", "content": f"请把下面这句话改得口语化、亲切、简短（不超过60字）：{core['reply']}"}],
            temperature=0.5,
        ):
            got_any = True
            final_reply += piece
            yield {"type": "delta", "content": piece}
        if got_any and final_reply.strip():
            final_reply = screen_output(final_reply)
        else:
            final_reply = ""
    else:
        # 无 LLM：按字符分块模拟流式（打字机效果）
        raw = screen_output(core["reply"])
        import asyncio
        # 每 1 个字符一块，模拟逐字输出
        for i in range(0, len(raw), 1):
            piece = raw[i:i + 1]
            final_reply += piece
            yield {"type": "delta", "content": piece}
            await asyncio.sleep(0.04)

    if not final_reply:
        final_reply = screen_output(core["reply"])
        yield {"type": "delta", "content": final_reply}

    # 结束帧
    yield {"type": "done", "reply": final_reply}

    # 保存助手消息
    _save_conversation(db, core["session_id"], user.id, "assistant", final_reply,
                       intent=core["intent"], agent=core["agent"], risk=core["risk"])
    await db.commit()


def _should_polish(reply: str) -> bool:
    from ai.llm.provider import llm_available
    return llm_available()


async def confirm_action(db: AsyncSession, user: User, session_id: str, action_id: str, confirmed: bool) -> dict:
    action = _pending_actions.pop(action_id, None)
    if not action:
        raise BizError(70004, "该确认已失效，请重新操作")
    res = await db.execute(select(Order).where(Order.order_no == action["order_no"]))
    order = res.scalar_one_or_none()
    if not order:
        raise BizError(40002)
    if confirmed:
        order.status = "paid"
        await db.flush()
        reply = "好的，订单已确认，我们会尽快为您安排服务。"
    else:
        order.status = "cancelled"
        await db.flush()
        reply = "好的，已帮您取消这个订单。"
    _save_conversation(db, session_id, user.id, "assistant", reply, agent="booking_agent")
    await db.commit()
    return {"reply": reply, "order_no": order.order_no, "status": order.status}

"""意图识别 + 槽位抽取。

策略：
1. LLM 可用时，用小模型/主模型做意图分类与槽位抽取（JSON 输出）。
2. LLM 不可用或失败时，降级到本地规则分类器（关键词匹配），保证基本可用。
"""

INTENT_PROMPT = """你是"银发AI语音生活助手"的意图识别模块，服务对象是使用语音的中老年用户，说话常有口音、省略、口语化。

可选意图（intent 只能取其中之一）：
- health_record  记录健康数据（血压/血糖/体重/心率/体温）
- health_query   查询健康情况
- service_booking 预约服务（陪诊/家政/买药/取快递/维修）
- order_query    查询订单
- reminder_create 设置提醒（用药/测量/复诊/活动/安康打卡）
- family_manage  亲情绑定相关
- safety_alert   疑似诈骗或风险
- sos            紧急求助
- support_question 使用咨询
- chitchat       闲聊
- unknown        无法判断

必须抽取的槽位（slots，没有的字段填 null）：
service_type（服务类型，如"陪诊""家政""买药""取快递""维修"）、time_text（时间文本）、location（地点）、medicine（药品名）、value_text（数值文本，如"高压150低压95""体重70公斤"）、contact（联系人）

老人说话常有口音、省略、口语化，请按最可能的生活意图理解。
若同时涉及身体不适与服务需求，intent 取更紧急者，并在 extra.sub_intent 中标注次意图。

只输出 JSON，不要输出其它文字。格式：
{"intent":"service_booking","confidence":0.92,"slots":{"service_type":"陪诊","time_text":"明天上午","location":"市医院","medicine":null,"value_text":null,"contact":null},"extra":{"sub_intent":"health"}}
"""

# LLM 可用时调用
async def classify_with_llm(text: str) -> dict:
    from ai.llm.provider import chat_json
    messages = [
        {"role": "system", "content": INTENT_PROMPT},
        {"role": "user", "content": text},
    ]
    result = await chat_json(messages)
    if not result:
        return _fallback_classify(text)
    # 规范化
    intent = str(result.get("intent", "unknown"))
    if intent not in VALID_INTENTS:
        intent = "unknown"
    return {
        "intent": intent,
        "confidence": float(result.get("confidence", 0.5)),
        "slots": result.get("slots", {}) or {},
        "extra": result.get("extra", {}) or {},
        "via_llm": True,
    }


VALID_INTENTS = {
    "health_record", "health_query", "service_booking", "order_query",
    "reminder_create", "family_manage", "safety_alert", "sos",
    "support_question", "chitchat", "unknown",
}


# ============ 本地规则降级分类器 ============
_RULES = [
    ("sos", ["救命", "救救我", "快点来", "摔倒", "摔了", "叫救护车", "SOS", "紧急求助", "快来救命"]),
    ("safety_alert", ["诈骗", "转账", "汇款", "验证码", "安全账户", "养老补贴", "退款", "中奖", "骗子"]),
    ("health_record", ["记", "记录", "帮我记", "血压是", "血糖是", "体重是", "体温是", "心率是", "测了"]),
    ("health_query", ["血压多少", "血糖多少", "最近血压", "健康怎么样", "最近身体", "查一下血压", "查一下血糖"]),
    ("reminder_create", ["提醒", "记得", "叫我", "别忘了", "吃药提醒", "复诊提醒", "打卡"]),
    ("service_booking", ["预约", "约个", "帮我叫", "陪诊", "家政", "买药", "取快递", "维修", "打扫", "护工", "保洁"]),
    ("order_query", ["订单", "我的单子", "约的", "查到哪了", "服务进度", "什么时候来"]),
    ("family_manage", ["绑定", "加孩子", "子女", "儿子", "女儿", "亲情", "家人"]),
    ("support_question", ["怎么用", "怎么操作", "教程", "帮助", "怎么办", "不会用"]),
]

_HEALTH_KEYWORDS = {
    "blood_pressure": ["血压", "高压", "低压"],
    "blood_glucose": ["血糖"],
    "weight": ["体重", "公斤", "斤"],
    "heart_rate": ["心率", "心跳"],
    "temperature": ["体温", "发烧", "发热"],
}

# 健康"报告异常"表述词：用户说"XX高/低"是在报告身体异常，应及时提醒
_HEALTH_ABNORMAL_WORDS = ["高", "低", "偏高", "偏低", "不正常", "不舒服", "难受", "头晕", "心慌"]

_SERVICE_KEYWORDS = {
    "陪诊": ["陪诊", "陪看病", "陪去医院"],
    "家政": ["家政", "保洁", "打扫", "收拾", "做饭", "小时工"],
    "买药": ["买药", "代买药", "送药"],
    "取快递": ["取快递", "代取", "拿快递", "快递"],
    "维修": ["维修", "修", "水管", "电工", "灯泡", "上门修"],
}


def _fallback_classify(text: str) -> dict:
    import re
    slots = {}

    # 前置：先抽健康类型
    health_type = ""
    for rtype, kws in _HEALTH_KEYWORDS.items():
        if any(k in text for k in kws):
            health_type = rtype
            break
    if health_type:
        slots["health_type"] = health_type

    # 抽数值文本（健康记录用）
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if nums:
        slots["value_text"] = text

    # 关键修复：健康类型 + 异常词（如"血糖高""血压高"）→ 判定为用户报告异常，及时提醒
    has_abnormal = any(w in text for w in _HEALTH_ABNORMAL_WORDS)
    intent = "unknown"
    if health_type or (has_abnormal and ("血压" in text or "血糖" in text or "高" in text or "低" in text)):
        # 用户提及身体指标异常
        intent = "health_record"

    if intent == "unknown":
        best = 0.0
        for it, keywords in _RULES:
            hits = sum(1 for k in keywords if k in text)
            if hits > best:
                best = hits
                intent = it
        if best == 0:
            intent = "support_question"

    # 服务类型
    for stype, kws in _SERVICE_KEYWORDS.items():
        if any(k in text for k in kws):
            slots["service_type"] = stype
            break
    # 时间文本
    if any(k in text for k in ("明天", "后天", "今天", "上午", "下午", "晚上", "点")):
        slots["time_text"] = text

    return {
        "intent": intent,
        "confidence": 0.6 if intent != "support_question" else 0.1,
        "slots": slots,
        "extra": {},
        "via_llm": False,
    }


async def classify(text: str) -> dict:
    """统一入口：优先 LLM，降级规则。健康报告异常场景优先用规则兜底，避免漏提醒。"""
    from ai.llm.provider import llm_available
    fb = _fallback_classify(text)
    if llm_available():
        result = await classify_with_llm(text)
        # LLM 返回 unknown 但本地规则能匹配时，以本地规则兜底
        if result.get("intent") == "unknown":
            if fb["intent"] != "support_question" or fb["confidence"] >= 0.5:
                return fb
        # 关键：用户报告健康异常（"血糖高/血压高"）时，规则判定为 health_record 优先，绝不漏提醒
        if fb["intent"] == "health_record" and _has_health_abnormal(text):
            return fb
        return result
    return fb


def _has_health_abnormal(text: str) -> bool:
    """判断文本是否在报告健康异常（含健康类型 + 高/低等异常词，或无具体数值但有异常表述）。"""
    has_abnormal = any(w in text for w in _HEALTH_ABNORMAL_WORDS)
    has_health = any(any(k in text for k in kws) for kws in _HEALTH_KEYWORDS.values())
    return has_abnormal and has_health

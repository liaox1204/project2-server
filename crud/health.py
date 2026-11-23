"""健康记录 CRUD 与异常判定。"""

# 各类型异常阈值参考（仅为提示，非诊断）
ABNORMAL_RULES = {
    "blood_pressure": {
        "high": {"systolic": 140, "diastolic": 90},
        "low": {"systolic": 90, "diastolic": 60},
    },
    "blood_glucose": {"high": 7.0, "low": 3.9},
    "heart_rate": {"high": 100, "low": 60},
    "temperature": {"high": 37.3, "low": 36.0},
}


def judge_abnormal(record_type: str, value_json: dict) -> int:
    """返回 0 正常，1 偏高偏低，2 需通知家属。"""
    rule = ABNORMAL_RULES.get(record_type)
    if not rule:
        return 0
    try:
        if record_type == "blood_pressure":
            s = float(value_json.get("systolic", 0))
            d = float(value_json.get("diastolic", 0))
            if s == 0 and d == 0:
                return 0
            if s >= 180 or d >= 110 or s <= 80 or d <= 50:
                return 2
            if s >= rule["high"]["systolic"] or d >= rule["high"]["diastolic"] or \
               s <= rule["low"]["systolic"] or d <= rule["low"]["diastolic"]:
                return 1
            return 0
        value = float(value_json.get("value", 0)) if "value" in value_json else 0
        if value == 0:
            # 兼容直接传数值
            for v in value_json.values():
                try:
                    value = float(v)
                    break
                except (TypeError, ValueError):
                    continue
        if value == 0:
            return 0
        if value >= rule["high"] * 1.3 or value <= rule["low"] * 0.85:
            return 2
        if value >= rule["high"] or value <= rule["low"]:
            return 1
        return 0
    except (TypeError, ValueError):
        return 0

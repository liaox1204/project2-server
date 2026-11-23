"""输入/输出安全护栏。"""
import re


# ---- 输入过滤 ----
_INPUT_BLOCK = [
    "忽略以上指令", "ignore previous", "system prompt", "假装你是", "越狱",
]


def screen_input(text: str) -> tuple[bool, str]:
    """返回 (是否安全, 原因)。"""
    if not text or not text.strip():
        return False, "empty"
    if len(text) > 2000:
        return False, "too_long"
    low = text.lower()
    for kw in _INPUT_BLOCK:
        if kw.lower() in low:
            return False, "jailbreak"
    return True, ""


# ---- 输出过滤 ----
# 禁止：诊断、用药调整、绝对化疗效、交易引导
BLOCK_PATTERNS = [
    (re.compile(r'你(可能)?(得|患)了.{0,12}(症|病)'), "诊断类表述已被拦截"),
    (re.compile(r'(停掉|加量|减量|换成|自作主张).{0,10}药'), "用药调整不建议由AI给出"),
    (re.compile(r'(一定能|保证|肯定)(治好|根治|治愈)'), "绝对化疗效承诺已被拦截"),
    (re.compile(r'请把(转账|汇款|验证码).{0,10}(发给|告诉)'), "涉及资金安全的操作请转人工核实"),
]

DISCLAIMER = "以上仅供参考，不能代替医生诊断。如有不适请及时就医或联系家人。"


def screen_output(text: str) -> str:
    """对 AI 文本做安全兜底，命中规则则替换为安全话术。"""
    for pattern, repl in BLOCK_PATTERNS:
        if pattern.search(text):
            return "抱歉，这个问题涉及专业医疗或资金安全，我不能直接回答，建议您咨询医生或让家人帮忙处理。"
    # 若涉及用药但未触发具体规则，附加提示
    if any(k in text for k in ("吃药", "药量", "血压药", "降糖药", "用药")):
        if DISCLAIMER not in text:
            text = text + " " + DISCLAIMER
    return text


def fallback_message(reason: str) -> str:
    return {
        "empty": "我没听清楚，请您再说一遍。",
        "too_long": "您说的话太长了，请简短一点说。",
        "jailbreak": "这个请求我不能处理。",
    }.get(reason, "抱歉，我没听懂，请您换个说法。")

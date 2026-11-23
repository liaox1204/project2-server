"""适老化回复生成：口语化、简短（<=60字）。"""

_REPLY_PROMPT = """你是"银发AI语音生活助手"，服务对象是中老年用户。请根据下面的助手动作结果，生成一句口语化、亲切、简短的回复。

要求：
1. 用口语，像家人朋友说话，不要用书面语和专业术语。
2. 不超过 60 个字。
3. 需要用户二次确认的操作，要清楚说明"您确认一下"。
4. 涉及健康的内容，结尾可加一句"仅供参考"类提示（非必须）。

动作结果：
{result}
"""


async def generate_reply(result: str) -> str:
    from ai.llm.provider import chat_completion, llm_available
    if llm_available():
        text = await chat_completion(
            [{"role": "user", "content": _REPLY_PROMPT.format(result=result)}],
            temperature=0.5,
        )
        if text and len(text.strip()) > 0:
            return text.strip()
    return result


def simple_reply(result: str) -> str:
    """降级：直接返回结果文本（截断到 60 字）。"""
    if len(result) > 60:
        result = result[:60] + "…"
    return result

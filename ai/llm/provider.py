"""LLM Provider：OpenAI 兼容接口适配（DeepSeek/通义/智谱/月之暗面等）。"""
import json
from typing import Optional

from config.settings import settings


def llm_available() -> bool:
    return settings.llm_configured


def _get_chat_model(model: Optional[str] = None, timeout: Optional[float] = None, temperature: float = 0.3):
    """返回 OpenAI 兼容的 ChatOpenAI 实例（懒加载，避免未配置时导入失败）。"""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model or settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=timeout or settings.LLM_TIMEOUT,
        temperature=temperature,
    )


async def chat_completion(messages: list, json_mode: bool = False, model: Optional[str] = None,
                          temperature: float = 0.3) -> str:
    """调用 LLM 返回文本。json_mode=True 时要求模型返回 JSON 字符串，失败返回空。"""
    try:
        llm = _get_chat_model(model=model, temperature=temperature)
        if json_mode:
            # 通过 response_format 请求 JSON（部分兼容服务支持）
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=model or settings.LLM_MODEL,
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                    timeout=settings.LLM_TIMEOUT,
                    temperature=temperature,
                    model_kwargs={"response_format": {"type": "json_object"}},
                )
            except Exception:
                llm = _get_chat_model(model=model, temperature=temperature)
        resp = await llm.ainvoke(messages)
        return resp.content if hasattr(resp, "content") else str(resp)
    except Exception:
        return ""


async def chat_json(messages: list, model: Optional[str] = None) -> Optional[dict]:
    """调用 LLM 并解析 JSON，失败返回 None。"""
    text = await chat_completion(messages, json_mode=True, model=model, temperature=0.1)
    if not text:
        return None
    try:
        return json.loads(_extract_json(text))
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json(text: str) -> str:
    """从文本中提取 JSON 片段。"""
    text = text.strip()
    if text.startswith("```"):
        # 去掉 markdown 代码块
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


# ============ 流式输出 ============
async def chat_stream(messages: list, model: Optional[str] = None, temperature: float = 0.5):
    """流式调用 LLM，逐块 yield 文本增量。失败时 yield 空（外层可降级）。"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=settings.LLM_TIMEOUT,
    )
    try:
        stream = await client.chat.completions.create(
            model=model or settings.LLM_MODEL,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception:
        # 流式失败：让调用方降级到本地分块模拟
        return


# ============ ASR 语音转文字 ============
async def transcribe_audio(audio_base64: str, audio_format: str = "wav") -> Optional[str]:
    """OpenAI 兼容 audio/transcriptions 接口：把 base64 音频转成文字。失败返回 None。

    audio_format: wav/webm/mp3/m4a/ogg 等，用于给接口正确的文件扩展名。
    """
    import base64 as b64
    import io

    from openai import AsyncOpenAI

    try:
        audio_bytes = b64.b64decode(audio_base64)
    except Exception:
        return None

    # 规范化扩展名
    fmt = (audio_format or "wav").lower().lstrip(".")
    if fmt not in ("wav", "webm", "mp3", "m4a", "ogg", "flac", "mp4", "aac"):
        fmt = "wav"

    client = AsyncOpenAI(
        api_key=settings.asr_api_key,
        base_url=settings.asr_base_url,
        timeout=settings.LLM_TIMEOUT,
    )
    try:
        resp = await client.audio.transcriptions.create(
            model=settings.ASR_MODEL,
            file=(f"voice.{fmt}", io.BytesIO(audio_bytes)),
        )
        text = getattr(resp, "text", "") or ""
        return text.strip() or None
    except Exception:
        return None

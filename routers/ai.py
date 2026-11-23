"""AI 助手路由（核心入口）。"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.Stu import get_database
from config.settings import settings
from core.response import ok, BizError
from core.deps import get_current_user
from ai.agent import run_agent, run_agent_stream, confirm_action
from ai.guard import screen_input, fallback_message
from models.models import User, UserMemory
from schemas.news import VoiceReq, ChatReq, ConfirmReq

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/asr")
async def asr(req: VoiceReq, user: User = Depends(get_current_user)):
    """纯语音转文字：只做 ASR，不执行 AI 回复。前端拿到文字后可填入输入框再发送。"""
    if not req.audio_base64:
        raise BizError(10001, "请提供语音 audio_base64")
    if not settings.asr_configured:
        raise BizError(70001, "语音识别服务尚未配置，请在 .env 中填写 ASR 相关配置")
    from ai.llm.provider import transcribe_audio
    text = await transcribe_audio(req.audio_base64, req.audio_format)
    if not text:
        raise BizError(70001, "语音识别失败，请重试或改用文字输入")
    return ok({"text": text}, "识别成功")


@router.post("/voice")
async def voice(req: VoiceReq, user: User = Depends(get_current_user),
                db: AsyncSession = Depends(get_database)):
    """语音助手统一入口：支持文字，或 base64 音频（走 ASR 转文字）。"""
    text = (req.text or "").strip()

    # 纯文字输入
    if text:
        result = await run_agent(db, user, text, req.session_id)
        return ok(result)

    # 音频输入：走 ASR
    if req.audio_base64:
        if not settings.asr_configured:
            return ok({"reply": "语音识别服务尚未配置，请在 .env 中填写 ASR 相关配置，或改用文字输入。",
                       "need_confirm": False, "asr_text": ""})
        from ai.llm.provider import transcribe_audio
        asr_text = await transcribe_audio(req.audio_base64, req.audio_format)
        if not asr_text:
            raise BizError(70001, "语音识别失败，请重试或改用文字输入")
        result = await run_agent(db, user, asr_text, req.session_id)
        result["asr_text"] = asr_text
        return ok(result)

    raise BizError(10001, "请输入文字或提供语音")


@router.post("/chat")
async def chat(req: ChatReq, user: User = Depends(get_current_user),
               db: AsyncSession = Depends(get_database)):
    result = await run_agent(db, user, req.text, req.session_id)
    return ok(result)


@router.post("/chat/stream")
async def chat_stream(req: ChatReq, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_database)):
    """流式对话：SSE 逐块返回。帧格式 = JSON 的 {type: meta|delta|done, ...}"""
    text = (req.text or "").strip()
    if not text:
        raise BizError(10001, "请输入内容")

    async def event_stream():
        try:
            async for frame in run_agent_stream(db, user, text, req.session_id):
                yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
        finally:
            pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/voice/stream")
async def voice_stream(req: VoiceReq, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_database)):
    """语音 + 流式回复：音频先 ASR 转文字，再流式返回回复。"""
    text = (req.text or "").strip()

    if not text and req.audio_base64:
        if not settings.asr_configured:
            raise BizError(70001, "语音识别服务尚未配置，请改用文字输入")
        from ai.llm.provider import transcribe_audio
        text = await transcribe_audio(req.audio_base64, req.audio_format)
        if not text:
            raise BizError(70001, "语音识别失败，请重试或改用文字输入")

    if not text:
        raise BizError(10001, "请输入文字或提供语音")

    async def event_stream():
        # 先发一条 ASR 识别结果，便于前端展示
        yield f"data: {json.dumps({'type': 'asr', 'text': text}, ensure_ascii=False)}\n\n"
        async for frame in run_agent_stream(db, user, text, req.session_id):
            yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/confirm")
async def confirm(req: ConfirmReq, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_database)):
    result = await confirm_action(db, user, req.session_id, req.action_id, req.confirmed)
    return ok(result)


@router.get("/memories")
async def memories(user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_database)):
    res = await db.execute(
        select(UserMemory).where(UserMemory.user_id == user.id, UserMemory.visible == 1)
    )
    mems = res.scalars().all()
    items = [{"id": m.id, "memory_type": m.memory_type, "key_name": m.key_name,
              "content": m.content} for m in mems]
    return ok(items)


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    mem = await db.get(UserMemory, memory_id)
    if mem is None or mem.user_id != user.id:
        from core.response import BizError
        raise BizError(10005)
    await db.delete(mem)
    await db.commit()
    return ok(None, "已删除该条记忆")

"""应用配置：从环境变量（或 .env 文件）读取，提供默认值。"""
import os
from pathlib import Path
from typing import List

# 自动加载项目根目录的 .env 文件（若存在）
try:
    from dotenv import load_dotenv
    # 项目根目录 = config 的上一级
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except Exception:
    pass


class Settings:
    # ---- 安全 ----
    SECRET_KEY: str = os.getenv("SECRET_KEY", "silver-ai-voice-assistant-dev-secret-key-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120   # access 2h
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30      # refresh 30d

    # ---- LLM（OpenAI 兼容接口，可配 DeepSeek/通义/智谱/月之暗面等）----
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "15"))
    # 意图识别小模型（可复用同一模型）
    LLM_FAST_MODEL: str = os.getenv("LLM_FAST_MODEL", "")

    # ---- CORS ----
    CORS_ORIGINS: List[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ]

    # ---- ASR（语音转文字，OpenAI 兼容 audio/transcriptions 接口）----
    # 默认指向硅基流动（SiliconFlow）语音识别，与 LLM 可共用同一 Key
    ASR_BASE_URL: str = os.getenv("ASR_BASE_URL", "https://api.siliconflow.com/v1")
    ASR_API_KEY: str = os.getenv("ASR_API_KEY", "")
    ASR_MODEL: str = os.getenv("ASR_MODEL", "FunAudioLLM/SenseVoiceSmall")

    # ---- 业务 ----
    # 高风险订单确认金额阈值（元）
    ORDER_CONFIRM_AMOUNT_THRESHOLD: float = float(os.getenv("ORDER_CONFIRM_AMOUNT_THRESHOLD", "100"))

    @property
    def llm_configured(self) -> bool:
        return bool(self.LLM_API_KEY)

    @property
    def asr_configured(self) -> bool:
        """ASR 是否已配置：有独立 Key，或复用 LLM Key（共用 base_url）。"""
        key = self.ASR_API_KEY or self.LLM_API_KEY
        return bool(key)

    @property
    def asr_base_url(self) -> str:
        return self.ASR_BASE_URL or self.LLM_BASE_URL

    @property
    def asr_api_key(self) -> str:
        return self.ASR_API_KEY or self.LLM_API_KEY


settings = Settings()

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.Stu import async_engine
from config.settings import settings
from core.response import BizError, biz_error_handler
from models.models import Base
from routers import api_router

# 上传目录（头像等）
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await async_engine.dispose()


app = FastAPI(title="Silver AI Voice Assistant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务：/static/uploads/xxx.jpg
app.mount("/static", StaticFiles(directory=str(UPLOAD_DIR)), name="static")

# 统一业务异常处理
app.add_exception_handler(BizError, biz_error_handler)

app.include_router(api_router)


@app.get("/")
async def root():
    return {"message": "银发AI语音生活助手 API", "docs": "/docs"}

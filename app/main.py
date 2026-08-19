"""
FastAPI 入口文件
- 启动 Uvicorn 服务器
- 注册路由
- 启动定时任务调度器
"""
import sys

# 确保 stdout/stderr 使用 UTF-8 编码，避免 emoji 等字符在 Windows 上编码失败
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from app.api.routes import router
from app.core.scheduler import scheduler_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    logger.info("=" * 50)
    logger.info("Sheen 个人 AI 助手启动中...")
    logger.info("=" * 50)

    # 启动定时任务调度器
    scheduler_manager.start()

    yield

    # 关闭调度器
    scheduler_manager.shutdown()
    logger.info("Sheen 已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title="Sheen",
        description="个人 AI 助手",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 注册路由
    app.include_router(router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    from app.core.config import settings

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
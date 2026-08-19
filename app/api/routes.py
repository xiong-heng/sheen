"""
FastAPI 路由注册
"""

from typing import Any, Dict

from fastapi import APIRouter, Request
from loguru import logger

from app.core.agent import agent

# 飞书采用条件导入，避免 lark-oapi EventDispatcher 导入失败导致启动崩溃
try:
    from app.api.webhooks.feishu import feishu_handler
    HAS_FEISHU = True
except Exception:
    feishu_handler = None  # type: ignore
    HAS_FEISHU = False
    logger.warning("飞书模块未加载，跳过飞书 Webhook")

# 钉钉采用条件导入，避免 dingtalk-crypto 编译失败导致启动崩溃
try:
    from app.api.webhooks.dingtalk import dingtalk_handler
    HAS_DINGTALK = True
except Exception:
    dingtalk_handler = None  # type: ignore
    HAS_DINGTALK = False
    logger.warning("钉钉模块未安装（dingtalk-crypto 编译失败），跳过钉钉 Webhook")

router = APIRouter()


@router.get("/")
async def root() -> Dict[str, str]:
    """健康检查"""
    return {"status": "ok", "service": "sheen"}


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """健康检查端点"""
    return {"status": "healthy", "service": "sheen"}


@router.post("/chat")
async def chat(
    request: Dict[str, Any],
) -> Dict[str, Any]:
    """
    直接聊天接口
    请求体: {"message": "你好", "session_id": "xxx"}
    """
    message = request.get("message", "")
    session_id = request.get("session_id", "default")

    if not message:
        return {"error": "message 不能为空"}

    logger.info(f"[API Chat] session={session_id}, message={message[:100]}")

    try:
        reply = await agent.run(
            user_input=message,
            session_id=session_id,
        )
        return {"reply": reply, "session_id": session_id}
    except Exception as e:
        logger.error(f"[API Chat] 处理失败: {e}")
        return {"error": str(e)}


if HAS_FEISHU:
    @router.post("/webhook/feishu")
    async def feishu_webhook(request: Request) -> Dict[str, Any]:
        """飞书 Webhook 回调入口"""
        body = await request.json()
        logger.debug(f"[Webhook Feishu] 收到请求: {str(body)[:200]}")

        try:
            result = await feishu_handler.handle_webhook(body)
            return result
        except Exception as e:
            logger.error(f"[Webhook Feishu] 处理失败: {e}")
            return {}


if HAS_DINGTALK:
    @router.post("/webhook/dingtalk")
    async def dingtalk_webhook(request: Request) -> Dict[str, Any]:
        """钉钉 Webhook 回调入口"""
        body = await request.json()
        headers = dict(request.headers)

        logger.debug(f"[Webhook DingTalk] 收到请求: {str(body)[:200]}")

        try:
            result = await dingtalk_handler.handle_webhook(body, headers)
            return result
        except Exception as e:
            logger.error(f"[Webhook DingTalk] 处理失败: {e}")
            return {"errcode": 500, "errmsg": str(e)}


@router.post("/memory/clear")
async def clear_memory(
    request: Dict[str, str],
) -> Dict[str, str]:
    """清除指定会话的记忆"""
    session_id = request.get("session_id", "default")
    await agent.memory.clear(session_id)
    logger.info(f"[API] 已清除会话记忆: {session_id}")
    return {"status": "ok", "session_id": session_id}
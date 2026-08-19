"""
飞书 Webhook 适配器（纯 HTTP 模式，不依赖 lark-oapi EventDispatcher）
- 仅用 lark-oapi Client 发送消息
- 消息解密和事件处理完全手写
"""

import json
from typing import Any, Dict, Optional

from loguru import logger

from app.core.agent import agent
from app.core.config import settings

# 条件导入 lark-oapi，避免 MemoryError 导致启动崩溃
try:
    from lark_oapi import Client
    from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
    HAS_LARK = True
except Exception:
    HAS_LARK = False
    logger.warning("lark-oapi 导入失败，飞书消息发送功能不可用")


class FeishuHandler:
    """飞书消息处理器（HTTP Webhook 模式）"""

    def __init__(self) -> None:
        self._client: Optional['Client'] = None
        if not HAS_LARK:
            logger.warning("[Feishu] lark-oapi 不可用，飞书功能完全禁用")
            return
        if settings.feishu_app_id and settings.feishu_app_secret:
            self._client = Client.builder() \
                .app_id(settings.feishu_app_id) \
                .app_secret(settings.feishu_app_secret) \
                .build()
            logger.info("[Feishu] 飞书客户端已初始化")
        else:
            logger.warning("[Feishu] 飞书配置不完整，跳过初始化")

    async def _send_message(self, chat_id: str, content: str) -> None:
        """发送飞书消息"""
        if not self._client:
            logger.error("[Feishu] 客户端未初始化")
            return

        try:
            request_body = CreateMessageRequestBody.builder() \
                .receive_id(chat_id) \
                .msg_type("text") \
                .content(json.dumps({"text": content}, ensure_ascii=False)) \
                .build()

            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(request_body) \
                .build()

            response = await self._client.im.v1.message.create(request)
            if response.success():
                logger.debug(f"[Feishu] 消息发送成功: {content[:50]}")
            else:
                logger.error(f"[Feishu] 消息发送失败: {response.msg}")

        except Exception as e:
            logger.error(f"[Feishu] 发送消息异常: {e}")

    async def handle_webhook(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理飞书 Webhook 回调（HTTP 模式）
        - 处理 URL 验证
        - 处理消息事件回调
        """
        # URL 验证
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}

        # 事件回调
        event = body.get("event", {})
        if event.get("type") == "im.message.receive_v1":
            message = event.get("message", {})
            content_raw = message.get("content", "{}")

            try:
                content: Dict[str, Any] = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
            except json.JSONDecodeError:
                content = {"text": content_raw}

            text = content.get("text", "") or content.get("content", "")
            sender = event.get("sender", {})
            user_id = sender.get("sender_id", {}).get("user_id", "unknown")
            chat_id = message.get("chat_id", "")

            logger.info(f"[Feishu Webhook] 收到消息: user={user_id}, text={text[:100]}")

            reply = await agent.run(
                user_input=text,
                session_id=f"feishu_{user_id}",
            )

            await self._send_message(chat_id, reply)

        return {}


# 全局单例
feishu_handler = FeishuHandler()
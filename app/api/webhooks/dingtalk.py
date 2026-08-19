"""
钉钉事件订阅适配器
- 使用 dingtalk-sdk 仅做消息解密
- 解密后提取 text 和 user_id，调用 core.agent.run 获得回复
- 再调用钉钉 API 发送消息
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional

import httpx
from loguru import logger

from app.core.agent import agent
from app.core.config import settings

# 条件导入 dingtalk-crypto，避免编译失败导致崩溃
try:
    from dingtalk_crypto import DingTalkCrypto
    HAS_DINGTALK_CRYPTO = True
except Exception:
    HAS_DINGTALK_CRYPTO = False
    logger.warning("dingtalk-crypto 导入失败，钉钉加解密功能不可用")


class DingTalkHandler:
    """钉钉消息处理器"""

    def __init__(self) -> None:
        self._crypto: Optional[DingTalkCrypto] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._access_token: str = ""
        self._token_expires_at: float = 0.0
        self._init_crypto()

    def _init_crypto(self) -> None:
        """初始化钉钉加解密工具"""
        if not HAS_DINGTALK_CRYPTO:
            logger.warning("[DingTalk] dingtalk-crypto 不可用，钉钉加解密功能禁用")
            return
        if not settings.dingtalk_aes_key or not settings.dingtalk_token:
            logger.warning("[DingTalk] 钉钉配置不完整，跳过初始化")
            return

        self._crypto = DingTalkCrypto(
            settings.dingtalk_token,
            settings.dingtalk_aes_key,
            settings.dingtalk_app_key or "",
        )
        logger.info("[DingTalk] 钉钉加解密已初始化")

    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _get_access_token(self) -> str:
        """获取钉钉 access_token"""
        if (
            self._access_token
            and time.time() < self._token_expires_at
        ):
            return self._access_token

        if not settings.dingtalk_app_key or not settings.dingtalk_app_secret:
            logger.error("[DingTalk] 缺少 app_key 或 app_secret")
            return ""

        url = "https://oapi.dingtalk.com/gettoken"
        params = {
            "appkey": settings.dingtalk_app_key,
            "appsecret": settings.dingtalk_app_secret,
        }

        try:
            response = await self.http_client.get(url, params=params)
            data = response.json()
            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 7200) - 60
                return self._access_token
            else:
                logger.error(f"[DingTalk] 获取 token 失败: {data}")
                return ""
        except Exception as e:
            logger.error(f"[DingTalk] 获取 token 异常: {e}")
            return ""

    async def _send_message(self, user_id: str, content: str) -> None:
        """发送钉钉消息"""
        token = await self._get_access_token()
        if not token:
            return

        url = "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2"
        params = {"access_token": token}

        body = {
            "agent_id": settings.dingtalk_app_key,
            "userid_list": user_id,
            "msg": {
                "msgtype": "text",
                "text": {"content": content},
            },
        }

        try:
            response = await self.http_client.post(url, params=params, json=body)
            data = response.json()
            if data.get("errcode") == 0:
                logger.debug(f"[DingTalk] 消息发送成功: {content[:50]}")
            else:
                logger.error(f"[DingTalk] 消息发送失败: {data}")
        except Exception as e:
            logger.error(f"[DingTalk] 发送消息异常: {e}")

    async def handle_webhook(
        self, body: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        处理钉钉 Webhook 回调
        1. 解密消息
        2. 提取文本和用户信息
        3. 调用 Agent 处理
        4. 发送回复
        """
        if not self._crypto:
            logger.error("[DingTalk] 加解密未初始化")
            return {"errcode": 500, "errmsg": "crypto not initialized"}

        try:
            # 从 headers 获取加解密参数
            signature = headers.get("signature", "")
            timestamp = headers.get("timestamp", "")
            nonce = headers.get("nonce", "")

            # 解密消息
            encrypt = body.get("encrypt", "")
            decrypt_msg = self._crypto.decrypt(encrypt, signature, timestamp, nonce)
            msg_data: Dict[str, Any] = json.loads(decrypt_msg)

            logger.info(f"[DingTalk] 收到消息: {json.dumps(msg_data, ensure_ascii=False)[:200]}")

            # 解析消息内容
            text = ""
            user_id = msg_data.get("senderId", "unknown")
            conversation_type = msg_data.get("conversationType", "")

            if conversation_type == "1":
                # 单聊
                text = msg_data.get("text", {}).get("content", "")
            elif conversation_type == "2":
                # 群聊
                text = msg_data.get("text", {}).get("content", "")

            if not text:
                logger.info("[DingTalk] 忽略非文本消息")
                return {"errcode": 0, "errmsg": "ok"}

            # 去掉 @机器人前缀
            if text.startswith("@"):
                text = text.split(" ", 1)[-1] if " " in text else ""

            # 调用 Agent 处理
            reply = await agent.run(
                user_input=text,
                session_id=f"dingtalk_{user_id}",
            )

            # 发送回复
            await self._send_message(user_id, reply)

        except Exception as e:
            logger.error(f"[DingTalk] 处理消息失败: {e}")

        return {"errcode": 0, "errmsg": "ok"}


# 全局单例
dingtalk_handler = DingTalkHandler()
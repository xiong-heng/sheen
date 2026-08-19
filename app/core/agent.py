"""
核心大脑：手写 ReAct 循环
- 调用 OpenAI SDK 处理 tool_calls
- 通过 ToolRegistry 获取工具 Schema
- 通过 Executor 统一执行工具
- 禁止使用 LangChain 或任何 Agent 框架
"""

import json
from typing import Any, Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.executor import execute_tool
from app.core.memory import DualMemory
from app.core.tool_registry import get_tool_registry


class PromptBuilder:
    """构建 System Prompt"""

    SYSTEM_PROMPT_TEMPLATE = """你是一个智能助手 Sheen，由用户个人打造。

你拥有以下工具可供调用：

{skills_description}

当用户请求获取实时信息（新闻、天气、百科、最新动态等）时，必须调用 `search_web` 工具。
当用户请求读取 Excel 文件时，必须调用 `read_excel_data` 工具。
不允许拒绝调用这些工具，即使你认为它们可能不可用，也请先调用再根据返回结果回复用户。

如果任务需要多个步骤，你可以依次调用多个工具，一个工具的输出可以作为另一个工具的输入。
请始终使用中文回复，除非用户使用其他语言。"""

    @staticmethod
    def build(tools: List[Any]) -> str:
        """构建 system prompt"""
        lines = []
        for tool in tools:
            params_desc = json.dumps(
                tool.get("parameters", {}), ensure_ascii=False, indent=2
            )
            lines.append(
                f"### {tool.get('name', 'unknown')}\n"
                f"描述：{tool.get('description', '')}\n"
                f"参数：\n```json\n{params_desc}\n```\n"
            )

        skills_description = "\n".join(lines) if lines else "暂无可用工具。"
        return PromptBuilder.SYSTEM_PROMPT_TEMPLATE.format(
            skills_description=skills_description
        )


class Agent:
    """手写 Agent 大脑，实现 ReAct 循环"""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.openai_model
        self.memory = DualMemory()
        self._tool_registry = get_tool_registry()
        self.max_iterations = settings.agent_max_iterations

        logger.info(
            f"[Agent] 初始化完成 | 模型: {self.model}"
            f" | 最大迭代: {self.max_iterations}"
            f" | 工具数: {len(self._tool_registry.list_tools())}"
        )

    def _build_tools(self) -> List[Dict[str, Any]]:
        """构建 OpenAI function calling 的工具列表"""
        return self._tool_registry.list_schemas()

    def _build_system_prompt(self) -> str:
        """构建 system prompt"""
        tools = self._tool_registry.list_tools()
        return PromptBuilder.build(tools)

    async def run(
        self,
        user_input: str,
        session_id: str = "default",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        主入口：ReAct 循环

        流程:
        1. 保存用户消息到记忆
        2. 构建 messages（含 system prompt + 历史）
        3. 调用 OpenAI API (tool_choice="auto")
        4. 若返回 tool_calls → 执行工具 → 结果追加回 messages → 再次调用
        5. 返回最终答案
        """
        logger.info(f"[Agent] 收到输入: session={session_id}, input={user_input[:100]}")

        # 保存用户消息
        await self.memory.add_message(session_id, "user", user_input)

        # 构建消息列表
        messages = await self.memory.build_messages(
            session_id, self._build_system_prompt()
        )
        if history:
            messages.extend(history)

        # 确保最后一条是 user 消息
        if not messages or messages[-1].get("role") != "user":
            messages.append({"role": "user", "content": user_input})
        elif messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})

        tools = self._build_tools()

        # ReAct 循环
        for iteration in range(self.max_iterations):
            logger.debug(f"[Agent] ReAct 迭代 {iteration + 1}/{self.max_iterations}")

            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                )
            except Exception as e:
                logger.error(f"[Agent] OpenAI API 调用失败: {e}")
                return f"抱歉，我暂时无法处理您的请求（API调用失败: {str(e)}）"

            choice = response.choices[0]
            message = choice.message

            # 记录 assistant 消息
            if message.content:
                messages.append({"role": "assistant", "content": message.content})

            # 没有 tool_calls → 直接返回
            if not message.tool_calls:
                final_answer = message.content or ""
                logger.info(
                    f"[Agent Dec] 第 {iteration+1} 轮 | 工具: 否 | 回复: {final_answer[:100]}"
                )

                # 存储回复（非错误回复）
                from app.core.memory_strategy import (
                    is_error_response,
                    store_important_facts,
                )

                if not is_error_response(final_answer):
                    await self.memory.add_message(
                        session_id, "assistant", final_answer
                    )
                    await store_important_facts(
                        self.memory, session_id, user_input, final_answer
                    )
                else:
                    logger.info(
                        f"[Agent] 跳过存储失败回复: {final_answer[:60]}"
                    )

                return final_answer

            # 处理 tool_calls
            assistant_tool_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
            messages.append(assistant_tool_msg)

            await self.memory.add_message(
                session_id,
                "assistant",
                message.content or "",
                tool_calls=json.dumps(
                    assistant_tool_msg["tool_calls"], ensure_ascii=False
                ),
            )

            # 执行每个工具调用
            for tool_call in message.tool_calls:
                skill_name = tool_call.function.name
                arguments = tool_call.function.arguments
                logger.info(
                    f"[Agent Dec] 第 {iteration+1} 轮 | 工具: {skill_name} | 参数: {arguments[:200]}"
                )

                result = await execute_tool(skill_name, arguments)

                tool_msg: Dict[str, str] = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
                messages.append(tool_msg)

                await self.memory.add_message(
                    session_id, "tool", result, tool_call_id=tool_call.id
                )

        # 达到最大迭代次数
        fallback = "抱歉，处理您的请求时达到了最大迭代次数，请稍后重试。"
        logger.warning(f"[Agent] 达到最大迭代次数")
        return fallback


# 全局单例
agent = Agent()
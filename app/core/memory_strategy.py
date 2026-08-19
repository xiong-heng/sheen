"""记忆存储策略：决定哪些对话内容需要存入长期记忆"""

from loguru import logger


def is_error_response(text: str) -> bool:
    """判断回复是否包含错误信息，避免存储失败的尝试"""
    error_patterns = [
        "抱歉，我目前还不具备",
        "抱歉，我暂时无法处理",
        "抱歉，处理您的请求时达到了最大迭代次数",
    ]
    return any(pattern in text for pattern in error_patterns)


async def store_important_facts(
    memory: object, session_id: str, user_input: str, response: str
) -> None:
    """
    将重要的对话事实存储到长期记忆。
    策略：当用户输入或模型回复较长时，认为对话包含重要信息。

    Args:
        memory: DualMemory 实例
        session_id: 会话 ID
        user_input: 用户输入
        response: 模型回复
    """
    if len(user_input) > 20 or len(response) > 50:
        fact = f"用户问: {user_input[:100]} | 我回答: {response[:200]}"
        # 只有在 memory 有 store_fact 方法时才调用
        if hasattr(memory, "store_fact") and callable(getattr(memory, "store_fact")):
            await memory.store_fact(session_id, fact)
            logger.debug(f"[MemoryStrategy] 已存储事实: {fact[:60]}...")
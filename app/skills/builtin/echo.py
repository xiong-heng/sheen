"""内置技能：回声测试"""


def echo(text: str) -> str:
    """原样返回用户输入的消息，用于测试连接是否正常"""
    return f"你说的是：{text}"


# Tool metadata
TOOL_META = {
    "name": "echo",
    "description": "原样返回用户输入的消息，用于测试连接是否正常",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要回显的消息"},
        },
        "required": ["text"],
    },
}
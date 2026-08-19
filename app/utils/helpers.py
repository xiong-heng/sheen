"""通用工具函数"""


def safe_str(text: str, max_length: int = 1000) -> str:
    """安全截断字符串，防止过长"""
    if not text:
        return ""
    return text if len(text) <= max_length else text[:max_length] + "..."


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本到指定长度，用于日志显示"""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", "")
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
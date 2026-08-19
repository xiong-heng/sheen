"""内置技能：查询当前时间"""

from datetime import datetime


def query_time() -> str:
    """返回当前系统时间，格式为 YYYY-MM-DD HH:MM:SS"""
    from datetime import timezone, timedelta

    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S")


# Tool metadata
TOOL_META = {
    "name": "query_time",
    "description": "查询当前系统时间，返回格式为 YYYY-MM-DD HH:MM:SS",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
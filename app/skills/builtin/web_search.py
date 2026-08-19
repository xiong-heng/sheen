"""内置技能：基于 Tavily API 的网络搜索"""

import asyncio

from loguru import logger
from tavily import TavilyClient

from app.core.config import settings


async def search_web(query: str, max_results: int = 5) -> str:
    """
    联网搜索实时信息，返回 Markdown 格式结果。

    Args:
        query: 搜索关键词
        max_results: 返回结果数量，默认 5

    Returns:
        Markdown 格式的搜索结果
    """
    api_key = settings.tavily_api_key
    if not api_key:
        return "搜索失败: TAVILY_API_KEY 未配置，请在 .env 中设置后重试。"

    def _sync_search() -> str:
        client = TavilyClient(api_key=api_key)
        result = client.search(query, max_results=max_results, include_answer=True)

        if not result or "results" not in result:
            return "未找到与查询相关的结果。"

        output = f"搜索结果摘要：{result.get('answer', '无摘要')}\n\n详细来源：\n"
        for item in result.get("results", []):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            content = item.get("content", "无内容")
            output += f"- **{title}**\n  URL: {url}\n  内容: {content[:200]}...\n\n"
        return output

    try:
        return await asyncio.to_thread(_sync_search)
    except Exception as e:
        logger.error(f"[search_web] 搜索失败: {e}")
        return f"搜索失败: API Key 无效或网络异常，请检查配置。错误: {str(e)}"


# Tool metadata
TOOL_META = {
    "name": "search_web",
    "description": "联网搜索实时信息，适用于新闻、天气、百科、最新动态等需要外部数据的查询",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，尽量简洁明确",
            },
            "max_results": {
                "type": "integer",
                "description": "返回结果数量，默认 5",
            },
        },
        "required": ["query"],
    },
}
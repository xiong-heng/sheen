"""
工具执行器测试
"""

import pytest

from app.core.executor import execute_tool
from app.core.tool_registry import get_tool_registry


async def test_tool_registry_has_tools():
    """测试 ToolRegistry 能加载到工具"""
    registry = get_tool_registry()
    tools = registry.list_tools()
    assert len(tools) > 0
    schemas = registry.list_schemas()
    assert len(schemas) == len(tools)


async def test_execute_echo():
    """测试执行 echo 内置工具"""
    result = await execute_tool("echo", '{"text": "hello"}')
    assert "hello" in result


async def test_execute_query_time():
    """测试执行 query_time 内置工具"""
    result = await execute_tool("query_time", "{}")
    assert isinstance(result, str)
    assert len(result) > 0

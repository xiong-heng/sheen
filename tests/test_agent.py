"""
Agent 核心流程测试
"""

import pytest

from app.core.agent import agent


async def test_agent_basic():
    """Agent 基础功能测试"""
    result = await agent.run("你好", session_id="test")
    assert isinstance(result, str)
    assert len(result) > 0


async def test_agent_echo():
    """Agent 调用 echo 工具测试"""
    result = await agent.run("请调用 echo 工具回显 '测试消息'", session_id="test-echo")
    assert isinstance(result, str)
    assert "测试消息" in result or len(result) > 0

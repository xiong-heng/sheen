"""
各技能独立测试
"""

import pytest

from app.skills.builtin.echo import echo
from app.skills.builtin.query_time import query_time


def test_echo():
    """echo 工具测试"""
    result = echo(text="test")
    assert "test" in result


def test_query_time():
    """query_time 工具测试"""
    result = query_time()
    assert isinstance(result, str)
    assert len(result) > 0

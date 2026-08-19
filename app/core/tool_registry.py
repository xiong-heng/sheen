"""
集中构建所有工具的 JSON Schema。

职责：
1. 扫描 app/skills/builtin/ 下的内置工具，读取 TOOL_META 常量
2. 扫描 app/skills/packages/ 下的技能包，从 SKILL.md 解析元数据
3. 提供 list_schemas() 供 agent 构建 OpenAI function calling 列表
4. 提供 get_tool() 供 executor 查找执行入口
"""

import importlib
import json
import os
import pkgutil
from typing import Any, Dict, List, Optional

from loguru import logger

import app.skills.builtin as builtin_pkg
from app.skills.loader import scan_packages, parse_package_meta

# 内置工具模块路径
BUILTIN_MODULES = [
    "app.skills.builtin.web_search",
    "app.skills.builtin.excel_reader",
    "app.skills.builtin.echo",
    "app.skills.builtin.query_time",
    "app.skills.builtin.file_manager",
]


class ToolRegistry:
    """集中构建和管理所有工具 Schema"""

    def __init__(self) -> None:
        self._builtin_tools: Dict[str, Dict[str, Any]] = {}
        self._package_tools: Dict[str, Dict[str, Any]] = {}
        self._schemas: Optional[List[Dict[str, Any]]] = None
        self._load_builtin_tools()
        self._load_package_tools()

    def _load_builtin_tools(self) -> None:
        """加载内置工具，从 TOOL_META 常量读取"""
        for mod_name in BUILTIN_MODULES:
            try:
                mod = importlib.import_module(mod_name)
                meta = getattr(mod, "TOOL_META", None)
                if meta is None:
                    logger.warning(f"[ToolRegistry] {mod_name} 没有 TOOL_META，跳过")
                    continue
                name = meta["name"]
                self._builtin_tools[name] = {
                    **meta,
                    "type": "builtin",
                    "module": mod_name,
                }
                logger.debug(f"[ToolRegistry] 注册内置工具: {name}")
            except Exception as e:
                logger.warning(f"[ToolRegistry] 加载内置工具 {mod_name} 失败: {e}")

    def _load_package_tools(self) -> None:
        """加载外部技能包，从 SKILL.md 解析"""
        packages = scan_packages()
        for pkg in packages:
            try:
                meta = parse_package_meta(pkg["path"])
                if meta is None:
                    continue
                name = meta["name"]
                self._package_tools[name] = {
                    **meta,
                    "type": "package",
                    "skill_path": pkg["path"],
                    "timeout": meta.get("timeout", 30),
                }
                logger.info(f"[ToolRegistry] 注册技能包: {name}")
            except Exception as e:
                logger.warning(f"[ToolRegistry] 加载技能包 {pkg['name']} 失败: {e}")

    def list_schemas(self) -> List[Dict[str, Any]]:
        """生成 OpenAI function calling 格式的 Tool Schema 列表（带缓存）"""
        if self._schemas is not None:
            return self._schemas

        schemas: List[Dict[str, Any]] = []
        for name, meta in {**self._builtin_tools, **self._package_tools}.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": meta.get("description", ""),
                    "parameters": meta.get("parameters", {}),
                },
            })

        self._schemas = schemas
        logger.info(f"[ToolRegistry] 共生成 {len(schemas)} 个工具 Schema")
        return schemas

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """按名称获取工具元数据"""
        return self._builtin_tools.get(name) or self._package_tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具的元数据列表"""
        return list({**self._builtin_tools, **self._package_tools}.values())


# 全局单例
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局 ToolRegistry 单例"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
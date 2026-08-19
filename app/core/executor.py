"""
统一工具/技能执行器。

职责：
1. 接收 skill_name + arguments
2. 从 ToolRegistry 查找工具元数据
3. 路由到正确的执行入口（内置函数 / 脚本技能包）
4. 返回执行结果
"""

import asyncio
import importlib
import json
import os
import shlex
import time
from typing import Any, Dict, Optional

from loguru import logger

from app.core.tool_registry import get_tool_registry

# 默认脚本执行超时（秒）
DEFAULT_TIMEOUT = 30
# 禁止脚本访问的环境变量黑名单
ENV_BLACKLIST = {"OPENAI_API_KEY", "TAVILY_API_KEY", "FEISHU_APP_SECRET", "DINGTALK_TOKEN"}


async def execute_builtin_tool(meta: Dict[str, Any], args: Dict[str, Any]) -> str:
    """执行内置 Python 工具"""
    module_name = meta.get("module", "")
    method_name = meta.get("name", "")

    try:
        mod = importlib.import_module(module_name)

        # 按名称映射到对应函数
        func_map = {
            "echo": "echo",
            "query_time": "query_time",
            "read_excel_data": "read_excel_data",
            "search_web": "search_web",
            "file_manager": "list_files",
        }
        func_name = func_map.get(method_name)
        if not func_name:
            return f"未找到内置工具的实现: {method_name}"

        func = getattr(mod, func_name, None)
        if func is None:
            return f"未找到函数: {func_name}"

        # 检查是否为异步函数
        if asyncio.iscoroutinefunction(func):
            return await func(**args)
        else:
            return await asyncio.to_thread(func, **args)

    except Exception as e:
        logger.error(f"[Executor] 内置工具 {method_name} 执行失败: {e}")
        return f"执行 {method_name} 时出错: {str(e)}"


async def execute_package_script(meta: Dict[str, Any], args: Dict[str, Any]) -> str:
    """执行外部脚本技能包"""
    skill_path = meta.get("skill_path", "")
    timeout = meta.get("timeout", DEFAULT_TIMEOUT)

    if not skill_path or not os.path.isdir(skill_path):
        return f"技能包路径不存在: {skill_path}"

    scripts_dir = os.path.join(skill_path, "scripts")
    if not os.path.isdir(scripts_dir):
        return f"技能包缺少 scripts/ 目录: {skill_path}"

    # 查找入口脚本
    entry = meta.get("entry", "")
    if entry:
        script_path = os.path.join(scripts_dir, entry)
    else:
        # 默认优先 main.py
        candidates = ["main.py", "run.sh", "run.js"]
        script_path = None
        for c in candidates:
            p = os.path.join(scripts_dir, c)
            if os.path.isfile(p):
                script_path = p
                break
        if script_path is None:
            return f"技能包 {os.path.basename(skill_path)} 中未找到入口脚本"

    # 构建命令
    ext = os.path.splitext(script_path)[1].lower()
    if ext == ".py":
        cmd = ["python", script_path]
    elif ext == ".sh":
        cmd = ["bash", script_path]
    elif ext == ".js":
        cmd = ["node", script_path]
    else:
        return f"不支持的脚本类型: {ext}"

    # 将 args 转为命令行参数
    for key, value in args.items():
        if key == "timeout" or key == "kwargs":
            continue
        cmd.extend([f"--{key}", str(value)])

    # 构建安全环境变量
    safe_env = os.environ.copy()
    for key in ENV_BLACKLIST:
        safe_env.pop(key, None)

    start_time = time.monotonic()
    logger.info(
        f"[Executor] 执行脚本技能: {os.path.basename(skill_path)}"
        f", 超时: {timeout}s, 命令: {' '.join(shlex.quote(str(c)) for c in cmd)}"
    )

    try:
        process = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                cwd=scripts_dir,
                env=safe_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=timeout,
        )

        stdout, stderr = await process.communicate()
        duration = time.monotonic() - start_time
        stdout_str = stdout.decode("utf-8", errors="replace").strip()
        stderr_str = stderr.decode("utf-8", errors="replace").strip()

        if process.returncode == 0:
            logger.info(
                f"[Executor] 脚本技能成功: {os.path.basename(skill_path)}"
                f", 耗时: {duration:.2f}s, 输出长度: {len(stdout_str)}"
            )
            return stdout_str or "执行成功，无输出。"
        else:
            logger.warning(
                f"[Executor] 脚本技能失败: {os.path.basename(skill_path)}"
                f", 返回码: {process.returncode}, stderr: {stderr_str[:200]}"
            )
            return f"执行失败（返回码 {process.returncode}）: {stderr_str or stdout_str}"

    except asyncio.TimeoutError:
        duration = time.monotonic() - start_time
        logger.error(
            f"[Executor] 技能 {os.path.basename(skill_path)} 超时"
            f"（{duration:.2f}s > {timeout}s）"
        )
        return (
            f"技能 {os.path.basename(skill_path)} 执行超时"
            f"（{timeout} 秒），请优化脚本或减少输入数据量。"
        )
    except Exception as e:
        logger.error(f"[Executor] 脚本技能执行异常: {e}")
        return f"执行脚本技能时出错: {str(e)}"


async def execute_tool(skill_name: str, arguments: str) -> str:
    """
    统一工具执行入口。

    Args:
        skill_name: 工具名称
        arguments: JSON 格式的参数

    Returns:
        执行结果字符串
    """
    registry = get_tool_registry()
    meta = registry.get_tool(skill_name)

    if meta is None:
        return f"未找到工具: {skill_name}"

    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as e:
        return f"参数解析失败: {str(e)}"

    tool_type = meta.get("type", "")

    # 日志记录
    logger.info(
        f"[Executor] 执行: {skill_name}"
        f" (类型: {tool_type}, 参数: {json.dumps(args, ensure_ascii=False)[:200]})"
    )
    print(f"[Executor] 执行 {skill_name} | 参数: {json.dumps(args, ensure_ascii=False)[:100]}")

    if tool_type == "builtin":
        return await execute_builtin_tool(meta, args)
    elif tool_type == "package":
        return await execute_package_script(meta, args)
    else:
        return f"未知的工具类型: {tool_type}"
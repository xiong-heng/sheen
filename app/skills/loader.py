"""
扫描 skills/packages/ 目录，识别 SKILL.md 技能包并动态注册。

与旧版 skill_loader.py 的区别：
- 只扫描 packages/ 目录（不再扫描 skills/ 根目录）
- 不再依赖 BaseSkill 类
- 元数据返回格式兼容 ToolRegistry
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from loguru import logger

# 技能包存放目录
PACKAGES_DIR = os.path.join(os.path.dirname(__file__), "packages")


def scan_packages() -> List[Dict[str, Any]]:
    """
    扫描 packages/ 目录，识别含有 SKILL.md 的文件夹。

    Returns:
        技能包信息列表，每项包含 name, path
    """
    packages: List[Dict[str, Any]] = []
    packages_dir = PACKAGES_DIR

    if not os.path.isdir(packages_dir):
        return packages

    for entry in sorted(os.listdir(packages_dir)):
        entry_path = os.path.join(packages_dir, entry)
        skill_md = os.path.join(entry_path, "SKILL.md")
        if os.path.isdir(entry_path) and os.path.isfile(skill_md):
            packages.append({
                "name": entry,
                "path": entry_path,
            })

    if packages:
        names = ", ".join(p["name"] for p in packages)
        logger.info(f"[Loader] 扫描到 {len(packages)} 个技能包: {names}")

    return packages


def parse_package_meta(package_path: str) -> Optional[Dict[str, Any]]:
    """
    解析技能包的 SKILL.md，提取元数据。

    支持 YAML Frontmatter (--- 包裹) 和 Markdown 正文。

    Args:
        package_path: 技能包目录路径

    Returns:
        Dict with name, description, parameters, entry, timeout 等
    """
    skill_md = os.path.join(package_path, "SKILL.md")
    if not os.path.isfile(skill_md):
        logger.warning(f"[Loader] 未找到 SKILL.md: {skill_md}")
        return None

    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"[Loader] 读取 SKILL.md 失败: {e}")
        return None

    meta: Dict[str, Any] = {
        "name": os.path.basename(package_path),
        "description": "",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "entry": "",
        "timeout": 30,
    }

    # 解析 YAML Frontmatter (--- 包裹)
    frontmatter_match = re.match(
        r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL
    )
    if frontmatter_match:
        yaml_text = frontmatter_match.group(1)
        for line in yaml_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 解析 name / description / entry / timeout
            for key in ("name", "description", "entry", "timeout"):
                prefix = f"{key}:"
                if line.startswith(prefix):
                    value = line[len(prefix):].strip().strip('"').strip("'")
                    if key == "timeout":
                        try:
                            meta[key] = int(value)
                        except ValueError:
                            pass
                    else:
                        meta[key] = value

            # 解析 parameters
            if line.startswith("parameters:"):
                # 尝试从 SKILL.md 中提取 JSON 参数块
                param_block = _extract_parameters_block(content)
                if param_block:
                    try:
                        meta["parameters"] = json.loads(param_block)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"[Loader] SKILL.md parameters 解析失败: "
                            f"{os.path.basename(package_path)}"
                        )

    return meta


def _extract_parameters_block(content: str) -> Optional[str]:
    """从 SKILL.md 中提取 parameters 的 JSON 块"""
    # 尝试匹配 ```json ... ``` 块
    json_block = re.search(
        r"```json\s*\n(.*?)\n```", content, re.DOTALL
    )
    if json_block:
        return json_block.group(1).strip()

    # 尝试匹配 ```yaml ... ``` 块
    yaml_block = re.search(
        r"```yaml\s*\n(.*?)\n```", content, re.DOTALL
    )
    if yaml_block:
        # 简单转为 JSON 兼容格式
        return yaml_block.group(1).strip()

    return None
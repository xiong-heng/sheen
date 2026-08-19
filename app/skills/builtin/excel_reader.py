"""内置技能：读取 Excel 文件"""

import json
from typing import Any, Dict, List, Optional

import pandas as pd


def read_excel_data(
    file_path: str, sheet_name: Optional[str] = None, rows: Optional[int] = None
) -> str:
    """
    读取 Excel 文件，返回 JSON 格式数据。

    Args:
        file_path: Excel 文件的绝对路径
        sheet_name: 工作表名称（默认第一个工作表）
        rows: 限制读取的行数（默认全部）

    Returns:
        JSON 字符串
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
        if rows is not None:
            df = df.head(rows)

        # 处理日期格式
        for col in df.select_dtypes(include=["datetime64"]).columns:
            df[col] = df[col].astype(str)

        # 处理 NaN
        df = df.where(pd.notna(df), None)

        data: List[Dict[str, Any]] = df.to_dict(orient="records")
        return json.dumps(data, ensure_ascii=False, indent=2)

    except FileNotFoundError:
        return f"错误：文件未找到 - {file_path}"
    except Exception as e:
        return f"读取 Excel 文件失败: {str(e)}"


# Tool metadata
TOOL_META = {
    "name": "read_excel_data",
    "description": "读取指定路径的 Excel 文件（.xlsx/.xls），返回 JSON 格式的数据，支持指定工作表名称和读取行数",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Excel 文件的绝对路径"},
            "sheet_name": {
                "type": "string",
                "description": "工作表名称，默认为第一个工作表",
            },
            "rows": {
                "type": "integer",
                "description": "读取的行数，默认全部",
            },
        },
        "required": ["file_path"],
    },
}
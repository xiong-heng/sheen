"""内置技能：文件操作（占位 stub）"""


async def list_files(path: str) -> str:
    """列出指定目录下的文件列表"""
    import os

    try:
        if not os.path.isdir(path):
            return f"错误：路径不存在或不是目录 - {path}"
        files = os.listdir(path)
        result = f"目录 {path} 下的文件（{len(files)} 项）：\n"
        for f in sorted(files):
            fp = os.path.join(path, f)
            size = os.path.getsize(fp) if os.path.isfile(fp) else 0
            ftype = "📄" if os.path.isfile(fp) else "📁"
            result += f"  {ftype} {f} ({size} 字节)\n"
        return result
    except Exception as e:
        return f"列出文件失败: {str(e)}"


# Tool metadata
TOOL_META = {
    "name": "file_manager",
    "description": "列出指定目录下的文件列表",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要查看的目录路径",
            },
        },
        "required": ["path"],
    },
}
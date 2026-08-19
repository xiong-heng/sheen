# Sheen — 你的个人 AI 助手
![Sheen](./images/logo.png)
> 你好，我是 Sheen。虽然我有时候会掉线，但我永远不会忘记你的名字——除非你让我帮你清理记忆，那我也只能照办。

---

## 主要功能

- **双层记忆系统**：短期记忆让你聊再多也不串台，长期记忆让 Sheen 能记住你几个月前说过的重要信息。
- **联网搜索**：通过 Tavily API 获取实时新闻、天气、百科等，让 AI 不再断网。
- **Excel 操作**：读取、分析、写入 Excel 文件，甚至能自动填写网页表单（需配合 Playwright）。
- **文件管理**：移动、复制、删除、重命名、分类文件，让你的桌面保持整洁。
- **定时任务**：每天早 8 点自动汇报，你也可以自定义任何时间触发任务。
- **可插拔技能包**：下载社区技能，放进 `app/skills/packages/` 即可使用，无需修改代码。
- **飞书 / 钉钉接入**（可选）：让 Sheen 在办公软件里随叫随到。

---

## 快速上手

### 第一步：安装 Python 环境

确保你的电脑安装了 Python 3.10 或 3.11（推荐 3.11，兼容性最好）。

```bash
python --version
```

### 第二步：下载项目

```bash
git clone https://github.com/xiong-heng/sheen.git
cd sheen
```

如果没有 Git，也可以直接下载 ZIP 压缩包并解压。

### 第三步：创建虚拟环境（强烈推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

激活后，命令行前面会出现 `(venv)` 字样。

### 第四步：安装依赖

```bash
pip install -r requirements.txt

# 如果遇到 playwright 相关错误，额外执行：
playwright install
```

### 第五步：配置环境变量

复制 `.env.example` 为 `.env`：

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

用记事本打开 `.env`，填写以下关键密钥：

| 变量名 | 说明 | 如何获取 |
|--------|------|----------|
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（推荐阿里云百炼或 DeepSeek） | 注册阿里云百炼或 DeepSeek |
| `OPENAI_BASE_URL` | API 地址 | 从服务商控制台复制 |
| `OPENAI_MODEL` | 模型名称（如 `qwen-plus` 或 `deepseek-chat`） | 根据服务商填写 |
| `TAVILY_API_KEY` | 联网搜索密钥（可选，但强烈建议） | 注册 Tavily 免费获取 |

其它变量（飞书、钉钉）可先留空，不影响核心功能。

### 第六步：启动 Sheen

```bash
python -m app.main
```

看到类似下面的日志，就说明启动成功了：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### 第七步：开始聊天

打开浏览器访问 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)，你会看到 Swagger 交互式文档。

找到 `POST /chat` 接口，点击 **Try it out**，输入：

```json
{
  "message": "你好，Sheen！",
  "session_id": "test"
}
```

点击 **Execute**，稍等片刻，就能看到 Sheen 的回复了。

---

## 使用更多功能

### Excel 读取

在聊天中直接说：

> 读取 C:/Users/你的用户名/Desktop/数据.xlsx 的内容

Sheen 会自动调用 `read_excel_data` 技能，返回 JSON 格式的数据。

### 联网搜索

问任何实时问题，比如：

> 北京今天天气怎么样？
> 搜索一下最新的 AI 新闻

Sheen 会调用 `search_web` 工具（需配置 `TAVILY_API_KEY`）。

### 文件管理

你可以让 Sheen：

- 把桌面上的 报告.docx 复制到 文档/备份/ 里
- 重命名 照片.jpg 为 旅行照片.jpg
- 整理 下载 文件夹（按扩展名分类）

### 定时任务

默认每天早上 8 点会执行一次 `daily_report` 任务。你可以修改 `app/cron/daily_report.json` 中的 cron 表达式，或新建其他任务文件。

### 扩展新技能

在 `app/skills/packages/` 下新建一个文件夹，比如 `my_tool`。在里面放一个 `SKILL.md`（告诉 AI 这个技能干什么用）和一个 `scripts/` 文件夹（放可执行脚本）。重启 Sheen，它会自动识别并加载该技能。

你也可以直接下载社区分享的技能包，解压后丢进 `packages/` 目录即可。

---

## 技术栈

- Python 3.10+ / FastAPI / Uvicorn
- OpenAI SDK（兼容阿里云百炼、DeepSeek 等）
- SQLite + sqlite-vec（向量检索）
- Tavily API（联网搜索）
- Playwright（网页自动化）
- APScheduler（定时任务）
- Pandas + openpyxl（Excel 处理）

---

## 许可证

本项目采用 MIT License，你可以任意使用、修改、分发，甚至用于商业项目。唯一要求是保留版权声明。

---

## 贡献与反馈

如果你发现问题，或者有好的功能建议，欢迎提交 Issue 或 Pull Request。也欢迎通过 GitHub Issues 分享你制作的技能包。

> 最后，记住：Sheen 虽然聪明，但不会替你吃饭。照顾好自己，朋友。

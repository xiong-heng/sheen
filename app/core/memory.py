"""
双轨记忆模块（基于 sqlite-vec）：
- 短期记忆：chat_history 表，存储最近 N 条对话
- 长期记忆：vec_memory 表（sqlite-vec 向量索引），RAG 检索
- 所有 SQLite 操作通过 asyncio.to_thread 包装为异步
"""

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
import sqlite_vec

from app.core.config import SQLITE_PATH, settings

# 向量维度（适配 text-embedding-3-small）
VECTOR_DIMS = 1536


def get_db_connection(db_path: Path = SQLITE_PATH) -> sqlite3.Connection:
    """获取 SQLite 连接并自动加载 sqlite-vec 扩展"""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.enable_load_extension(True)

    # 获取 vec0.dll 的绝对路径
    vec_pkg_dir = os.path.dirname(sqlite_vec.__file__)
    dll_path = os.path.join(vec_pkg_dir, "vec0.dll")

    if not os.path.exists(dll_path):
        raise FileNotFoundError(
            f"vec0.dll 未找到，期望路径: {dll_path}\n"
            "请确认 sqlite-vec 已正确安装: pip install sqlite-vec"
        )

    try:
        conn.load_extension(dll_path)
        logger.info(f"sqlite-vec 扩展加载成功 (路径: {dll_path})")
    except Exception as e:
        logger.error(f"加载 sqlite-vec 扩展失败: {e}")
        logger.error(
            "请确保已安装 Microsoft Visual C++ Redistributable: "
            "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        )
        raise

    return conn


def init_memory_db(db_path: Path = SQLITE_PATH) -> None:
    """初始化数据库表结构（同步，启动时调用）"""
    conn = get_db_connection(db_path)
    try:
        # 短期记忆表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tool_calls TEXT,
                tool_call_id TEXT,
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_history_session_ts
            ON chat_history (session_id, timestamp DESC)
        """)

        # 兼容旧数据库：添加新列（如果不存在则忽略）
        for col in ("tool_calls", "tool_call_id"):
            try:
                conn.execute(f"ALTER TABLE chat_history ADD COLUMN {col} TEXT")
            except Exception:
                pass  # 列已存在

        # 长期记忆内容表（存储原始文本和元数据）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)

        # 长期记忆向量表（sqlite-vec 虚拟表，1536 维，余弦距离）
        try:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_memory USING vec0(
                    embedding float[{VECTOR_DIMS}] distance_metric=cosine
                )
            """)
        except Exception as e:
            logger.warning(f"[Memory] vec0 虚拟表可能已存在，尝试忽略: {e}")

        conn.commit()
        logger.info("[Memory] 数据库初始化完成")
    finally:
        conn.close()


# ---- 辅助函数：向量编码 ----

async def _get_embedding(text: str) -> List[float]:
    """获取文本向量（使用 OpenAI embedding API，异步封装）"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    try:
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"[Memory] Embedding API 调用失败，使用模拟向量: {e}")
        # 降级：MD5 哈希模拟 1536 维向量
        import hashlib
        hash_bytes = hashlib.md5(text.encode()).digest()
        vec = [float(b) / 255.0 for b in hash_bytes]
        vec = vec * (VECTOR_DIMS // len(vec)) + vec[: (VECTOR_DIMS % len(vec))]
        return vec


# ---- 短期记忆操作 ----

async def add_memory(
    session_id: str,
    content: str,
    role: str,
    tool_calls: Optional[str] = None,
    tool_call_id: Optional[str] = None,
) -> None:
    """添加一条消息到短期记忆"""
    def _sync():
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO chat_history (session_id, role, content, tool_calls, tool_call_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, role, content, tool_calls, tool_call_id, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_sync)
    logger.debug(f"[Memory] 短期记忆已添加: session={session_id}, role={role}")


async def get_recent_history(
    session_id: str, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """获取最近 N 条会话历史（按时间升序），返回完整的 OpenAI 消息格式"""
    max_count = limit or settings.short_term_max_messages

    def _sync() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT role, content, tool_calls, tool_call_id FROM chat_history
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, max_count),
            )
            rows = cursor.fetchall()
            messages: List[Dict[str, Any]] = []
            for row in reversed(rows):
                msg: Dict[str, Any] = {"role": row["role"], "content": row["content"]}
                if row["tool_calls"]:
                    try:
                        msg["tool_calls"] = json.loads(row["tool_calls"])
                    except json.JSONDecodeError:
                        pass
                if row["tool_call_id"]:
                    msg["tool_call_id"] = row["tool_call_id"]
                messages.append(msg)
            return messages
        finally:
            conn.close()

    return await asyncio.to_thread(_sync)


# ---- 长期记忆操作 ----

async def store_fact(
    session_id: str, fact: str, metadata: Optional[Dict[str, Any]] = None
) -> None:
    """存储一条事实到长期记忆（含向量）"""
    embedding = await _get_embedding(fact)
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    def _sync():
        conn = get_db_connection()
        try:
            # 插入文档内容
            cursor = conn.execute(
                "INSERT INTO memory_docs (session_id, content, metadata, created_at) VALUES (?, ?, ?, ?)",
                (session_id, fact, meta_json, time.time()),
            )
            doc_id = cursor.lastrowid

            # 插入向量（vec_memory 的 rowid 与 memory_docs.id 一一对应）
            conn.execute(
                "INSERT INTO vec_memory (rowid, embedding) VALUES (?, ?)",
                (doc_id, json.dumps(embedding)),
            )
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_sync)
    logger.debug(f"[Memory] 长期记忆已存储: {fact[:50]}...")


async def retrieve_memory(
    session_id: str, query: str, top_k: int = 3
) -> List[str]:
    """向量检索与查询相关的长期记忆"""
    if not query.strip():
        return []

    embedding = await _get_embedding(query)

    def _sync() -> List[str]:
        conn = get_db_connection()
        try:
            conn.row_factory = sqlite3.Row

            # 构建 WHERE 条件：session_id 为 "_all" 时不按会话过滤
            session_filter = "" if session_id == "_all" else "AND m.session_id = ?"
            params: List[Any] = [json.dumps(embedding), top_k]
            if session_id != "_all":
                params.insert(0, session_id)

            cursor = conn.execute(
                f"""
                SELECT m.content
                FROM vec_memory v
                JOIN memory_docs m ON v.rowid = m.id
                WHERE v.embedding MATCH ? {session_filter}
                ORDER BY v.distance
                LIMIT ?
                """,
                params,
            )
            rows = cursor.fetchall()
            return [row["content"] for row in rows if row["content"]]
        except Exception as e:
            logger.warning(f"[Memory] 向量检索失败，回退按 session 搜索: {e}")
            # 回退：按 session 取最近文档
            try:
                filter_clause = "" if session_id == "_all" else "WHERE session_id = ?"
                cursor = conn.execute(
                    f"""
                    SELECT content FROM memory_docs
                    {filter_clause}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (top_k,) if session_id == "_all" else (session_id, top_k),
                )
                return [row["content"] for row in cursor.fetchall() if row["content"]]
            except:
                return []
        finally:
            conn.close()

    return await asyncio.to_thread(_sync)


async def delete_session_memories(session_id: str) -> None:
    """删除指定会话的所有记忆"""
    def _sync():
        conn = get_db_connection()
        try:
            # 获取该会话的所有文档 ID
            cursor = conn.execute(
                "SELECT id FROM memory_docs WHERE session_id = ?",
                (session_id,),
            )
            ids = [row[0] for row in cursor.fetchall()]

            # 删除向量
            for doc_id in ids:
                conn.execute("DELETE FROM vec_memory WHERE rowid = ?", (doc_id,))

            # 删除文档
            conn.execute("DELETE FROM memory_docs WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_sync)
    logger.info(f"[Memory] 已清除会话 {session_id} 的长期记忆")


# ---- DualMemory 管理器（对外接口，保持与旧代码一致） ----

class DualMemory:
    """双轨记忆管理器"""

    def __init__(self) -> None:
        init_memory_db()

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[str] = None,
        tool_call_id: Optional[str] = None,
    ) -> None:
        """添加消息到短期记忆"""
        await add_memory(session_id, content, role, tool_calls, tool_call_id)

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取短期记忆历史"""
        return await get_recent_history(session_id)

    async def store_fact(
        self, session_id: str, fact: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """存储事实到长期记忆"""
        await store_fact(session_id, fact, metadata)

    async def get_relevant_context(self, query: str) -> List[str]:
        """获取与查询相关的长期记忆上下文"""
        # 由于 agent.py 调用时没有传 session_id，默认检索所有会话
        return await retrieve_memory("_all", query)

    async def build_messages(
        self, session_id: str, system_prompt: str
    ) -> List[Dict[str, Any]]:
        """
        构建完整的消息列表：
        1. System Prompt（含长期记忆上下文）
        2. 短期记忆历史
        """
        history = await self.get_history(session_id)

        # 取最近用户消息作为检索查询
        recent_user_msgs = [
            m["content"]
            for m in reversed(history)
            if m["role"] == "user"
        ]
        query = recent_user_msgs[0] if recent_user_msgs else ""

        # 检索长期记忆
        relevant_context = await self.get_relevant_context(query) if query else []

        # 增强 system prompt
        enhanced_system = system_prompt
        if relevant_context:
            context_str = "\n".join(f"- {fact}" for fact in relevant_context)
            enhanced_system = (
                f"{system_prompt}\n\n## 相关记忆上下文\n{context_str}"
            )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": enhanced_system}
        ]
        messages.extend(history)
        return messages

    async def clear(self, session_id: str) -> None:
        """清除指定会话的所有记忆"""
        # 清空短期记忆
        def _clear_short():
            conn = get_db_connection()
            try:
                conn.execute(
                    "DELETE FROM chat_history WHERE session_id = ?",
                    (session_id,),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_clear_short)
        await delete_session_memories(session_id)
        logger.info(f"[Memory] 已清除会话 {session_id} 的所有记忆")


# 应用启动时初始化数据库
init_memory_db()
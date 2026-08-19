"""
定时任务模块：APScheduler 加载 cron 配置
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.core.config import BASE_DIR


class SchedulerManager:
    """定时任务管理器"""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._cron_dir = BASE_DIR / "app" / "cron"

    def load_cron_jobs(self) -> None:
        """加载 /crons/*.json 下的所有定时任务配置"""
        if not self._cron_dir.exists():
            logger.warning(f"[Scheduler] cron 目录不存在: {self._cron_dir}")
            return

        cron_files = list(self._cron_dir.glob("*.json"))
        if not cron_files:
            logger.info("[Scheduler] 未找到 cron 配置文件")
            return

        for file_path in cron_files:
            jobs = self._load_cron_file(file_path)
            for job_config in jobs:
                self._register_job(job_config)

    def _load_cron_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载单个 cron JSON 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 支持单个任务或任务列表
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"[Scheduler] 加载 cron 文件失败 {file_path}: {e}")
            return []

    def _register_job(self, config: Dict[str, Any]) -> None:
        """注册一个定时任务"""
        cron_expr = config.get("cron", "")
        skill_name = config.get("skill", "")
        task_name = config.get("name", f"{skill_name}@{cron_expr}")

        if not cron_expr or not skill_name:
            logger.warning(f"[Scheduler] 无效的 cron 配置: {config}")
            return

        try:
            # 解析 cron 表达式: "0 8 * * *"
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                logger.error(f"[Scheduler] 无效的 cron 表达式: {cron_expr}")
                return

            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )

            self.scheduler.add_job(
                func=self._execute_cron_task,
                trigger=trigger,
                id=task_name,
                name=task_name,
                replace_existing=True,
                kwargs={"skill_name": skill_name, "task_name": task_name},
            )
            logger.info(f"[Scheduler] 已注册定时任务: {task_name} ({cron_expr})")
        except Exception as e:
            logger.error(f"[Scheduler] 注册任务失败 {task_name}: {e}")

    async def _execute_cron_task(
        self, skill_name: str, task_name: str
    ) -> None:
        """执行定时任务"""
        from app.core.agent import agent

        logger.info(f"[Scheduler] 执行定时任务: {task_name}")
        user_input = f"[定时任务] 请执行任务: {task_name}，调用技能: {skill_name}"
        try:
            result = await agent.run(
                user_input=user_input,
                session_id="_cron_scheduler",
            )
            logger.info(f"[Scheduler] 任务 {task_name} 完成: {result[:100]}")
        except Exception as e:
            logger.error(f"[Scheduler] 任务 {task_name} 执行失败: {e}")

    def start(self) -> None:
        """启动调度器"""
        self.load_cron_jobs()
        if self.scheduler.get_jobs():
            self.scheduler.start()
            logger.info(
                f"[Scheduler] 调度器已启动，共 {len(self.scheduler.get_jobs())} 个任务"
            )
        else:
            logger.info("[Scheduler] 无定时任务，调度器未启动")

    def shutdown(self) -> None:
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("[Scheduler] 调度器已关闭")


# 全局单例
scheduler_manager = SchedulerManager()
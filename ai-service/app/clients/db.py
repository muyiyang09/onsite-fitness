"""MySQL 只读访问层（SQLAlchemy 2.0 Core + pymysql）。

AI 服务只读现有 sports_takeout 库（coach / course / category / coach_schedule），
连接参数来自 config.settings.mysql_dsn。故意用「只读 + 惰性 engine + 查询函数」，
不引入 ORM 模型，保持与 Java 后端解耦：后端改了表，AI 服务只需改 SQL 字符串。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    """惰性创建全局 engine（连接池）。用只读账号即可。

    #05 显式配置池参数：默认 5 连接撑不住并发，池满即报错；显式 pool_size/max_overflow
    让业务峰值（≥50 并发）不至于排队等连接。
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.mysql_dsn,
            pool_pre_ping=True,  # 取连接前先 ping，避免拿到失效连接
            pool_recycle=3600,
            pool_size=settings.mysql_pool_size,
            max_overflow=settings.mysql_max_overflow,
            pool_timeout=settings.mysql_pool_timeout,
            echo=False,
            future=True,
        )
    return _engine


def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """执行只读查询，返回 list[dict]（每行一个 dict，key 为列名）。"""
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params or {})
        cols = list(rows.keys())
        return [dict(zip(cols, row, strict=True)) for row in rows]


def execute(sql: str, params: dict[str, Any] | None = None) -> int:
    """执行写操作（INSERT/UPDATE），返回受影响行数。用于审计日志等旁路写入。"""
    with get_engine().begin() as conn:  # begin() 自动 commit / 异常回滚
        result = conn.execute(text(sql), params or {})
        return result.rowcount


async def afetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """异步版 fetch_all。用线程池执行同步查询，不阻塞事件循环。

    为什么不换 aiomysql 驱动：DB 读只有毫秒级，不是延迟瓶颈（LLM 才是），
    `asyncio.to_thread` 复用已测试的同步 SQLAlchemy 层，零新依赖、零驱动迁移风险。
    """
    import asyncio

    return await asyncio.to_thread(fetch_all, sql, params)


async def aexecute(sql: str, params: dict[str, Any] | None = None) -> int:
    """异步版 execute。审计日志等旁路写入用（fire-and-forget）。"""
    import asyncio

    return await asyncio.to_thread(execute, sql, params)


def is_db_available() -> bool:
    """探活：MySQL 是否可连。用于上层决定走真库还是 mock 兜底。"""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("MySQL 不可用：%s", exc)
        return False

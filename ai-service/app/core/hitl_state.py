"""HITL 审核单状态（#10 §1.4）：Redis 存储 + 防重复 resume / 冲突 / 取消。

审核单生命周期：pending（等待人工）→ approved / rejected / cancelled（终态）。
用 Redis key `hitl:{thread_id}:status` 记录，TTL 24h 与 Checkpointer 对齐。

设计（fail-open）：Redis 不可用时状态读写降级为「无状态」——不阻断审核流程，
代价是冲突检测失效（单副本场景可接受；多副本生产 Redis 是硬依赖，不会不可用）。
"""

from __future__ import annotations

import logging

import redis.asyncio as redis

from app.clients.redis_client import get_pool

logger = logging.getLogger(__name__)

_TTL = 86400  # 24h，与 Checkpointer TTL 对齐
_PENDING = "pending"
_TERMINAL = {"approved", "rejected", "cancelled"}


async def set_status(thread_id: str, status: str) -> None:
    try:
        r = redis.Redis(connection_pool=get_pool())
        await r.set(f"hitl:{thread_id}:status", status, ex=_TTL)
    except Exception as exc:  # noqa: BLE001
        logger.debug("HITL 状态写降级（Redis 不可用）：%s", exc)


async def get_status(thread_id: str) -> str | None:
    try:
        r = redis.Redis(connection_pool=get_pool())
        return await r.get(f"hitl:{thread_id}:status")
    except Exception as exc:  # noqa: BLE001
        logger.debug("HITL 状态读降级（Redis 不可用）：%s", exc)
        return None


def is_terminal(status: str | None) -> bool:
    """是否已是终态（不能再 resume）。"""
    return status in _TERMINAL


__all__ = ["set_status", "get_status", "is_terminal", "_PENDING"]

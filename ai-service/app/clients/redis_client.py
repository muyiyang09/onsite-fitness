"""Redis 连接池共享层（#05）。

缓存 / 限流 / Token 预算都要连 Redis，统一走这一个连接池，避免各自建池浪费连接。
所有上游组件对 Redis 的调用都是「fail-open」：连不上就降级，绝不抛异常阻断业务。
"""

from __future__ import annotations

import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def get_pool() -> redis.ConnectionPool:
    """惰性获取全局连接池（decode_responses=True，短连接超时避免拖慢请求）。"""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=2
        )
    return _pool


async def close() -> None:
    """优雅停机时关闭连接池。"""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


__all__ = ["get_pool", "close"]

"""RedisDBCheckpointer：RedisSaver 的 DB 灾备包装。

背景：Redis Checkpointer 有 TTL，到期时用户还在会话中 → state 丢失 → 会话中断。
本包装在 Redis miss 时从 DB 读 state + 回填 Redis，aput 时双写 DB，形成灾备。

三类缓存防护（防雪崩/穿透/击穿）：
  - singleflight（防击穿）：同一 thread_id 并发读 Redis miss 时，只放一个请求进 DB，
    其余等锁，避免瞬时并发把 DB 打爆；
  - 空值缓存（防穿透）：刚查过 DB 确认无数据，短时间内不再查 DB；
  - 刷新续期（防雪崩）：Redis 侧 refresh_on_read=True 读时续期，活跃 thread 不被误清。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langgraph.checkpoint.base import CheckpointTuple

logger = logging.getLogger(__name__)

_EMPTY_CACHE_TTL = 60  # 空值缓存 TTL（秒）：确认 DB 无数据后，60s 内不再查 DB


class RedisDBCheckpointer:
    """包装 AsyncRedisSaver，加 DB 灾备。其余方法通过 __getattr__ 委托给 inner。"""

    def __init__(self, inner) -> None:
        self._inner = inner
        self._locks: dict[str, asyncio.Lock] = {}
        self._empty_cache: dict[str, float] = {}

    def _thread_id(self, config: dict[str, Any]) -> str:
        return (config.get("configurable") or {}).get("thread_id", "")

    async def aget_tuple(self, config: dict[str, Any]):
        result = await self._inner.aget_tuple(config)
        if result is not None:
            return result  # Redis 命中，直接返回

        thread_id = self._thread_id(config)
        if not thread_id:
            return None

        # singleflight：并发读只放一个进 DB
        lock = self._locks.setdefault(thread_id, asyncio.Lock())
        async with lock:
            # 空值缓存（防穿透）
            last_miss = self._empty_cache.get(thread_id)
            if last_miss and time.time() - last_miss < _EMPTY_CACHE_TTL:
                return None
            self._empty_cache.pop(thread_id, None)

            from app.core import session_store

            try:
                data = await session_store.get_state(thread_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Checkpoint] DB 灾备读失败，thread_id=%s：%s", thread_id, exc)
                return None

            if data is None:
                self._empty_cache[thread_id] = time.time()  # 空值缓存
                return None

            checkpoint = data.get("checkpoint")
            metadata = data.get("metadata") or {}
            # 回填 Redis，后续请求走 Redis 快速路径
            try:
                await self._inner.aput(config, checkpoint, metadata, {})
                logger.info("[Checkpoint] DB 灾备命中 + 回填 Redis，thread_id=%s", thread_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Checkpoint] 回填 Redis 失败，thread_id=%s：%s", thread_id, exc)

            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=data.get("parent_config"),
                pending_writes=data.get("pending_writes"),
            )

    async def aput(
        self, config: dict[str, Any], checkpoint, metadata, new_versions
    ) -> dict[str, Any]:
        await self._inner.aput(config, checkpoint, metadata, new_versions)

        thread_id = self._thread_id(config)
        if thread_id:
            from app.core import session_store

            try:
                await session_store.put_state(
                    thread_id,
                    {
                        "checkpoint": checkpoint,
                        "metadata": metadata,
                        "parent_config": None,
                        "pending_writes": None,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                # DB 灾备写失败不影响主流程（Redis 已写成功）
                logger.warning("[Checkpoint] DB 灾备写失败，thread_id=%s：%s", thread_id, exc)
        return config

    def __getattr__(self, name: str):
        # 其余方法（aget/alist/aput_writes/...）全部委托给 inner RedisSaver
        return getattr(self._inner, name)


__all__ = ["RedisDBCheckpointer"]

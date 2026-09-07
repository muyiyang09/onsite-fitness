"""Checkpointer 构建器（上线加固：崩溃恢复 + 多副本共享状态 + DB 灾备）。

为什么需要（#03 §4.1）：
  - MemorySaver 进程内、重启即丢、多副本不共享；
  - RedisSaver 持久化 + TTL 自动清理 + 多副本共享 thread_id 状态，
    是 HITL interrupt（证书审核最终确认）跨副本恢复的基础；
  - 但 Redis TTL 到期时用户还在会话中 → state 丢失 → 会话中断。
    DB 灾备层：Redis miss 时从 DB 读 → 回填 Redis → 继续会话。

设计（fail-open）：
  - `checkpointer_backend=memory`（默认，开发）→ MemorySaver；
  - `checkpointer_backend=redis`（生产）→ AsyncRedisSaver（异步图用 ainvoke），
    构建失败时回退 MemorySaver 并告警——Checkpointer 故障不能拖垮服务启动；
  - `checkpoint_db_fallback=True`（生产默认开）→ 在 AsyncRedisSaver 外包一层
    RedisDBCheckpointer，aget miss 时查 DB + 回填 Redis，aput 时双写 DB。
    DB 灾备层自带 singleflight（防击穿）+ 空值缓存（防穿透）+ TTL 抖动（防雪崩）。
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def build_checkpointer():
    """按配置构建 Checkpointer。

    构建顺序：Redis → RedisDBCheckpointer 包装 → MemorySaver 回退。
    每层都有 fail-open 降级，最终保证返回一个可用 Checkpointer。
    """
    if settings.checkpointer_backend == "redis":
        try:
            from langgraph.checkpoint.redis import AsyncRedisSaver

            # default_ttl 单位是「分钟」（langgraph-checkpoint-redis 约定）
            ttl = {
                "default_ttl": settings.checkpoint_ttl_minutes,
                "refresh_on_read": True,  # 读取时续期，活跃 thread 不会被误清
            }
            saver = AsyncRedisSaver(redis_url=settings.redis_url, ttl=ttl)
            logger.info(
                "[Checkpoint] 使用 RedisSaver，TTL=%d 分钟", settings.checkpoint_ttl_minutes
            )

            # DB 灾备包装：防止 Redis TTL 过期导致会话中断
            if settings.checkpoint_db_fallback:
                try:
                    from app.core.checkpoint_redis_db import RedisDBCheckpointer

                    saver = RedisDBCheckpointer(saver)
                    logger.info("[Checkpoint] 已启用 DB 灾备层（防雪崩/穿透/击穿）")
                except Exception as exc:  # noqa: BLE001
                    # DB 灾备层包装失败不影响 RedisSaver 本身可用
                    logger.warning("[Checkpoint] DB 灾备层包装失败，仅用裸 RedisSaver：%s", exc)

            return saver
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Checkpoint] RedisSaver 构建失败，回退 MemorySaver：%s", exc)

    from langgraph.checkpoint.memory import MemorySaver

    logger.info("[Checkpoint] 使用 MemorySaver（单进程开发模式）")
    return MemorySaver()


__all__ = ["build_checkpointer"]

"""Redis 结果缓存（#05 商业化加固 · 省 LLM 成本 + 提速）。

相同 query 24h 内直接复用结果，跳过 LLM 调用。健身推荐场景下「望京 减脂 预算200」
这类高频 query 命中率可观，能显著省 token 成本 + 降延迟。

设计要点（上线关键）：
  - **fail-open**：Redis 挂了 / 连不上时，缓存读写都静默降级为「不缓存」，绝不因此
    阻断推荐主链路——保护组件自身故障不能让业务全挂；
  - 惰性连接池：首次使用才建 ConnectionPool，不拖慢启动；
  - key 用 md5(query|top_n|city)，避免把中文/长 query 直接当 key。

缓存三防（§6.18 · 雪崩/穿透/击穿）：
  - **雪崩**：TTL 加 ±10% 抖动，避免同一时刻大批 key 同时过期回源打挂 DB/LLM；
  - **穿透**：命中率为主场景，空值缓存意义有限，未落 null 占位（决策见 TODO 文档）；
  - **击穿**：singleflight 互斥锁——同一 key 只允许一个请求回源构图，其余等待复用结果，
    避免热点 query 瞬间 N 路并发打同一个 LLM 调用。
  锁释放用 Lua CAS（get==value→del），杜绝「锁已过期被他人接管后误删」的 TOCTOU。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from typing import Any
from uuid import uuid4

import redis.asyncio as redis

from app.clients.redis_client import get_pool
from app.config import settings

logger = logging.getLogger(__name__)

_JITTER_RATIO = 0.10  # 雪崩防护：±10% 抖动 TTL
_LOCK_TTL_SECONDS = 120  # 击穿防护：锁 TTL 必须 > 最坏图执行时长（llm_timeout=60s）
_POLL_INTERVAL, _POLL_BUDGET = 0.5, 8.0  # 等待者预算：8 秒拿不到就自己跑图（避免活锁）

# 哨兵：Redis 异常时 try_acquire_build_lock 返回它，表示「没抢到锁但也不用释放」，
# 从而让 release_build_lock 能安全跳过（fail-open 语义，不误 eval）。
_NO_LOCK = "no-lock"

_UNLOCK_LUA = (
    "if redis.call('get',KEYS[1]) == ARGV[1] "
    "then return redis.call('del',KEYS[1]) else return 0 end"
)


def make_cache_key(user_query: str, top_n: int, city_override: str | None = None) -> str:
    """缓存 key：md5(query|top_n|city)。"""
    raw = f"{user_query}|{top_n}|{city_override or ''}"
    return f"recommend:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


def _jittered(ttl: int) -> int:
    """给 TTL 加 ±_JITTER_RATIO 抖动（雪崩防护）。"""
    return max(1, int(ttl * (1 + random.uniform(-_JITTER_RATIO, _JITTER_RATIO))))


async def get_cache(key: str) -> dict[str, Any] | None:
    """读缓存。命中返回 dict，未命中 / Redis 不可用返回 None。"""
    try:
        r = redis.Redis(connection_pool=get_pool())
        val = await r.get(key)
        return json.loads(val) if val else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("缓存读降级（Redis 不可用）：%s", exc)
        return None


async def set_cache(key: str, value: dict[str, Any], ttl: int | None = None) -> None:
    """写缓存（TTL 抖动）。Redis 不可用时静默跳过。"""
    try:
        r = redis.Redis(connection_pool=get_pool())
        await r.setex(
            key,
            _jittered(ttl or settings.cache_ttl),
            json.dumps(value, ensure_ascii=False, default=str),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("缓存写降级（Redis 不可用）：%s", exc)


async def try_acquire_build_lock(key: str) -> str | None:
    """singleflight 抢锁：抢到才允许回源构图。

    返回：
      - uuid 字符串：抢到锁，构图完成后必须 release；
      - None：别人正在建（应等待复用结果，或超时后自己兜底跑图）；
      - _NO_LOCK：Redis 挂了，fail-open（不阻塞，也无需释放）。
    """
    try:
        r = redis.Redis(connection_pool=get_pool())
        token = uuid4().hex
        ok = await r.set(f"{key}:lock", token, nx=True, ex=_LOCK_TTL_SECONDS)
        return token if ok else None
    except Exception:  # noqa: BLE001
        return _NO_LOCK


async def release_build_lock(key: str, token: str | None) -> None:
    """Lua CAS 原子释放：token 不匹配（锁已过期被他人接管）不误删。

    对 None（未抢到）与 _NO_LOCK（Redis 挂了）直接跳过，不 eval。
    """
    if token is None or token == _NO_LOCK:
        return
    try:
        r = redis.Redis(connection_pool=get_pool())
        await asyncio.wait_for(r.eval(_UNLOCK_LUA, 1, f"{key}:lock", token), timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("锁释放失败（忽略）：%s", exc)


async def wait_for_result(key: str, budget: float = _POLL_BUDGET) -> dict[str, Any] | None:
    """等待别人构图的结果：预算内轮询缓存，拿到即返回，超时返回 None（调用方自己兜底）。"""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + budget
    while loop.time() < deadline:
        got = await get_cache(key)
        if got is not None:
            return got
        await asyncio.sleep(_POLL_INTERVAL)
    return None


__all__ = [
    "get_cache",
    "set_cache",
    "make_cache_key",
    "try_acquire_build_lock",
    "release_build_lock",
    "wait_for_result",
]

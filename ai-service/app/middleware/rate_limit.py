"""限流中间件（#05 商业化加固 · 防恶意刷 + 公平分配）。

三级限流（固定窗口，每分钟）：全局 / 单 IP / 单用户。用 Redis INCR + EXPIRE 实现，
超阈值抛 RateLimitError → 转 429。

设计要点（上线关键）：
  - **fail-open**：Redis 挂了 / 连不上时静默放过流量（只 debug 日志），绝不让「限流组件
    自身故障」把整个服务打挂——这是限流器生产化的第一条铁律；
  - 只对 `/v1/ai/` 业务路径限流，健康检查等系统路径不限；
  - 固定窗口（按分钟取整）实现简单、可读，商业项目入门够用；若要更平滑可换令牌桶。
"""

from __future__ import annotations

import logging
import time

import redis.asyncio as redis
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.clients.redis_client import get_pool
from app.config import settings
from app.core.exceptions import AIError, RateLimitError

logger = logging.getLogger(__name__)


async def check_rate_limit(user_id: str, ip: str) -> None:
    """三级限流检查。超阈值抛 RateLimitError；Redis 不可用 fail-open 直接放过。"""
    try:
        r = redis.Redis(connection_pool=get_pool())
        now = int(time.time())
        for key, limit, window in [
            (f"rl:global:{now // 60}", settings.rl_global_per_min, 60),
            (f"rl:ip:{ip}:{now // 60}", settings.rl_ip_per_min, 60),
            (f"rl:user:{user_id}:{now // 60}", settings.rl_user_per_min, 60),
        ]:
            cnt = await r.incr(key)
            await r.expire(key, window)
            if cnt > limit:
                raise RateLimitError(detail=f"{key.split(':')[0]} 超限 {cnt}/{limit}")
    except RateLimitError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.debug("限流降级（Redis 不可用，fail-open 放行）：%s", exc)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 只限业务路径；健康检查等系统路径跳过
        if not request.url.path.startswith("/v1/ai/"):
            return await call_next(request)

        user_id = request.headers.get("x-user-id", "anon")
        ip = request.client.host if request.client else "unknown"
        try:
            await check_rate_limit(user_id, ip)
        except AIError as exc:
            # 中间件异常不会被 FastAPI 全局 handler 捕获，需自行构造错误响应
            return JSONResponse(
                status_code=exc.http_status,
                content={
                    "code": exc.code,
                    "msg": exc.msg,
                    "request_id": request.headers.get("x-request-id", "-"),
                },
            )
        return await call_next(request)


__all__ = ["RateLimitMiddleware", "check_rate_limit"]

"""Token 预算控制（#05 商业化加固 · 成本管控）。

LLM 成本是变量，恶意用户/被劫持账号能瞬间烧光预算。三级预算：
  1. 单次请求输入 token 上限（防长 prompt 攻击）；
  2. 单用户单日上限；
  3. 全局单日上限（触发后运营可切 mock 模式）。

设计要点（上线关键）：
  - **fail-open**：Redis 不可用时跳过预算检查（只 debug 日志），预算管控故障不能拦正常用户；
  - 不做 tiktoken（OpenAI BPE，国内下载其词表文件易失败）：用「中文 1 字符 ≈ 1 token、
    其它 4 字符 ≈ 1 token」的启发式估算，对成本封顶足够准（预算是上限，不是精确记账）；
  - 本函数在**端点内**调用（已有 Pydantic 解析好的 body），不做成中间件——因为读 body
    的中间件在 Starlette 里要缓存 body、实现别扭，端点里直接拿 payload 更干净。
"""

from __future__ import annotations

import logging
import time

import redis.asyncio as redis

from app.clients.redis_client import get_pool
from app.config import settings
from app.core.exceptions import TokenBudgetExceededError

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """估算 token 数：CJK 字符 1 字 = 1 token，其它 4 字符 ≈ 1 token。"""
    text = text or ""
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    other = len(text) - cjk
    return cjk + (other // 4) + 1


async def check_token_budget(user_id: str, input_tokens: int) -> None:
    """检查三级 token 预算。超限抛 TokenBudgetExceededError；Redis 不可用 fail-open。"""
    # 单次请求上限：纯内存判断，无需 Redis
    if input_tokens > settings.token_per_request_limit:
        raise TokenBudgetExceededError(
            f"单次请求输入过长 {input_tokens} > {settings.token_per_request_limit}"
        )

    try:
        r = redis.Redis(connection_pool=get_pool())
        today = time.strftime("%Y%m%d")

        # 单用户单日：累加并检查
        user_key = f"tok:user:{user_id}:{today}"
        user_used = await r.incrby(user_key, input_tokens)
        await r.expire(user_key, 86400 * 2)  # 留 2 天冗余，跨天自然过期
        if user_used > settings.token_user_daily_limit:
            raise TokenBudgetExceededError(
                f"单用户单日超限 {user_used} > {settings.token_user_daily_limit}"
            )

        # 全局单日：累加并检查
        global_key = f"tok:global:{today}"
        global_used = await r.incrby(global_key, input_tokens)
        await r.expire(global_key, 86400 * 2)
        if global_used > settings.token_global_daily_limit:
            raise TokenBudgetExceededError(
                f"全局单日超限 {global_used} > {settings.token_global_daily_limit}"
            )
    except TokenBudgetExceededError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.debug("Token 预算降级（Redis 不可用，fail-open 放行）：%s", exc)


__all__ = ["estimate_tokens", "check_token_budget"]

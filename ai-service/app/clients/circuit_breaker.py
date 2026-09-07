"""LLM 熔断器（#05 商业化加固 · 防雪崩）。

当 LLM 连续失败 N 次（阈值 cb_fail_threshold），熔断器「开路」：后续请求直接快速失败
（不再真调 LLM），由上层走 mock 降级，避免每次请求都傻等 60s 超时、把线程池/超时预算
耗尽。一段时间（cb_reset_timeout）后进入「半开」，放一个请求试探，成功则恢复闭合。

状态机：
    CLOSED --连续 N 次失败--> OPEN --超时后--> HALF_OPEN --试探成功--> CLOSED
                                            └--试探失败--> OPEN

与限流/降级的区别（见 #05 文档 §2.2）：限流挡入口、熔断快速失败不传染、降级返回兜底。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, TypeVar

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"  # 正常放行
    OPEN = "open"  # 熔断，快速失败
    HALF_OPEN = "half_open"  # 半开，放一个试探


class CircuitBreaker:
    def __init__(self, fail_threshold: int = 5, reset_timeout: int = 60) -> None:
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.fail_count = 0
        self.state = CircuitState.CLOSED
        self.last_fail_time = 0.0
        self._probe_inflight = False  # 半开时是否已有试探请求在飞
        self._lock = asyncio.Lock()

    async def _allow(self) -> None:
        """判断当前请求是否被放行；不放行则抛 RuntimeError（快速失败）。"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_fail_time > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self._probe_inflight = False
                logger.info("[熔断] 超时后进入半开试探")
            else:
                raise RuntimeError(f"CircuitBreaker OPEN（{self.reset_timeout}s 后重试）")
        if self.state == CircuitState.HALF_OPEN:
            # 半开只放一个试探请求，其余快速失败
            if self._probe_inflight:
                raise RuntimeError("CircuitBreaker HALF_OPEN 试探中，请稍后再试")
            self._probe_inflight = True

    async def _on_success(self) -> None:
        self.state = CircuitState.CLOSED
        self.fail_count = 0
        self._probe_inflight = False
        logger.info("[熔断] 恢复闭合")

    async def _on_failure(self) -> None:
        self.fail_count += 1
        self.last_fail_time = time.time()
        self._probe_inflight = False
        if self.fail_count >= self.fail_threshold:
            self.state = CircuitState.OPEN
            logger.warning("[熔断] 连续 %d 次失败，开路 %ds", self.fail_count, self.reset_timeout)

    async def call(self, fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        async with self._lock:
            await self._allow()
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            async with self._lock:
                await self._on_failure()
            raise
        async with self._lock:
            await self._on_success()
        return result


# 全局单例：LLM 调用统一走这个熔断器（阈值/超时读配置）
llm_breaker = CircuitBreaker(
    fail_threshold=settings.cb_fail_threshold,
    reset_timeout=settings.cb_reset_timeout,
)

__all__ = ["CircuitBreaker", "CircuitState", "llm_breaker"]

"""轻量 Trace：节点级耗时追踪（#06 可观测性）。

两层观测（互补，不互替）：
  - 结构化日志（无条件开）：每次节点执行打一条 `[Trace] node=xxx latency_ms=yyy`
    （带 request_id），配合 ELK/Loki 覆盖 80% 的排查需求；
  - Langfuse span（#13，可选）：LANGFUSE_ENABLED=true 且装包后，每个节点成为 trace
    树上的 span，LLM generation（llm.py 埋点）自动嵌套其下——见 langfuse_client.py。
    未启用时 observe_span 是 no-op，行为与纯日志版完全一致。

产出：每次节点执行打一条 `[Trace] node=xxx latency_ms=yyy`（带 request_id）。
"""
from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Awaitable, Callable

from app.clients.langfuse_client import observe_span
from app.graphs.base import invoke_node

logger = logging.getLogger("app.trace")


def trace_node(name: str):
    """节点级耗时装饰器。包装 async 节点：超时兜底 + 耗时日志 +（可选）Langfuse span。

    同时借 invoke_node 套 asyncio.wait_for 超时兜底（§6.30 死循环防护），
    节点挂起/死循环会被强制终止而非无限占用 worker。
    """

    def decorator(fn: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        # Langfuse span 包在最内层：只覆盖节点实际执行（不含 wait_for 兜底壳），
        # 超时取消/节点异常都会被记录到 span 上。
        fn = observe_span(f"node.{name}")(fn)

        @wraps(fn)
        async def wrapper(state):
            start = time.perf_counter()
            try:
                return await invoke_node(fn, state)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info("[Trace] node=%s latency_ms=%.1f", name, elapsed_ms)

        return wrapper

    return decorator


__all__ = ["trace_node"]

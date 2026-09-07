"""Langfuse LLM 可观测性集成（#13 · 可选依赖，未装包/未启用时全链路 no-op）。

覆盖三层埋点（业务代码零改动，收口在基础设施层）：
  - 入口 root trace：API 端点装饰器（observe_span("api.xxx")），request_id 写进 metadata；
  - 节点 span：trace.py 的 trace_node 统一注入（node.xxx）；
  - LLM generation：llm.py 收口点（llm.completion / llm.acompletion），
    上报完整 messages、输出文本与 API 返回的**真实 usage**（替代 estimate_tokens 估算）。

设计纪律（与审计/限流/熔断同款 fail-open）：
  - 旁路上报：SDK 内部内存队列 + 后台批量发送，主流程只入队；
  - fail-open：未装包 / 未配置 / 初始化失败 / 上报异常，一律静默降级为纯日志，绝不阻断业务；
  - 可采样：LANGFUSE_SAMPLE_RATE（低峰全采、高峰调低）；停机前 flush 防丢队列尾巴。

为什么在 llm.py 收口而不走 litellm 的 langfuse callback：
  litellm==1.55.3 的集成只兼容 Langfuse v2 SDK（`langfuse.model.CreateTrace/CreateGeneration`，
  v3 已移除该 API）。本项目锁定 litellm 版本不升级，因此用 v3 的 @observe 在自己的
  LLM 客户端封装处埋点——这也顺便保证 usage/cost 归因的模型名口径与 LLM_MODEL 一致。

面试速记：Langfuse = LLM 应用的「行车记录仪」。日志回答「快不快、挂没挂」，
Langfuse 回答「AI 为什么这么答、花了多少钱」。详见 docs/13-Langfuse接入与面试题.md。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from app.config import settings

logger = logging.getLogger("app.langfuse")

# 进程内开关：init_langfuse() 成功后才置 True（观察点：装饰器在 import 时就已生效，
# 这里只控制「上报类」操作；observe 包装与否在 import 时由 settings.langfuse_enabled 决定）。
_langfuse_client: Any = None


def langfuse_ready() -> bool:
    """是否已完成初始化（init_langfuse 成功）。未 ready 时所有上报操作为 no-op。"""
    return _langfuse_client is not None


def init_langfuse() -> bool:
    """启动时初始化（lifespan 调用）。未启用/未配置/未装包/失败一律返回 False（fail-open）。

    v3 SDK 的全局 client（observe/langfuse_context 共用）从 LANGFUSE_* 环境变量读取
    凭据，因此这里把 settings 注入 env（setdefault：真实环境变量优先），再取全局 client。
    """
    global _langfuse_client
    if not settings.langfuse_enabled:
        return False
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.warning("[Langfuse] LANGFUSE_ENABLED=true 但缺少 PUBLIC_KEY/SECRET_KEY，降级关闭")
        return False
    try:
        import langfuse  # 延迟导入：未装包时只影响 Langfuse，不影响服务启动
    except ImportError:
        logger.warning(
            "[Langfuse] 未安装 langfuse 包，降级关闭（安装：pip install -e '.[langfuse]'）"
        )
        return False

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
    if settings.langfuse_sample_rate < 1.0:
        os.environ.setdefault("LANGFUSE_SAMPLE_RATE", str(settings.langfuse_sample_rate))

    try:
        _langfuse_client = langfuse.get_client()
        logger.info(
            "[Langfuse] 已启用：host=%s sample_rate=%s（旁路异步上报，fail-open）",
            settings.langfuse_host,
            settings.langfuse_sample_rate,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Langfuse] 初始化失败，降级关闭：%s", exc)
        return False


def flush_langfuse() -> None:
    """优雅停机前 flush：把内存队列里未发送的 trace 全部发出，防丢尾巴。"""
    if _langfuse_client is None:
        return
    try:
        _langfuse_client.flush()
        logger.info("[Langfuse] 停机 flush 完成")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Langfuse] flush 失败（忽略，不影响停机）：%s", exc)


def observe_span(name: str, as_type: str = "span"):
    """Langfuse 装饰器工厂：启用时把函数包成 span/generation；否则原样返回函数（no-op）。

    用法：
      - API 入口 root trace：@observe_span("api.recommend-coach")
      - 图节点 span：@observe_span("node.extract_intent")
      - LLM generation：@observe_span("llm.acompletion", as_type="generation")

    装饰发生在 import 时（由 settings.langfuse_enabled 决定），进程生命周期内行为一致；
    observe 未捕获的包装异常也按 fail-open 降级为不埋点。
    """

    def decorator(fn: Callable) -> Callable:
        if not settings.langfuse_enabled:
            return fn
        try:
            from langfuse import observe
        except ImportError:
            return fn
        try:
            return observe(name=name, as_type=as_type)(fn)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Langfuse] 包装 %s 失败，降级为不埋点：%s", name, exc)
            return fn

    return decorator


def update_trace_meta(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> None:
    """给当前 root trace 补元数据（user_id / session_id / request_id 等），便于按维度检索。

    旁路 no-op：未启用或上下文中没有活跃 trace 时静默忽略。
    """
    if not langfuse_ready():
        return
    try:
        from langfuse import langfuse_context

        langfuse_context.update_current_trace(
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[Langfuse] update_current_trace 失败（忽略）：%s", exc)


def update_current_generation(
    *,
    output: Any,
    model: str | None = None,
    usage: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """给当前 generation 补输出与真实 usage（llm.py 从 litellm 响应中提取后调用）。

    usage 口径（Langfuse v3 dict 形式）：{"input": p, "output": c, "total": t, "unit": "TOKENS"}。
    """
    if not langfuse_ready():
        return
    try:
        from langfuse import langfuse_context

        kw: dict[str, Any] = {"output": output}
        if model:
            kw["model"] = model
        if usage:
            kw["usage"] = usage
        if metadata:
            kw["metadata"] = metadata
        langfuse_context.update_current_observation(**kw)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[Langfuse] update_current_observation 失败（忽略）：%s", exc)


__all__ = [
    "langfuse_ready",
    "init_langfuse",
    "flush_langfuse",
    "observe_span",
    "update_trace_meta",
    "update_current_generation",
]

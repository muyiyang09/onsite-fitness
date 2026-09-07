"""业务异常体系 + 错误码（#05 商业化加固）。

设计动机（为什么不能用一坨 try/except + HTTPException 糊）：
  1. 商业项目要「错误码」而非「裸 500」——客户端能按 code 做降级/重试/提示，运营能按 code 告警；
  2. 统一异常基类让「全局异常中间件」只需一处映射 code → HTTP 状态码，不泄露内部栈；
  3. 错误分类（限流 / 降级 / 上游失败）对应不同处理策略，而非一律 500。

约定：业务层抛 `AIError` 子类，main.py 注册一个全局 handler 统一转成
`{"code": ..., "msg": ..., "request_id": ...}` 的 JSON 响应。
"""

from __future__ import annotations


class AIError(Exception):
    """AI 服务统一异常基类。子类只需覆盖 code / msg / http_status。"""

    code: str = "AI_INTERNAL"
    msg: str = "AI 服务内部错误"
    http_status: int = 500

    def __init__(self, msg: str | None = None, *, detail: str | None = None) -> None:
        self.msg = msg or self.msg
        self.detail = detail  # 面向开发者的额外信息（不进对外响应，只进日志）
        super().__init__(self.msg)


class LLMTimeoutError(AIError):
    """LLM 调用超时。上游慢/挂，属「降级」场景：客户端可重试或提示稍后再试。"""

    code = "AI_LLM_TIMEOUT"
    msg = "LLM 调用超时"
    http_status = 502


class LLMUnavailableError(AIError):
    """LLM 持续失败（熔断开路）。属「降级」：已切 mock，但明确告知调用方。"""

    code = "AI_LLM_UNAVAILABLE"
    msg = "LLM 服务暂不可用"
    http_status = 503


class UpstreamError(AIError):
    """MySQL / Redis 等上游依赖不可用。"""

    code = "AI_UPSTREAM"
    msg = "上游依赖暂不可用"
    http_status = 502


class TokenBudgetExceededError(AIError):
    """Token 预算耗尽（成本管控）。"""

    code = "AI_TOKEN_BUDGET"
    msg = "Token 预算耗尽"
    http_status = 429


class RateLimitError(AIError):
    """请求过频（限流）。"""

    code = "AI_RATE_LIMIT"
    msg = "请求过于频繁，请稍后再试"
    http_status = 429


class ValidationFailedError(AIError):
    """入参校验失败（Pydantic 之外的自定义校验）。"""

    code = "AI_VALIDATION"
    msg = "请求参数不合法"
    http_status = 400


class ConflictError(AIError):
    """资源状态冲突（如 HITL 审核单已处理过）。"""

    code = "AI_CONFLICT"
    msg = "资源状态冲突"
    http_status = 409


class NotFoundError(AIError):
    """资源不存在（如 HITL 审核单已取消/过期）。"""

    code = "AI_NOT_FOUND"
    msg = "资源不存在"
    http_status = 404


__all__ = [
    "AIError",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "UpstreamError",
    "TokenBudgetExceededError",
    "RateLimitError",
    "ValidationFailedError",
    "ConflictError",
    "NotFoundError",
]

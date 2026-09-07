"""Supervisor：统一 AI 入口路由（#08 · 多 Agent 协作）。

根据用户 query 路由到三个子 Agent 之一。默认关闭（supervisor_enabled=False），
各子 Agent 走自己的端点；打开后 `/v1/ai/chat` 用本路由分发。

设计（#02 §7 / #09 Q1.4）：Supervisor 只做路由、不做重活，用便宜模型/规则即可，
避免成为单点瓶颈。这里 mock 用关键词规则，真实用 LLM 分类。

§6.29：route_query 的 LLM 调用包熔断（llm_breaker）——连续失败超过阈值后快速失败，
降级到关键词规则路由（再兜底 recommend_coach），避免每次请求都傻等 LLM 超时。
"""

from __future__ import annotations

import logging

from app.clients.circuit_breaker import llm_breaker
from app.clients.llm import achat, is_mock_mode

logger = logging.getLogger(__name__)

_AGENTS = ("recommend_coach", "review_summary", "cert_review")


def _route_by_keyword(user_query: str) -> str:
    """关键词规则路由（离线兜底 / LLM 熔断后的降级路径）。"""
    q = (user_query or "").lower()
    if any(k in q for k in ("评价", "评论", "口碑", "反馈", "评价怎么样")):
        return "review_summary"
    if any(k in q for k in ("证书", "审核", "资质", "认证", "验证")):
        return "cert_review"
    return "recommend_coach"


async def route_query(user_query: str) -> str:
    """路由用户 query → agent 名。默认 recommend_coach。"""
    if is_mock_mode():
        return _route_by_keyword(user_query)

    from app.prompts.loader import load_prompt

    try:
        text = await llm_breaker.call(
            achat,
            [
                {"role": "system", "content": load_prompt("supervisor_route")},
                {"role": "user", "content": user_query},
            ],
        )
        text = (text or "").strip().lower()
        for agent in _AGENTS:
            if agent in text:
                return agent
        return "recommend_coach"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supervisor LLM 路由失败，降级关键词规则：%s", exc)
        return _route_by_keyword(user_query)


__all__ = ["route_query", "_AGENTS"]

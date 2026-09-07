"""教练推荐 + 用户反馈回流路由。"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.clients.cache import (
    get_cache,
    make_cache_key,
    release_build_lock,
    set_cache,
    try_acquire_build_lock,
    wait_for_result,
)
from app.clients.langfuse_client import observe_span, update_trace_meta
from app.config import settings
from app.core import metrics
from app.core.audit import spawn_audit
from app.core.exceptions import UpstreamError, ValidationFailedError
from app.core.logging import request_id_var
from app.core.safety import detect_injection
from app.graphs.recommend_coach import RECOMMEND_GRAPH
from app.middleware.token_budget import check_token_budget, estimate_tokens
from app.schemas.coach_recommend import RecommendResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ai", tags=["AI"])


class RecommendCoachIn(BaseModel):
    user_query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="用户自然语言，如 '望京 预算200 产后恢复 周末'",
    )
    city_code_override: str | None = Field(
        default=None, description="可选：小程序端已知用户城市时，强制覆盖 LLM 抽取结果"
    )
    top_n: int = Field(default=3, ge=1, le=5, description="返回教练数量（1~5）")


class FeedbackIn(BaseModel):
    """用户对推荐结果的反馈（点赞/点踩/下单），用于在线 Eval 回流。"""

    request_id: str = Field(..., description="对应推荐请求的 request_id（关联审计/日志）")
    action: str = Field(..., description="用户行为：like / dislike / order")
    coach_id: int | None = Field(default=None, description="被点击/下单的教练 ID")
    feedback: str | None = Field(default=None, description="补充文字反馈")


@router.post(
    "/recommend-coach",
    summary="教练智能推荐（自然语言 → Top N 教练 + 理由）",
    response_model=RecommendResult,
)
@observe_span("api.recommend-coach")
async def recommend_coach(
    payload: RecommendCoachIn,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> RecommendResult:
    user_id = x_user_id or "anon"
    request_id = request_id_var.get()
    query = payload.user_query.strip()
    if not query:
        raise ValidationFailedError("user_query 不能为空")

    # 注入检测（只告警 + 计数，不粗暴拒绝——推荐是低风险场景）
    if detect_injection(query):
        metrics.incr("injection_detected_total")
        logger.warning("[Safety] 检测到疑似提示词注入：%s", query[:100])

    # 1. Token 预算（fail-open：Redis 挂了直接放过）
    await check_token_budget(user_id, estimate_tokens(query))

    # 2. 结果缓存（相同 query 24h 复用，跳过 LLM）+ 击穿防护（singleflight）
    cache_key = make_cache_key(query, payload.top_n, payload.city_code_override)
    build_lock_token: str | None = None
    if settings.cache_enabled:
        cached = await get_cache(cache_key)
        if cached:
            metrics.incr("cache_hit_total")
            logger.info("[Cache] 命中，跳过 LLM：%s", query[:50])
            return RecommendResult.model_validate(cached)
        metrics.incr("cache_miss_total")

        # singleflight：抢到锁才回源构图；抢不到则等待复用在建请求的结果
        build_lock_token = await try_acquire_build_lock(cache_key)
        if build_lock_token is None:
            cached = await wait_for_result(cache_key)
            if cached:
                metrics.incr("cache_hit_total")
                logger.info("[Cache] 击穿等待命中，跳过 LLM：%s", query[:50])
                return RecommendResult.model_validate(cached)
            # 等待超时未拿到：自己跑图兜底（避免活锁）

    # 3. 走 Graph（ainvoke）
    thread_id = f"anon-{uuid4().hex}"  # 单次推荐无 resume，唯一 id 避免跨请求状态累积
    # Langfuse（#13）：root trace 元数据，request_id 是日志/审计/trace 三方关联键
    update_trace_meta(
        user_id=user_id,
        session_id=thread_id,
        metadata={"request_id": request_id, "top_n": payload.top_n},
        tags=["recommend"],
    )
    state_in: dict[str, object] = {"user_query": query, "top_n": payload.top_n}
    if payload.city_code_override:
        state_in["city_code_override"] = payload.city_code_override

    start = time.perf_counter()
    try:
        state_out = await RECOMMEND_GRAPH.ainvoke(
            state_in, config={"configurable": {"thread_id": thread_id}}
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Graph 执行失败：query=%s", query)
        raise UpstreamError(f"Graph 执行失败：{exc!r}") from exc
    finally:
        await release_build_lock(cache_key, build_lock_token)
    duration_ms = int((time.perf_counter() - start) * 1000)
    metrics.observe("graph_latency_ms", duration_ms)

    result_dict = state_out.get("result")
    if not result_dict:
        raise UpstreamError("Graph 返回缺 result 字段")
    result = RecommendResult.model_validate(result_dict)

    # 4. 写缓存 + 审计（旁路，不阻断响应）
    if settings.cache_enabled:
        await set_cache(cache_key, result.model_dump())
    spawn_audit(
        user_id=user_id,
        request_id=request_id,
        action="graph_invoke",
        model=settings.llm_model,
        prompt=query,
        response=result.recommend_reason,
        input_tokens=estimate_tokens(query),
        output_tokens=estimate_tokens(result.recommend_reason),
        duration_ms=duration_ms,
        success=True,
    )
    return result


@router.post("/feedback", summary="用户反馈回流（点赞/点踩/下单）")
async def feedback(payload: FeedbackIn, request: Request) -> dict[str, bool]:
    """把用户反馈写入 ai_eval_online 表，作为在线 Eval 集（真实 ground truth）。

    旁路写入：失败不阻断响应（反馈不应拖垮主流程），但生产前需建表。
    """
    from app.clients.db import aexecute

    user_id = request.headers.get("x-user-id", "anon")
    sql = (
        "INSERT INTO ai_eval_online "
        "(request_id, user_id, action, coach_id, feedback, created_at) "
        "VALUES (:request_id, :user_id, :action, :coach_id, :feedback, NOW())"
    )
    try:
        await aexecute(
            sql,
            {
                "request_id": payload.request_id,
                "user_id": user_id,
                "action": payload.action,
                "coach_id": payload.coach_id,
                "feedback": payload.feedback,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("反馈写入失败（不影响主流程，生产前需执行 sql/ai_eval_online.sql）：%s", exc)
    return {"ok": True}

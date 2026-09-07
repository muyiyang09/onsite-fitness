"""评价摘要路由。"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Header, Request

from app.clients.langfuse_client import observe_span, update_trace_meta
from app.config import settings
from app.core.audit import spawn_audit
from app.core.exceptions import UpstreamError, ValidationFailedError
from app.core.logging import request_id_var
from app.graphs.review_summary import REVIEW_SUMMARY_GRAPH
from app.schemas.review_summary import ReviewSummaryIn, ReviewSummaryResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ai", tags=["AI"])


@router.post(
    "/review-summary", response_model=ReviewSummaryResult, summary="评价摘要（教练优缺点 + 标签）"
)
@observe_span("api.review-summary")
async def review_summary(
    payload: ReviewSummaryIn,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> ReviewSummaryResult:
    if not settings.review_summary_enabled:
        raise ValidationFailedError("评价摘要 Agent 未启用")
    user_id = x_user_id or "anon"
    request_id = request_id_var.get()
    thread_id = f"review-{payload.coach_id}-{uuid4().hex}"
    update_trace_meta(
        user_id=user_id,
        session_id=thread_id,
        metadata={"request_id": request_id, "coach_id": payload.coach_id, "limit": payload.limit},
        tags=["review-summary"],
    )
    try:
        state_out = await REVIEW_SUMMARY_GRAPH.ainvoke(
            {"coach_id": payload.coach_id, "limit": payload.limit},
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("评价摘要执行失败：coach_id=%s", payload.coach_id)
        spawn_audit(
            user_id=user_id,
            request_id=request_id,
            action="review_summary",
            model=settings.llm_model,
            prompt=f"coach_id={payload.coach_id},limit={payload.limit}",
            success=False,
            error=str(exc)[:1000],
        )
        raise UpstreamError(f"评价摘要执行失败：{exc!r}") from exc

    result = ReviewSummaryResult.model_validate(state_out["result"])
    spawn_audit(
        user_id=user_id,
        request_id=request_id,
        action="review_summary",
        model=settings.llm_model,
        prompt=f"coach_id={payload.coach_id},limit={payload.limit}",
        response=result.summary,
        success=True,
    )
    return result

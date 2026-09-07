"""统一 AI 入口（Supervisor 路由）。"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.clients.langfuse_client import observe_span, update_trace_meta
from app.config import settings
from app.core.audit import spawn_audit
from app.core.exceptions import UpstreamError
from app.core.logging import request_id_var
from app.graphs.recommend_coach import RECOMMEND_GRAPH
from app.graphs.supervisor import route_query
from app.schemas.coach_recommend import RecommendResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ai", tags=["AI"])


class ChatIn(BaseModel):
    """统一 AI 入口请求（Supervisor 路由）。"""

    query: str = Field(..., min_length=1, max_length=500, description="用户自由文本")
    thread_id: str | None = Field(default=None, description="会话 ID（可选）")


@router.post("/chat", summary="统一 AI 入口（Supervisor 路由）")
@observe_span("api.chat")
async def chat(
    payload: ChatIn,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> dict[str, object]:
    """Supervisor 路由：推荐教练直接派发，评价/证书返回路由提示（走专用端点）。"""
    user_id = x_user_id or "anon"
    request_id = request_id_var.get()
    update_trace_meta(
        user_id=user_id,
        session_id=payload.thread_id,
        metadata={"request_id": request_id},
        tags=["supervisor"],
    )

    try:
        agent = await route_query(payload.query)
        if agent == "recommend_coach":
            state_out = await RECOMMEND_GRAPH.ainvoke(
                {"user_query": payload.query, "top_n": 3},
                config={"configurable": {"thread_id": payload.thread_id or f"chat-{uuid4().hex}"}},
            )
            result = RecommendResult.model_validate(state_out["result"]).model_dump()
            spawn_audit(
                user_id=user_id,
                request_id=request_id,
                action="chat_supervisor",
                model=settings.llm_model,
                prompt=payload.query,
                response=f"agent={agent}",
                success=True,
            )
            return {"agent": agent, "result": result}

        hint = "请调用对应专用端点（/v1/ai/review-summary 或 /v1/ai/cert-review）"
        spawn_audit(
            user_id=user_id,
            request_id=request_id,
            action="chat_supervisor",
            model=settings.llm_model,
            prompt=payload.query,
            response=f"agent={agent},hint={hint}",
            success=True,
        )
        return {"agent": agent, "hint": hint}
    except Exception as exc:  # noqa: BLE001
        logger.exception("统一 AI 入口失败：query=%s", payload.query)
        spawn_audit(
            user_id=user_id,
            request_id=request_id,
            action="chat_supervisor",
            model=settings.llm_model,
            prompt=payload.query,
            success=False,
            error=str(exc)[:1000],
        )
        raise UpstreamError(f"统一 AI 入口失败：{exc!r}") from exc

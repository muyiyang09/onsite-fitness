"""证书审核路由（含 HITL resume / cancel）。"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Header, Request
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.clients.langfuse_client import observe_span, update_trace_meta
from app.config import settings
from app.core import hitl_state
from app.core.audit import spawn_audit
from app.core.exceptions import ConflictError, NotFoundError, UpstreamError, ValidationFailedError
from app.core.logging import request_id_var
from app.graphs.cert_review import CERT_REVIEW_GRAPH
from app.schemas.cert_review import CertReviewIn, CertReviewResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ai", tags=["AI"])


class ResumeIn(BaseModel):
    """HITL 审核单恢复请求。"""

    action: str = Field(..., description="管理员决定：approve / reject")


@router.post("/cert-review", summary="证书审核（OCR → 核验 → 风险评估；HITL 开启时返回 pending）")
@observe_span("api.cert-review")
async def cert_review(
    payload: CertReviewIn,
    request: Request,
    x_user_id: str | None = Header(default=None),
):
    if not settings.cert_review_enabled:
        raise ValidationFailedError("证书审核 Agent 未启用")
    user_id = x_user_id or "anon"
    request_id = request_id_var.get()
    prompt = f"coach_id={payload.coach_id},cert_type={payload.cert_type},cert_number={payload.cert_number}"
    thread_id = f"cert-{payload.coach_id}-{uuid4().hex}"
    update_trace_meta(
        user_id=user_id,
        session_id=thread_id,
        metadata={
            "request_id": request_id,
            "coach_id": payload.coach_id,
            "cert_type": payload.cert_type,
        },
        tags=["cert-review"],
    )
    try:
        state_out = await CERT_REVIEW_GRAPH.ainvoke(
            {
                "coach_id": payload.coach_id,
                "cert_type": payload.cert_type,
                "cert_number": payload.cert_number,
                "holder_name": payload.holder_name,
                "image_url": payload.image_url,
            },
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("证书审核执行失败：coach_id=%s", payload.coach_id)
        spawn_audit(
            user_id=user_id,
            request_id=request_id,
            action="cert_review",
            model=settings.llm_model,
            prompt=prompt,
            success=False,
            error=str(exc)[:1000],
        )
        raise UpstreamError(f"证书审核执行失败：{exc!r}") from exc

    # HITL 开启时：interrupt 暂停，返回 pending + thread_id，等管理员 resume
    if "__interrupt__" in state_out:
        interrupt = [
            i.get("value") if isinstance(i, dict) else str(i) for i in state_out["__interrupt__"]
        ]
        await hitl_state.set_status(thread_id, hitl_state._PENDING)
        spawn_audit(
            user_id=user_id,
            request_id=request_id,
            action="cert_review",
            model=settings.llm_model,
            prompt=prompt,
            response=f"thread_id={thread_id},interrupt={interrupt}",
            success=True,
        )
        return {
            "status": "pending",
            "thread_id": thread_id,
            "interrupt": interrupt,
        }

    result = CertReviewResult.model_validate(state_out["result"])
    spawn_audit(
        user_id=user_id,
        request_id=request_id,
        action="cert_review",
        model=settings.llm_model,
        prompt=prompt,
        response=f"risk={result.risk_level},suggestion={result.suggestion}",
        success=True,
    )
    return result


@router.post("/cert-review/{thread_id}/resume", summary="HITL 人工确认（approve / reject）")
@observe_span("api.cert-review-resume")
async def resume_cert_review(
    thread_id: str,
    payload: ResumeIn,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> CertReviewResult:
    if not settings.hitl_enabled:
        raise ValidationFailedError("HITL 未启用")
    user_id = x_user_id or "anon"
    request_id = request_id_var.get()
    # resume 与首次审核共用 session_id=thread_id，trace 树上能看到 interrupt 前后全链路
    update_trace_meta(
        user_id=user_id,
        session_id=thread_id,
        metadata={"request_id": request_id, "action": payload.action},
        tags=["cert-review", "hitl"],
    )

    # 冲突检测：已处理过 / 已取消 → 拒绝重复 resume
    status = await hitl_state.get_status(thread_id)
    if hitl_state.is_terminal(status):
        raise ConflictError("该审核单已处理过")
    if status is None:
        raise NotFoundError("审核单不存在或已过期")

    try:
        state_out = await CERT_REVIEW_GRAPH.ainvoke(
            Command(resume={"action": payload.action}),
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("证书审核 resume 失败：thread_id=%s", thread_id)
        spawn_audit(
            user_id=user_id,
            request_id=request_id,
            action="cert_review_resume",
            model=settings.llm_model,
            prompt=f"thread_id={thread_id},action={payload.action}",
            success=False,
            error=str(exc)[:1000],
        )
        raise UpstreamError(f"证书审核 resume 失败：{exc!r}") from exc

    result = CertReviewResult.model_validate(state_out["result"])
    await hitl_state.set_status(thread_id, payload.action)
    spawn_audit(
        user_id=user_id,
        request_id=request_id,
        action="cert_review_resume",
        model=settings.llm_model,
        prompt=f"thread_id={thread_id},action={payload.action}",
        response=f"risk={result.risk_level},suggestion={result.suggestion}",
        success=True,
    )
    return result


@router.post("/cert-review/{thread_id}/cancel", summary="HITL 取消审核单")
async def cancel_cert_review(
    thread_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> dict[str, object]:
    if not settings.hitl_enabled:
        raise ValidationFailedError("HITL 未启用")
    user_id = x_user_id or "anon"
    request_id = request_id_var.get()
    await hitl_state.set_status(thread_id, "cancelled")
    spawn_audit(
        user_id=user_id,
        request_id=request_id,
        action="cert_review_cancel",
        model=settings.llm_model,
        prompt=f"thread_id={thread_id}",
        response="status=cancelled",
        success=True,
    )
    return {"ok": True, "thread_id": thread_id, "status": "cancelled"}

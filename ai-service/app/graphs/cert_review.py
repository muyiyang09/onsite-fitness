"""证书审核 Agent（#08-B）：ReAct + HITL。

业务：教练入驻上传证书（国职/国际/急救证），管理端审核。流程：
  OCR 识别 → 抽取关键字段 → 核验（编号格式/有效期/姓名）→ 风险评估 → 管理员最终确认(HITL)。

范式选择（为什么 ReAct + HITL，见 #08 §2.2）：
  - 核验步骤天然是「LLM 自主决定调哪些核验工具」的探索性任务，适合 ReAct；
  - 最终「通过/拒绝」影响资质合规，必须 HITL 人工兜底（interrupt + Checkpointer）。

当前落地：核验用确定性规则（编号格式/有效期/姓名），预留 ReAct 工具循环位；
HITL 用 interrupt 但默认关闭（hitl_enabled=False），打开后需配合 resume 端点。
"""

from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from langgraph.types import interrupt

from app.clients.circuit_breaker import llm_breaker
from app.clients.llm import achat_structured, is_mock_mode
from app.clients.trace import trace_node
from app.config import settings
from app.core.checkpoint import build_checkpointer
from app.graphs.base import END, START, ConditionalRouter, StateGraph
from app.schemas.cert_review import CertificateFields, VerificationItem

logger = logging.getLogger(__name__)

# 编号格式（mock 规则）：类型前缀 + 6 位数字
_CERT_PREFIX = {"国职": "GZ", "国际认证": "INT", "急救证": "FA"}


class CertReviewState(TypedDict, total=False):
    coach_id: int
    cert_type: str
    cert_number: str
    holder_name: str
    image_url: str
    fields: dict[str, Any]  # CertificateFields.model_dump()
    verifications: list[dict[str, Any]]
    risk_level: str  # low/medium/high
    suggestion: str  # approve/reject/manual_review
    result: dict[str, Any]  # CertReviewResult.model_dump()
    route: str
    used_mock: bool


@trace_node("ocr")
async def ocr(state: CertReviewState) -> dict[str, Any]:
    """Node 1（OCR）：识别证书文字。mock 模式下直接用入参（无真实 OCR）。"""
    # 未来：调 PaddleOCR / 云 OCR；当前 mock 直接透传入参
    logger.info("[Cert OCR] 识别证书（mock）：%s", state.get("cert_type"))
    return {"used_mock": is_mock_mode()}


@trace_node("extract_fields")
async def extract_fields(state: CertReviewState) -> dict[str, Any]:
    """Node 2（抽取字段）：从 OCR 文本抽结构化字段。mock 直接用入参。"""
    if is_mock_mode():
        fields = CertificateFields(
            cert_type=state.get("cert_type") or "",
            cert_number=state.get("cert_number") or "",
            holder_name=state.get("holder_name") or "",
        ).model_dump()
    else:
        from app.prompts.loader import load_prompt

        try:
            obj = await llm_breaker.call(
                achat_structured,
                [
                    {"role": "system", "content": load_prompt("cert_extract_fields")},
                    {
                        "role": "user",
                        "content": (
                            f"证书类型：{state.get('cert_type')}\n证书编号：{state.get('cert_number')}\n"
                            f"持有人：{state.get('holder_name')}"
                        ),
                    },
                ],
                CertificateFields,
            )
            fields = obj.model_dump()
        except Exception as exc:  # noqa: BLE001
            logger.warning("字段抽取失败，用入参兜底：%s", exc)
            fields = CertificateFields(
                cert_type=state.get("cert_type") or "",
                cert_number=state.get("cert_number") or "",
                holder_name=state.get("holder_name") or "",
            ).model_dump()
    return {"fields": fields}


@trace_node("verify")
async def verify(state: CertReviewState) -> dict[str, Any]:
    """Node 3（核验）：确定性规则核验（编号格式/有效期/姓名）。预留 ReAct 工具循环位。"""
    fields = state.get("fields") or {}
    cert_type = fields.get("cert_type") or state.get("cert_type") or ""
    number = fields.get("cert_number") or state.get("cert_number") or ""
    holder = fields.get("holder_name") or state.get("holder_name") or ""

    prefix = _CERT_PREFIX.get(cert_type, "")
    number_ok = bool(prefix) and bool(re.fullmatch(rf"{prefix}\d{{6,}}", number or ""))
    expiry = fields.get("expiry_date")
    expiry_ok = True
    if expiry:
        expiry_ok = str(expiry) >= "2026-08-27"  # 简化：有效期未过（真实场景查当前日期）
    name_ok = bool(holder and len(holder) >= 2)

    verifications = [
        VerificationItem(
            check="编号格式",
            passed=number_ok,
            detail=f"期望前缀 {prefix}+6位数字" if not number_ok else "格式正确",
        ).model_dump(),
        VerificationItem(
            check="有效期", passed=expiry_ok, detail="已过期" if not expiry_ok else "有效期内"
        ).model_dump(),
        VerificationItem(
            check="姓名匹配", passed=name_ok, detail="姓名有效" if name_ok else "姓名缺失"
        ).model_dump(),
    ]
    logger.info("[Cert Verify] 核验完成：%s", [v["passed"] for v in verifications])
    return {"verifications": verifications}


@trace_node("risk_assess")
async def risk_assess(state: CertReviewState) -> dict[str, Any]:
    """Node 4（风险评估）：根据核验结果定风险等级 + 建议。"""
    verifications = state.get("verifications") or []
    failed = [v for v in verifications if not v.get("passed")]

    if any(v.get("check") in ("编号格式", "有效期") and not v.get("passed") for v in verifications):
        risk_level, suggestion = "high", "reject"
    elif failed:
        risk_level, suggestion = "medium", "manual_review"
    else:
        risk_level, suggestion = "low", "approve"

    logger.info("[Cert Risk] 风险=%s 建议=%s", risk_level, suggestion)
    return {"risk_level": risk_level, "suggestion": suggestion}


@trace_node("hitl")
async def hitl_checkpoint(state: CertReviewState) -> dict[str, Any]:
    """Node 5（HITL）：人工最终确认 + 组装最终结果。

    默认关闭（hitl_enabled=False）：直接按 Agent 建议出结果；
    打开后：interrupt 暂停，管理员通过 /resume 提交决定后恢复。
    """
    if settings.hitl_enabled:
        decision = interrupt(
            {
                "prompt": f"证书审核人工确认（风险等级：{state.get('risk_level')}）",
                "fields": state.get("fields"),
                "verifications": state.get("verifications"),
                "suggestion": state.get("suggestion"),
            }
        )
        if decision.get("action") == "reject":
            state = {**state, "suggestion": "reject"}
        else:
            state = {**state, "suggestion": decision.get("action", state.get("suggestion"))}

    return {"route": "done", "result": _build_result(state)}


def _build_result(state: CertReviewState) -> dict[str, Any]:
    from app.schemas.cert_review import CertReviewResult

    return CertReviewResult(
        coach_id=int(state.get("coach_id") or 0),
        fields=CertificateFields.model_validate(state.get("fields") or {}),
        verifications=[
            VerificationItem.model_validate(v) for v in (state.get("verifications") or [])
        ],
        risk_level=state.get("risk_level") or "low",
        suggestion=state.get("suggestion") or "manual_review",
        used_mock=bool(state.get("used_mock")) or is_mock_mode(),
    ).model_dump()


_builder = StateGraph(CertReviewState)
_builder.add_node("ocr", ocr)
_builder.add_node("extract_fields", extract_fields)
_builder.add_node("verify", verify)
_builder.add_node("risk_assess", risk_assess)
_builder.add_node("hitl", hitl_checkpoint)
_builder.add_edge(START, "ocr")
_builder.add_edge("ocr", "extract_fields")
_builder.add_edge("extract_fields", "verify")
_builder.add_edge("verify", "risk_assess")
_builder.add_edge("risk_assess", "hitl")
_router = ConditionalRouter(state_field="route", mapping={"done": END}, default=END)
_builder.add_conditional_edges("hitl", _router.route, _router.edges())

CERT_REVIEW_GRAPH = _builder.compile(checkpointer=build_checkpointer())

__all__ = ["CertReviewState", "CERT_REVIEW_GRAPH", "_build_result"]

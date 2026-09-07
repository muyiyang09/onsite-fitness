"""评价摘要 Agent（#08-A）：Plan-and-Execute + Reflection。

业务：教练列表页 / 详情页展示「用户评价摘要」——人工读几百条评价不现实，
让 Agent 批量处理 → 总结优缺点 + 标签化。

范式选择（为什么 Plan-and-Execute + Reflection，见 #08 §1.2 / #02 §4）：
  长任务（评价可能上百条）先规划分批 → 并行 Map 打标签 → Reduce 聚合 → 自评质量门控。
  Reflection 用「规则门控」（长度/覆盖正负/含数据），不用 LLM 自评——能省一次 LLM 调用。

当前数据：MySQL 尚无 review 表，AI_MOCK_DB / 无数据时用内置 mock 评价兜底；
真实评价表落地后改 fetch_reviews 即可（#07 工具层预留了 fetch_reviews 工具位）。
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from app.clients.circuit_breaker import llm_breaker
from app.clients.llm import achat, is_mock_mode
from app.clients.trace import trace_node
from app.core.checkpoint import build_checkpointer
from app.graphs.base import END, START, ConditionalRouter, StateGraph
from app.prompts.loader import load_prompt
from app.schemas.review_summary import ReviewSummaryResult
from app.tools.review_cert_tools import fetch_reviews

logger = logging.getLogger(__name__)

MAX_REFINE = 2  # 摘要质量不达标的重写次数
SUMMARY_MAX_LEN = 200  # 摘要长度上限（字）

_POS_WORDS = ("专业", "好", "到位", "推荐", "耐心", "认真", "满意", "值", "明显")
_NEG_WORDS = ("迟到", "不", "差", "慢", "麻烦", "敷衍", "改期")


class ReviewSummaryState(TypedDict, total=False):
    coach_id: int
    limit: int
    reviews: list[dict[str, Any]]  # 原始评价 [{content, rating}]
    sentiment: dict[str, int]  # {positive/negative/neutral: 条数}
    positive_tags: list[str]
    negative_tags: list[str]
    summary: str
    result: dict[str, Any]  # ReviewSummaryResult.model_dump()
    route: str  # ConditionalRouter 分支 key
    reason_attempts: int  # 摘要重写次数
    reason_feedback: str
    used_mock: bool


def _classify(text: str) -> str:
    """规则分类情感（mock 用；真实 LLM 下可换成 LLM 打标）。"""
    if any(w in text for w in _NEG_WORDS):
        return "negative"
    if any(w in text for w in _POS_WORDS):
        return "positive"
    return "neutral"


@trace_node("plan")
async def plan(state: ReviewSummaryState) -> dict[str, Any]:
    """Node 1（Plan）：取评价 + 规划。真读 coach_review，无数据回退 mock。"""
    coach_id = int(state.get("coach_id") or 0)
    reviews = await fetch_reviews(coach_id, int(state.get("limit") or 30))
    logger.info("[Review Plan] coach=%d 取 %d 条评价", coach_id, len(reviews))
    return {"coach_id": coach_id, "reviews": reviews, "used_mock": is_mock_mode()}


@trace_node("map")
async def map_reviews(state: ReviewSummaryState) -> dict[str, Any]:
    """Node 2（Map）：批量打标签（情感 + 关键词）。规则版，真实场景可换 LLM 并行。"""
    reviews = state.get("reviews") or []
    sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    pos_tags: list[str] = []
    neg_tags: list[str] = []
    for r in reviews:
        text = r.get("content", "") if isinstance(r, dict) else str(r)
        s = _classify(text)
        sentiment[s] += 1
        if s == "negative":
            neg_tags.append(text)
        else:
            pos_tags.append(text)
    logger.info("[Review Map] 情感分布=%s", sentiment)
    return {"sentiment": sentiment, "positive_tags": pos_tags, "negative_tags": neg_tags}


@trace_node("reduce")
async def reduce_summary(state: ReviewSummaryState) -> dict[str, Any]:
    """Node 3（Reduce）：聚合正负标签 → 生成摘要（LLM / mock 模板）。"""
    sentiment = state.get("sentiment") or {}
    pos = state.get("positive_tags") or []
    neg = state.get("negative_tags") or []
    reason_feedback = state.get("reason_feedback")

    if is_mock_mode():
        summary = _mock_summary(sentiment, pos, neg)
    else:
        brief = (
            f"正向评价 {sentiment.get('positive', 0)} 条，负面 {sentiment.get('negative', 0)} 条。\n"
            f"正向：{'；'.join(pos[:3])}\n负面：{'；'.join(neg[:3])}"
        )
        user = f"请为教练总结评价摘要（含优缺点 + 数据支撑，200 字内）：\n{brief}"
        if reason_feedback:
            user += f"\n\n【重写要求】上次摘要被拒：{reason_feedback}，请重写。"
        try:
            summary = await llm_breaker.call(
                achat,
                [
                    {"role": "system", "content": load_prompt("review_reduce_summary")},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("摘要 LLM 失败，回退 mock：%s", exc)
            summary = _mock_summary(sentiment, pos, neg)

    return {"summary": summary}


def _mock_summary(sentiment: dict[str, int], pos: list[str], neg: list[str]) -> str:
    p = sentiment.get("positive", 0)
    n = sentiment.get("negative", 0)
    pos_brief = "、".join([_extract_kw(t) for t in pos[:3]]) or "专业负责"
    neg_brief = "、".join([_extract_kw(t) for t in neg[:2]]) or "无明显负面"
    return (
        f"评价普遍称赞{pos_brief}（{p} 条正面）。负面集中在{neg_brief}（{n} 条），整体满意度较高。"
    )


def _extract_kw(text: str) -> str:
    for w in ("专业", "到位", "耐心", "态度好", "性价比高", "迟到", "改期"):
        if w in text:
            return w
    return "服务"


@trace_node("reflect")
async def reflect_quality(state: ReviewSummaryState) -> dict[str, Any]:
    """Node 4（Reflection）：质量门控——摘要长度/覆盖正负面，不合格回 reduce 重写。"""
    summary = state.get("summary") or ""
    attempts = int(state.get("reason_attempts") or 0)
    issue = _summary_issue(summary)
    if issue and attempts < MAX_REFINE:
        logger.info("[Review Reflect] 摘要不合格（%s），回 reduce 重写", issue)
        return {"route": "rewrite", "reason_attempts": attempts + 1, "reason_feedback": issue}

    result = ReviewSummaryResult(
        coach_id=int(state.get("coach_id") or 0),
        summary=summary,
        positive_tags=[_extract_kw(t) for t in (state.get("positive_tags") or [])][:5],
        negative_tags=[_extract_kw(t) for t in (state.get("negative_tags") or [])][:5],
        sentiment=state.get("sentiment") or {},
        used_mock=bool(state.get("used_mock")) or is_mock_mode(),
    )
    return {"route": "done", "result": result.model_dump()}


def _summary_issue(summary: str) -> str | None:
    if not (summary or "").strip():
        return "摘要为空"
    if len(summary) > SUMMARY_MAX_LEN:
        return f"摘要超过 {SUMMARY_MAX_LEN} 字"
    return None


_builder = StateGraph(ReviewSummaryState)
_builder.add_node("plan", plan)
_builder.add_node("map", map_reviews)
_builder.add_node("reduce", reduce_summary)
_builder.add_node("reflect", reflect_quality)
_builder.add_edge(START, "plan")
_builder.add_edge("plan", "map")
_builder.add_edge("map", "reduce")
_builder.add_edge("reduce", "reflect")
_router = ConditionalRouter(
    state_field="route", mapping={"rewrite": "reduce", "done": END}, default=END
)
_builder.add_conditional_edges("reflect", _router.route, _router.edges())

REVIEW_SUMMARY_GRAPH = _builder.compile(checkpointer=build_checkpointer())

__all__ = ["ReviewSummaryState", "REVIEW_SUMMARY_GRAPH"]

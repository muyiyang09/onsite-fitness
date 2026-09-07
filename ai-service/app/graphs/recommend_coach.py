"""教练推荐 Graph（LangGraph + LiteLLM + Pydantic）。

拓扑（带条件分支 + 循环，Phase 1 Loop 工程）：

  START → extract_intent ──► retrieve_and_rank ──┬─(route="reason")──► generate_reason ──┬─(route="done")──► END
                                                 │                                       │
                                                 └─(route="refine")─► relax_filters ─────┘  └─(route="rewrite")─► generate_reason (自循环)

  • Node 1（extract_intent）：LLM 抽取意图，失败自动重试（累加修正提示），耗尽回退 mock 规则。
  • Node 2（retrieve_and_rank）：SQL + 规则打分，空结果触发 refine 循环（确定性放宽过滤后重查）。
  • relax_filters：按优先级清掉 male_only→min_rating→level→city 等硬过滤条件，回 Node 2 重查。
  • Node 3（generate_reason）：生成推荐理由 + 质量门控（空/过长/无教练名 → 带反馈重写）。

设计要点：
  • Node 2 不调用 LLM，用「结构化条件 + 规则打分 + SQL」——
    这比让 LLM 在成百上千教练里选 Top3 更准、也便宜 10 倍。
  • 只有 Node 1（自然语言 → 条件）、Node 3（生成人话理由）才用 LLM。
  • 全程 Pydantic 强类型 + normalize 结构适配层，拒绝 LLM 漂移引发硬失败。
  • 所有循环都有 refine_count / reason_attempts 硬上限，保证图必终止。
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from app.clients.circuit_breaker import llm_breaker
from app.clients.hybrid import hybrid_match_scores
from app.clients.llm import achat, achat_structured, is_mock_mode
from app.clients.trace import trace_node
from app.core.checkpoint import build_checkpointer
from app.core.safety import wrap_user_input
from app.graphs.base import END, START, ConditionalRouter, StateGraph
from app.prompts.loader import load_prompt
from app.schemas.coach_recommend import (
    CoachCandidate,
    IntentExtraction,
    RecommendResult,
)
from app.tools.coach_tools import fetch_coaches, fetch_courses, fetch_slots

logger = logging.getLogger(__name__)

# =============================================================================
# Loop 工程（Phase 1）参数：循环/重试/门控的硬上限，保证图必终止。
# =============================================================================
MAX_INTENT_RETRIES = 3  # Node1 意图抽取失败重试次数
MAX_REFINE = 3  # Node2 空结果 → 放宽过滤的最大轮数
MAX_REASON_RETRIES = 2  # Node3 推荐理由质量不达标的重写次数
REASON_MAX_LEN = 120  # 推荐理由长度上限（字），超过即判质量不达标


# =============================================================================
# State：Graph 全局状态，每个节点读 state + 写回 dict（LangGraph 自动 merge）
# =============================================================================
class RecommendState(TypedDict, total=False):
    # 入参
    user_query: str  # 用户原始自然语言
    city_code_override: str  # 小程序端已知用户城市时可以强制覆盖，避免 LLM 抽错
    top_n: int  # 返回多少个教练，默认 3
    # 节点中间产物
    intent: dict[str, Any]  # Node 1 输出：IntentExtraction.model_dump()
    candidates: list[dict[str, Any]]  # Node 2 输出：list[CoachCandidate.model_dump()]
    matched_course: dict[str, Any]  # Node 2 输出：匹配课程 {name, price, category}
    over_budget: bool  # Node 2 输出：匹配课程是否超预算
    # 最终输出
    result: dict[str, Any]  # RecommendResult.model_dump()
    used_mock: bool  # 是否走了 mock 路径
    # Loop 控制字段（Phase 1）：条件路由 + 循环计数
    route: str  # ConditionalRouter 的分支 key（Node2/Node3 写回）
    intent_errors: list[str]  # Node1 每次抽取失败原因（累加修正提示）
    refine_count: int  # Node2 空结果后已放宽过滤的次数
    reason_attempts: int  # Node3 推荐理由已重写次数
    reason_feedback: str  # Node3 上次理由被拒原因（喂回重写）


# =============================================================================
# Node 1：用户自然语言 → 结构化筛选条件（IntentExtraction）
# =============================================================================
SYSTEM_NODE1 = load_prompt("recommend_node1_intent")


def _build_node1_system(errors: list[str]) -> str:
    """把历史失败原因拼进 Node1 system prompt，作为下一轮的修正提示。"""
    if not errors:
        return SYSTEM_NODE1
    tips = "\n".join(f"- {e}" for e in errors[-3:])  # 只带最近 3 条，防 prompt 膨胀
    return (
        SYSTEM_NODE1
        + "\n\n【重试提示】你之前的输出不合法，请严格输出符合 schema 的 JSON 并修正以下问题：\n"
        + tips
    )


async def _extract_intent_llm(user_query: str, errors: list[str]) -> dict[str, Any]:
    """Node1 的 LLM 抽取（含重试 + 修正提示累加）。失败抛异常，由 extract_intent 兜底 mock。

    分层（#05）：LiteLLM 内置 num_retries 处理 HTTP 重试 → 这里处理「格式/校验失败」的
    业务重试（累加修正提示）→ 最外层熔断器（连续失败快速失败）。
    """
    for attempt in range(1, MAX_INTENT_RETRIES + 1):
        try:
            intent_obj = await achat_structured(
                messages=[
                    {"role": "system", "content": _build_node1_system(errors)},
                    {"role": "user", "content": wrap_user_input(user_query)},
                ],
                output_schema=IntentExtraction,
            )
            return intent_obj.model_dump()
        except Exception as exc:  # noqa: BLE001
            msg = f"第 {attempt} 次失败：{exc}"
            errors.append(msg)
            logger.warning("[Recommend Node1] 意图抽取失败（%s）", msg)
    raise RuntimeError(f"意图抽取重试 {MAX_INTENT_RETRIES} 次仍失败")


@trace_node("extract_intent")
async def extract_intent(state: RecommendState) -> dict[str, Any]:
    """Node 1（异步）。LLM 抽取经熔断器 + 重试，耗尽后回退 mock 规则抽取。"""
    user_query = state.get("user_query") or ""
    city_override = state.get("city_code_override")
    used_mock = False
    errors: list[str] = list(state.get("intent_errors") or [])

    if is_mock_mode():
        logger.info("[Recommend Node1] Mock 模式：用规则抽取 fallback")
        intent = _mock_extract_intent(user_query)
        used_mock = True
    else:
        try:
            # 熔断器包裹「重试 + LLM」：LLM 连续失败到阈值后，后续请求快速失败，不再傻等 60s
            intent = await llm_breaker.call(_extract_intent_llm, user_query, errors)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Recommend Node1] LLM 抽取失败（可能已熔断），降级 mock：%s", exc)
            intent = _mock_extract_intent(user_query)
            used_mock = True

    # 小程序端如果已经知道城市（通过定位/用户配置），直接覆盖 LLM 结果，避免"我在朝阳"→ 城市被抽成别的
    if city_override:
        intent["city_name"] = city_override

    # 保证 specialization_tags 始终是 list
    intent.setdefault("specialization_tags", [])
    return {"intent": intent, "used_mock": used_mock, "intent_errors": errors}


# ---------------------------------------------------------------------------
# Mock 用的超简单关键词正则（离线 demo 专用）
# ---------------------------------------------------------------------------
def _mock_extract_intent(query: str) -> dict[str, Any]:
    q = (query or "").lower()
    d: dict[str, Any] = {
        "city_name": None,
        "district": None,
        "specialization": None,
        "specialization_tags": [],
        "level": None,
        "min_rating": None,
        "max_price": None,
        "time_slot": None,
        "male_only": None,
        "user_goal": query or None,
    }
    # 只做几个高命中关键词，作为离线演示
    if any(k in q for k in ("减脂", "减肥", "瘦", "燃脂", "塑形")):
        d["specialization"] = "减脂塑形"
        d["specialization_tags"].append("减脂")
    if any(k in q for k in ("增肌", "力量", "壮", "哑铃")):
        d["specialization"] = d["specialization"] or "增肌训练"
        d["specialization_tags"].append("增肌")
    if any(k in q for k in ("产后", "孕产", "修复")):
        d["specialization"] = "产后恢复"
        d["specialization_tags"].append("产后恢复")
    if any(k in q for k in ("拉伸", "放松", "康复", "疼痛")):
        d["specialization"] = d["specialization"] or "拉伸放松"
        d["specialization_tags"].append("拉伸")

    if "北京" in q:
        d["city_name"] = "北京市"
    if "望京" in q:
        d["district"] = "望京"
        d["city_name"] = d["city_name"] or "北京市"
    if "朝阳" in q:
        d["district"] = d["district"] or "朝阳区"
        d["city_name"] = d["city_name"] or "北京市"

    if "金牌" in q:
        d["level"] = 4
    if "高级" in q and d["level"] is None:
        d["level"] = 3

    # 价格：优先「预算 N」写法，否则找数字 + 元/块/以内/以下
    import re

    m = re.search(r"预算\s*(\d+)", q) or re.search(r"(\d+)\s*(?:元|块|以内|以下|/次|每次|一次)", q)
    if m:
        d["max_price"] = float(m.group(1))

    if any(k in q for k in ("周末", "周六", "周日")):
        d["time_slot"] = "周末"
    elif any(k in q for k in ("晚上", "下班后")):
        d["time_slot"] = "工作日晚上"
    return d


# =============================================================================
# Node 2：按结构化条件查教练库 + 规则打分（无 LLM，纯 SQL + 加权）
# =============================================================================
# 打分权重（价格维度已移除，见项目决策：价格在教练间无价差，原 25% 摊给评分/匹配）：
#   评分 40% / 语义匹配 35% / 等级 10% / 距离(半径) 10% / 档期 5%
_WEIGHTS: dict[str, float] = {
    "rating": 0.40,
    "match": 0.35,
    "level": 0.10,
    "distance": 0.10,
    "schedule": 0.05,
}

# 用户目标关键词 → 可匹配教练 bio 的同义/扩展词（用于子串匹配）
_SPEC_SYNONYMS: dict[str, list[str]] = {
    "减脂": ["减脂", "减肥", "瘦身", "燃脂", "体脂", "塑形"],
    "增肌": ["增肌", "增重", "力量", "体能", "健美"],
    "产后": ["产后", "孕产", "修复", "恢复"],
    "拉伸": ["拉伸", "放松", "筋膜", "松解"],
    "康复": ["康复", "运动康复", "理疗", "疼痛"],
    "体态": ["体态", "矫正", "姿态"],
    "青少年": ["青少年", "儿童", "少儿"],
}

# 数据获取（教练/课程/档期）已抽到 app/tools/coach_tools.py 作为可复用工具，
# 供多 Agent 共享 + MCP Server 对外暴露（#07 MCP 工具层）。


# ---------------------------------------------------------------------------
# 打分辅助：语义匹配 / 课程匹配 / 预算 / 档期 / 距离
# ---------------------------------------------------------------------------
def _expand_keywords(specialization: str | None, tags: list[str]) -> list[str]:
    """把用户的 specialization + tags 展开成可用于 bio 子串匹配的关键词集合。"""
    kws: list[str] = []
    for t in list(tags or []) + [specialization or ""]:
        t = (t or "").strip()
        if not t:
            continue
        kws.append(t)
        for canonical, synonyms in _SPEC_SYNONYMS.items():
            if canonical in t or any(s in t for s in synonyms):
                kws.extend(synonyms)
    seen: set[str] = set()
    out: list[str] = []
    for k in kws:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _match_bio_score(bio: str, keywords: list[str]) -> int:
    """0~100：用户目标关键词在教练 bio 里的命中程度。"""
    if not keywords:
        return 70  # 用户没目标，给中位分
    bio_l = (bio or "").lower()
    hits = [k for k in keywords if k.lower() in bio_l]
    if not hits:
        return 40  # 有关键词但都不命中：给低分，不直接剔除
    return min(100, 50 + 30 + min(20, (len(hits) - 1) * 10))


def _match_course(
    specialization: str | None, tags: list[str], courses: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """从课程目录挑一门最匹配用户目标的课（用于参考价 + 预算过滤）。"""
    if not courses:
        return None
    keywords = _expand_keywords(specialization, tags)
    best, best_hits = None, -1
    for c in courses:
        blob = f"{c.get('category', '')} {c.get('name', '')}".lower()
        hits = sum(1 for k in keywords if k.lower() in blob)
        if hits > best_hits:
            best, best_hits = c, hits
    if best_hits <= 0:
        # 无关键词命中时，取最便宜的一门（更保守、更贴合预算）
        return min(courses, key=lambda c: float(c.get("price") or 10**9))
    return best


def _apply_budget(
    matched: dict[str, Any] | None, max_price: float | None, courses: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, bool]:
    """预算过滤：优先挑「同类且预算内」的课；没有则保留原课并标记超预算。"""
    if matched is None:
        return None, False
    if max_price is None or float(matched.get("price") or 0) <= float(max_price):
        return matched, False
    cheaper = [
        c
        for c in courses
        if c.get("category") == matched.get("category")
        and float(c.get("price") or 0) <= float(max_price)
    ]
    if cheaper:
        return min(cheaper, key=lambda c: float(c["price"])), False
    return matched, True


def _time_bucket(time_slot: str | None) -> str | None:
    """把用户时段粗分成 morning/afternoon/evening；无法判断返回 None。"""
    if not time_slot:
        return None
    s = str(time_slot)
    if any(k in s for k in ("上午", "早上", "凌晨", "早晨")):
        return "morning"
    if any(k in s for k in ("下午", "中午")):
        return "afternoon"
    if any(k in s for k in ("晚上", "夜", "下班后")):
        return "evening"
    return None


def _slot_bucket(slot: str) -> str:
    """把 coach_schedule.time_slot（如 '09:00-10:00'）按开始小时粗分桶。"""
    try:
        hour = int(str(slot).split(":")[0])
    except (ValueError, IndexError):
        return "any"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _schedule_ratio(slots: list[str], bucket: str | None) -> float:
    """档期匹配比（0~1）。"""
    if bucket is None:
        return 1.0 if slots else 0.5  # 没指定时段：有档期给满，无档期给 0.5 兜底
    matched = [s for s in slots if _slot_bucket(s) == bucket]
    if matched:
        return 1.0
    return 0.6 if slots else 0.0  # 该时段没空但有其他档期给 0.6；完全无档期给 0


def _distance_score(service_radius_km: float) -> int:
    """无用户坐标，用服务半径近似「可达性」：半径越大越可能覆盖到用户。"""
    return min(100, int(float(service_radius_km or 0) / 15.0 * 100))


@trace_node("retrieve_and_rank")
async def retrieve_and_rank(state: RecommendState) -> dict[str, Any]:
    """Node 2（异步）：真读 MySQL（失败回退 mock）+ 5 维加权打分，返回 candidates + 匹配课程。"""
    intent = state.get("intent") or {}
    top_n = int(state.get("top_n") or 3)
    max_price = intent.get("max_price")
    min_level = intent.get("level")
    min_rating = intent.get("min_rating")
    city_name = intent.get("city_name")
    target_spec = intent.get("specialization")
    target_tags: list[str] = intent.get("specialization_tags") or []
    time_slot = intent.get("time_slot")
    male_only = intent.get("male_only")
    user_query = state.get("user_query") or ""  # 混合检索（#04）用原文做 BM25/向量召回

    # ---- 1. 取数据（教练 / 课程目录 / 档期）—— 走工具层（#07）----
    coaches = await fetch_coaches(city_name=city_name)
    courses = await fetch_courses()
    slots = await fetch_slots([c["coach_id"] for c in coaches])  # None=DB 不可用

    # ---- 2. 关键词 + 匹配课程 + 预算过滤 ----
    keywords = _expand_keywords(target_spec, target_tags)
    matched_course = _match_course(target_spec, target_tags, courses)
    matched_course, over_budget = _apply_budget(matched_course, max_price, courses)
    ref_price = float(matched_course["price"]) if matched_course else 0.0
    ref_course_name = matched_course.get("name") if matched_course else None
    spec_label = matched_course.get("category") if matched_course else target_spec

    # ---- 3. 硬过滤 ----
    filtered: list[dict[str, Any]] = []
    for c in coaches:
        if city_name and c.get("city_name") != city_name:
            continue
        if min_level is not None and int(c.get("level", 0)) < int(min_level):
            continue
        if min_rating is not None and float(c.get("rating", 0)) < float(min_rating):
            continue
        if male_only is True and c.get("sex") != "1":
            continue
        if male_only is False and c.get("sex") != "0":
            continue
        filtered.append(c)

    # 一个都没命中 → 触发 refine loop（确定性放宽后重查）；放宽耗尽才降级到全量兜底
    refine_count = int(state.get("refine_count") or 0)
    if not filtered and refine_count < MAX_REFINE:
        logger.info("[Recommend Node2] 硬过滤后候选为空，触发放宽（第 %d 轮）", refine_count + 1)
        return {
            "route": "refine",
            "candidates": [],
            "matched_course": matched_course,
            "over_budget": over_budget,
        }
    if not filtered:
        # 放宽耗尽仍为空：回退全量候选，保证至少给 top_n 个参考
        filtered = list(coaches)

    # ---- 4. 5 维打分 + 加权综合 ----
    bucket = _time_bucket(time_slot)

    # 混合检索（#04）：BM25(+向量)+RRF 算出的语义相关度 {coach_id: 0~1}，覆盖语义匹配维。
    # 不可用 / 无召回时返回 {}，下面逐教练退回 `_match_bio_score` 子串匹配，行为与 #03 一致。
    hybrid_scores = hybrid_match_scores(user_query, filtered)
    if hybrid_scores:
        logger.info(
            "[Recommend Node2] 混合检索命中 %d 位教练，语义匹配维切换为 BM25/RRF 相关度",
            len(hybrid_scores),
        )

    candidates: list[CoachCandidate] = []
    for c in filtered:
        cid = int(c["coach_id"])
        score_rating = int(float(c.get("rating") or 0) / 5.0 * 100)
        score_level = int(int(c.get("level") or 1) / 4.0 * 100)
        if cid in hybrid_scores:
            # 混合相关度（0~1）→ 0~100，替代子串匹配作为语义匹配分
            score_match = max(0, min(100, int(hybrid_scores[cid] * 100)))
        else:
            score_match = _match_bio_score(c.get("bio") or "", keywords)
        score_distance = _distance_score(c.get("service_radius_km") or 0)
        if slots is None:
            ratio = 1.0  # DB 不可用，档期一律按「有空」处理
        else:
            ratio = _schedule_ratio(slots.get(c["coach_id"], []), bucket)
        score_schedule = int(ratio * 100)

        total = (
            score_rating * _WEIGHTS["rating"]
            + score_match * _WEIGHTS["match"]
            + score_level * _WEIGHTS["level"]
            + score_distance * _WEIGHTS["distance"]
            + score_schedule * _WEIGHTS["schedule"]
        )

        candidates.append(
            CoachCandidate(
                coach_id=int(c["coach_id"]),
                name=c.get("name", ""),
                level=int(c.get("level") or 1),
                rating=float(c.get("rating") or 0),
                service_radius_km=float(c.get("service_radius_km") or 0),
                city_name=c.get("city_name") or "",
                bio=c.get("bio") or "",
                specialization=spec_label,
                course_name=ref_course_name,
                price=ref_price,
                distance_km_est=None,
                schedule_match_ratio=round(ratio, 2),
                score_rating=score_rating,
                score_level=score_level,
                score_match=score_match,
                score_distance=score_distance,
                score_schedule=score_schedule,
                score_total=round(total, 2),
            )
        )

    # ---- 5. 按综合分降序，取 Top N ----
    candidates.sort(key=lambda x: x.score_total, reverse=True)
    top = candidates[:top_n]
    return {
        "route": "reason",
        "candidates": [c.model_dump() for c in top],
        "matched_course": matched_course,
        "over_budget": over_budget,
    }


# =============================================================================
# Refine 节点：Node2 空结果 → 确定性放宽硬过滤条件 → 回 Node2 重查
# =============================================================================
@trace_node("relax_filters")
async def relax_filters(state: RecommendState) -> dict[str, Any]:
    """refine 节点（异步）：确定性放宽硬过滤条件，再回 retrieve_and_rank 重查。

    放宽顺序（按「越容易过度约束越先放」）：
      第 1 次：清性别(male_only) + 最低评分(min_rating)
      第 2 次：清等级(level)
      第 3 次及以后：清城市(city_name)
    """
    intent = dict(state.get("intent") or {})
    refine = int(state.get("refine_count") or 0) + 1
    if refine == 1:
        intent["male_only"] = None
        intent["min_rating"] = None
    elif refine == 2:
        intent["level"] = None
    else:
        intent["city_name"] = None
    logger.info(
        "[Recommend refine] 放宽过滤第 %d 轮：male_only=%s min_rating=%s level=%s city=%s",
        refine,
        intent.get("male_only"),
        intent.get("min_rating"),
        intent.get("level"),
        intent.get("city_name"),
    )
    return {"intent": intent, "refine_count": refine}


# =============================================================================
# Node 3：根据用户目标 + Top 教练，生成 2~3 句推荐理由（LLM）
# =============================================================================
SYSTEM_NODE3 = load_prompt("recommend_node3_reason")


def _mock_generate_reason(
    intent: dict[str, Any],
    candidates: list[dict[str, Any]],
    matched_course: dict[str, Any] | None = None,
    over_budget: bool = False,
) -> str:
    goal = intent.get("user_goal") or "找合适的教练"
    names = "、".join([c.get("name", "?") for c in candidates[:2]]) or "推荐的几位教练"
    course_txt = ""
    if matched_course:
        course_txt = (
            f"匹配课程「{matched_course.get('name')}」¥{float(matched_course.get('price') or 0):.0f}"
            + ("，略超你的预算" if over_budget else "，在你预算内")
        )
    return (
        f"针对你的目标「{goal}」，推荐先约 {names} 试试。"
        f"{course_txt}。几位教练评分高、擅长领域匹配，体验风险低。"
    )


def _reason_quality_issue(reason: str, candidates: list[dict[str, Any]]) -> str | None:
    """推荐理由质量门控：返回 None 表示合格，否则返回「不合格原因」。

    判定：空 / 超过长度上限 / 没提到任何候选教练姓名。
    """
    reason = (reason or "").strip()
    if not reason:
        return "推荐理由为空"
    if len(reason) > REASON_MAX_LEN:
        return f"推荐理由超过 {REASON_MAX_LEN} 字（当前 {len(reason)} 字）"
    names = [c.get("name") for c in (candidates or [])]
    if names and not any(n and n in reason for n in names):
        return "推荐理由没有提到任何候选教练姓名"
    return None


@trace_node("generate_reason")
async def generate_reason(state: RecommendState) -> dict[str, Any]:
    """Node 3（异步）：生成推荐理由 + 质量门控（不达标带反馈重写）+ 组装最终 RecommendResult。"""
    user_query = state.get("user_query") or ""
    intent = state.get("intent") or {}
    candidates_dicts: list[dict[str, Any]] = state.get("candidates") or []
    matched_course = state.get("matched_course")
    over_budget = bool(state.get("over_budget"))
    used_mock = bool(state.get("used_mock")) or is_mock_mode()
    reason_attempts = int(state.get("reason_attempts") or 0)
    reason_feedback = state.get("reason_feedback")

    # 先把 candidates 还原成 Pydantic（保证结构合法）
    candidates_objs: list[CoachCandidate] = [
        CoachCandidate.model_validate(c) for c in candidates_dicts
    ]

    if used_mock:
        reason = _mock_generate_reason(intent, candidates_dicts, matched_course, over_budget)
    else:
        top_coaches_brief = (
            "\n".join(
                [
                    f"- {c.name}（{['初', '中', '高', '金'][c.level - 1]}牌，评分{c.rating}，"
                    f"擅长：{c.bio or c.specialization or '未填写'}，参考课 ¥{c.price:.0f}，综合分{c.score_total:.1f}）"
                    for c in candidates_objs
                ]
            )
            or "（无候选）"
        )
        user = f"用户目标：{intent.get('user_goal') or user_query}"
        if reason_feedback:
            user += f"\n\n【重写要求】上次推荐理由被拒，原因：{reason_feedback}。请针对该问题重写。"
        try:
            # 熔断器包裹 LLM 生成：连续失败快速失败，避免每次傻等超时
            reason = await llm_breaker.call(
                achat,
                [
                    {"role": "system", "content": SYSTEM_NODE3},
                    {"role": "user", "content": f"{user}\n\n候选教练：\n{top_coaches_brief}"},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Node3 推荐理由 LLM 失败，回退 mock：%s", exc)
            reason = _mock_generate_reason(intent, candidates_dicts, matched_course, over_budget)
            used_mock = True

    # ---- 质量门控：不达标且未超重试上限 → 回本节点重写（self-loop）----
    issue = _reason_quality_issue(reason, candidates_dicts)
    if issue is not None and reason_attempts < MAX_REASON_RETRIES:
        logger.info(
            "[Recommend Node3] 理由质量不达标（%s），触发第 %d 次重写",
            issue,
            reason_attempts + 1,
        )
        return {
            "route": "rewrite",
            "reason_attempts": reason_attempts + 1,
            "reason_feedback": issue,
            "used_mock": used_mock,
        }
    if issue is not None:
        # 重写耗尽仍不达标：回退 mock 模板（确定性可接受，保证终止）
        logger.warning(
            "[Recommend Node3] 理由重写 %d 次仍不达标，回退 mock 模板", MAX_REASON_RETRIES
        )
        reason = _mock_generate_reason(intent, candidates_dicts, matched_course, over_budget)
        used_mock = True

    # ---- 组装最终结果 ----
    result_obj = RecommendResult(
        user_query=user_query,
        intent=IntentExtraction.model_validate(intent),
        candidates=candidates_objs,
        coach_ids=[c.coach_id for c in candidates_objs],
        recommend_reason=reason,
        matched_course_name=(matched_course.get("name") if matched_course else None),
        matched_course_price=(float(matched_course["price"]) if matched_course else None),
        over_budget=over_budget,
        used_mock=used_mock,
    )
    return {"route": "done", "result": result_obj.model_dump(), "used_mock": used_mock}


# =============================================================================
# Graph 编译
# =============================================================================
_builder = StateGraph(RecommendState)
_builder.add_node("extract_intent", extract_intent)
_builder.add_node("retrieve_and_rank", retrieve_and_rank)
_builder.add_node("relax_filters", relax_filters)
_builder.add_node("generate_reason", generate_reason)

_builder.add_edge(START, "extract_intent")
_builder.add_edge("extract_intent", "retrieve_and_rank")

# Node2 → 空结果走 refine 循环，有结果走理由生成
_router_retrieve = ConditionalRouter(
    state_field="route",
    mapping={"refine": "relax_filters", "reason": "generate_reason"},
    default="generate_reason",
)
_builder.add_conditional_edges(
    "retrieve_and_rank", _router_retrieve.route, _router_retrieve.edges()
)
_builder.add_edge("relax_filters", "retrieve_and_rank")

# Node3 → 质量不达标回本节点重写，达标才结束
_router_reason = ConditionalRouter(
    state_field="route",
    mapping={"rewrite": "generate_reason", "done": END},
    default=END,
)
_builder.add_conditional_edges("generate_reason", _router_reason.route, _router_reason.edges())

RECOMMEND_GRAPH = _builder.compile(checkpointer=build_checkpointer())
"""对外的推荐图。使用方式：

    from app.graphs.recommend_coach import RECOMMEND_GRAPH
    state_out = RECOMMEND_GRAPH.invoke(
        {
            "user_query": "我家住望京，预算 200 以内，想产后恢复",
            "top_n": 3,
        },
        config={"configurable": {"thread_id": "demo-1"}},  # checkpointer 要求 thread_id
    )
    result = RecommendResult.model_validate(state_out["result"])
"""


__all__ = [
    "RecommendState",
    "RECOMMEND_GRAPH",
    "extract_intent",
    "retrieve_and_rank",
    "relax_filters",
    "generate_reason",
]

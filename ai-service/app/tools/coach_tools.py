"""教练相关工具（#07 MCP 工具层）：数据查询 + 混合检索，注册到全局工具表。

把原来散在 recommend_coach.py 里的数据获取逻辑抽到这里，做成「可复用工具」，
供推荐 Agent、未来的评价摘要/证书审核 Agent 共享，也供 MCP Server 对外暴露。
"""

from __future__ import annotations

import logging
from typing import Any

from app.clients import bm25, reranker, vectorstore
from app.clients.db import afetch_all
from app.clients.llm import is_mock_db
from app.tools.registry import TOOL_REGISTRY, Tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 本地假数据（离线兜底，与 SQL 种子保持一致）
# ---------------------------------------------------------------------------
_MOCK_COACHES: list[dict[str, Any]] = [
    {
        "coach_id": 1,
        "name": "李教练",
        "sex": "1",
        "level": 4,
        "rating": 4.9,
        "service_radius_km": 8.0,
        "city_name": "北京市",
        "bio": "国职认证，专注减脂塑形 8 年",
    },
    {
        "coach_id": 2,
        "name": "王教练",
        "sex": "2",
        "level": 3,
        "rating": 4.8,
        "service_radius_km": 5.0,
        "city_name": "北京市",
        "bio": "擅长增肌与体能训练",
    },
    {
        "coach_id": 3,
        "name": "张教练",
        "sex": "1",
        "level": 2,
        "rating": 4.7,
        "service_radius_km": 10.0,
        "city_name": "北京市",
        "bio": "运动康复方向，产后恢复经验丰富",
    },
]

_MOCK_COURSES: list[dict[str, Any]] = [
    {"category": "减脂塑形", "name": "上门减脂私教课", "price": 199.0},
    {"category": "增肌训练", "name": "上门增肌训练课", "price": 229.0},
    {"category": "拉伸放松", "name": "拉伸放松课", "price": 129.0},
]


def _normalize_coach(c: dict[str, Any]) -> dict[str, Any]:
    """把 DB 行 / mock 行统一成下游用到的 coach 结构。"""
    return {
        "coach_id": int(c.get("coach_id", c.get("id"))),
        "name": c.get("name", ""),
        "sex": c.get("sex"),
        "level": int(c.get("level") or 1),
        "rating": float(c.get("rating") or 0),
        "service_radius_km": float(c.get("service_radius_km") or 0),
        "city_name": c.get("city_name") or "",
        "bio": c.get("bio") or "",
    }


# ---------------------------------------------------------------------------
# 工具实现（异步，统一 kwargs 入参）
# ---------------------------------------------------------------------------
async def fetch_coaches(
    city_name: str | None = None, level_min: int | None = None
) -> list[dict[str, Any]]:
    """取「已审核正常(status=1)」教练；AI_MOCK_DB / MySQL 失败回退 mock。"""
    if is_mock_db():
        coaches = [_normalize_coach(c) for c in _MOCK_COACHES]
    else:
        try:
            sql = (
                "SELECT id, name, sex, level, rating, service_radius_km, city_code, city_name, bio "
                "FROM coach WHERE status = 1"
            )
            params: dict[str, Any] = {}
            if city_name:
                sql += " AND city_name = :city_name"
                params["city_name"] = city_name
            if level_min is not None:
                sql += " AND level >= :level_min"
                params["level_min"] = int(level_min)
            rows = await afetch_all(sql, params)
            if rows:
                coaches = [_normalize_coach(r) for r in rows]
            else:
                coaches = [_normalize_coach(c) for c in _MOCK_COACHES]
        except Exception as exc:  # noqa: BLE001
            logger.warning("MySQL 教练查询失败，回退 mock：%s", exc)
            coaches = [_normalize_coach(c) for c in _MOCK_COACHES]

    # mock 模式同样应用 level 过滤，保证行为一致
    if level_min is not None:
        coaches = [c for c in coaches if int(c.get("level", 0)) >= int(level_min)]
    return coaches


async def fetch_courses() -> list[dict[str, Any]]:
    """课程目录（course JOIN category）。失败回退 mock。"""
    if is_mock_db():
        return list(_MOCK_COURSES)
    try:
        sql = (
            "SELECT c.name AS name, c.price AS price, cat.name AS category "
            "FROM course c LEFT JOIN category cat ON c.category_id = cat.id "
            "WHERE c.status = 1 AND cat.type = 1"
        )
        rows = await afetch_all(sql)
        if rows:
            return [
                {
                    "name": r.get("name"),
                    "price": float(r.get("price") or 0),
                    "category": r.get("category") or "",
                }
                for r in rows
            ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("MySQL 课程目录查询失败，回退 mock：%s", exc)
    return list(_MOCK_COURSES)


async def fetch_slots(coach_ids: list[int]) -> dict[int, list[str]] | None:
    """每个教练「未来可约」时段 {coach_id: [time_slot,...]}；失败返回 None。"""
    if is_mock_db():
        return {int(c["coach_id"]): ["09:00-10:00"] for c in _MOCK_COACHES}
    if not coach_ids:
        return {}
    try:
        placeholders = ", ".join(str(int(i)) for i in coach_ids)
        sql = (
            "SELECT coach_id, time_slot FROM coach_schedule "
            f"WHERE status = 1 AND schedule_date >= CURDATE() AND coach_id IN ({placeholders})"
        )
        rows = await afetch_all(sql)
        slots: dict[int, list[str]] = {}
        for r in rows:
            slots.setdefault(int(r["coach_id"]), []).append(r["time_slot"])
        return slots
    except Exception as exc:  # noqa: BLE001
        logger.warning("MySQL 排期查询失败，档期按默认处理：%s", exc)
        return None


async def bm25_search(query: str, top_k: int = 50) -> list[tuple[int, float]]:
    """BM25 关键词召回。返回 [(coach_id, score)]。"""
    return bm25.search(query, top_k)


async def vector_search(query: str, top_k: int = 50) -> list[tuple[int, float]]:
    """向量语义召回。返回 [(coach_id, similarity)]。轻量模式下返回 []。"""
    return vectorstore.search(query, top_k)


async def rerank_docs(
    query: str, docs: list[dict[str, Any]], top_n: int = 3
) -> list[dict[str, Any]]:
    """Cross-Encoder 重排。docs: [{"coach_id":.., "text":..}]。轻量模式下原样返回。"""
    return reranker.rerank(query, docs, top_n)


# ---------------------------------------------------------------------------
# 注册工具到全局注册表
# ---------------------------------------------------------------------------
def _register() -> None:
    TOOL_REGISTRY.register(
        Tool(
            name="fetch_coaches",
            description="按城市/最低等级查询已审核教练列表，返回 coach_id/name/level/rating/bio 等",
            input_schema={
                "type": "object",
                "properties": {
                    "city_name": {"type": "string", "description": "城市名，如 '北京市'"},
                    "level_min": {"type": "integer", "description": "最低等级 1-4"},
                },
            },
            handler=fetch_coaches,
        )
    )
    TOOL_REGISTRY.register(
        Tool(
            name="fetch_courses",
            description="查询课程目录（课程名/价格/分类）",
            input_schema={"type": "object", "properties": {}},
            handler=fetch_courses,
        )
    )
    TOOL_REGISTRY.register(
        Tool(
            name="bm25_search",
            description="BM25 关键词召回教练，返回 [(coach_id, score)]",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 50},
                },
                "required": ["query"],
            },
            handler=bm25_search,
        )
    )
    TOOL_REGISTRY.register(
        Tool(
            name="vector_search",
            description="向量语义召回教练，返回 [(coach_id, similarity)]",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 50},
                },
                "required": ["query"],
            },
            handler=vector_search,
        )
    )
    TOOL_REGISTRY.register(
        Tool(
            name="rerank_docs",
            description="Cross-Encoder 重排候选文档，返回精排后的 top N",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "docs": {"type": "array", "items": {"type": "object"}},
                    "top_n": {"type": "integer", "default": 3},
                },
                "required": ["query", "docs"],
            },
            handler=rerank_docs,
        )
    )


_register()

__all__ = [
    "fetch_coaches",
    "fetch_courses",
    "fetch_slots",
    "bm25_search",
    "vector_search",
    "rerank_docs",
]

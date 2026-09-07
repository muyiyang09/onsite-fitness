"""评价 / 证书数据工具（#08 数据侧落地）。

把评价摘要、证书审核两个 Agent 的数据源从「写死 mock」切到「真读 MySQL + mock 兜底」：
  - fetch_reviews：从 coach_review 表取教练评价（无数据/AI_MOCK_DB 回退 mock）；
  - fetch_certificate：从 coach_certificate 表取最新证书（无则返回 None）。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.clients.db import afetch_all
from app.clients.llm import is_mock_db
from app.tools.registry import TOOL_REGISTRY, Tool

logger = logging.getLogger(__name__)

# 内置 mock 评价（离线兜底；coach_review 表有数据后自动切真读）
_MOCK_REVIEWS: list[str] = [
    "李教练很专业，减脂计划定制得很合理，效果明显",
    "动作纠正到位，服务态度很好，值得推荐",
    "按时上门，装备齐全，训练强度适中",
    "时间安排不太灵活，改期比较麻烦",
    "迟到过一次，等了 30 分钟",
    "性价比高，一对一指导很耐心",
]


async def fetch_reviews(coach_id: int, limit: int = 30) -> list[dict[str, Any]]:
    """取教练最近 N 条评价。返回 [{"content":.., "rating":..}]。无数据回退 mock。"""
    if is_mock_db():
        return [{"content": r, "rating": 5} for r in _MOCK_REVIEWS[:limit]]
    try:
        # 真实表名 = order_review；字段名 = coach_rating / create_time（对齐 sky-take-out SQL v0.2）。
        # limit 是 Pydantic 校验过的 int（1~200），直接内插无注入风险。
        rows = await afetch_all(
            "SELECT content, coach_rating AS rating FROM order_review "
            f"WHERE coach_id = :cid ORDER BY create_time DESC LIMIT {int(limit)}",
            {"cid": int(coach_id)},
        )
        if rows:
            return [
                {"content": r.get("content") or "", "rating": int(r.get("rating") or 5)}
                for r in rows
            ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("评价查询失败，回退 mock：%s", exc)
    return [{"content": r, "rating": 5} for r in _MOCK_REVIEWS[:limit]]


async def fetch_certificate(coach_id: int) -> Optional[dict[str, Any]]:
    """取教练最新一条待审核证书。无则返回 None。"""
    if is_mock_db():
        return None
    try:
        rows = await afetch_all(
            "SELECT cert_type, cert_number, holder_name, image_url FROM coach_certificate "
            "WHERE coach_id = :cid ORDER BY created_at DESC LIMIT 1",
            {"cid": int(coach_id)},
        )
        if rows:
            return rows[0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("证书查询失败：%s", exc)
    return None


# ---------------------------------------------------------------------------
# 注册工具
# ---------------------------------------------------------------------------
TOOL_REGISTRY.register(Tool(
    name="fetch_reviews",
    description="取教练最近 N 条评价，返回 [{content, rating}]",
    input_schema={
        "type": "object",
        "properties": {
            "coach_id": {"type": "integer"},
            "limit": {"type": "integer", "default": 30},
        },
        "required": ["coach_id"],
    },
    handler=fetch_reviews,
))
TOOL_REGISTRY.register(Tool(
    name="fetch_certificate",
    description="取教练最新一条待审核证书，返回 {cert_type, cert_number, holder_name, image_url} 或 null",
    input_schema={
        "type": "object",
        "properties": {"coach_id": {"type": "integer"}},
        "required": ["coach_id"],
    },
    handler=fetch_certificate,
))

__all__ = ["fetch_reviews", "fetch_certificate"]

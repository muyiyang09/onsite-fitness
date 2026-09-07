"""评价摘要 Agent（#08-A）的 Pydantic 契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewSummaryIn(BaseModel):
    """评价摘要请求：给某教练最近 N 条评价生成优缺点摘要。"""

    coach_id: int = Field(..., description="教练 ID")
    limit: int = Field(default=30, ge=1, le=200, description="取最近多少条评价")


class ReviewSummaryResult(BaseModel):
    """评价摘要输出：一段摘要 + 正负面标签 + 情感计数。"""

    coach_id: int = Field(description="教练 ID")
    summary: str = Field(description="2~3 句优缺点摘要")
    positive_tags: list[str] = Field(default_factory=list, description="高频正向标签")
    negative_tags: list[str] = Field(default_factory=list, description="高频负面标签")
    sentiment: dict[str, int] = Field(
        default_factory=dict, description="{positive/negative/neutral: 条数}"
    )
    used_mock: bool = Field(default=False, description="是否走了 mock（离线/无评价数据）")

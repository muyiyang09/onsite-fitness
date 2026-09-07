"""Loop 工程（Phase 1）单元测试：纯函数 + 图终止。

不依赖真实 LLM（AI_MOCK=1）；不依赖 MySQL（Node2 的 DB 查询失败自动回退 mock）。
运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_loop.py -q
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 让 pytest 之外也能直接跑：确保 ai-service 根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 强制 mock 模式（不依赖 API Key 也能跑通图）
os.environ.setdefault("AI_MOCK", "1")

from app.graphs.recommend_coach import (  # noqa: E402
    MAX_REFINE,
    RECOMMEND_GRAPH,
    _reason_quality_issue,
    relax_filters,
    retrieve_and_rank,
)
from app.schemas.coach_recommend import RecommendResult  # noqa: E402


# ---------------------------------------------------------------------------
# Node3 推荐理由质量门控
# ---------------------------------------------------------------------------
def test_reason_quality_empty():
    assert _reason_quality_issue("", [{"name": "李教练"}]) == "推荐理由为空"


def test_reason_quality_too_long():
    assert _reason_quality_issue("好" * 200, [{"name": "李教练"}]) is not None


def test_reason_quality_no_coach_name():
    assert _reason_quality_issue("这位教练很专业，快下单吧", [{"name": "李教练"}]) is not None


def test_reason_quality_ok():
    assert _reason_quality_issue("推荐李教练，评分4.9专注减脂", [{"name": "李教练"}]) is None


def test_reason_quality_ok_no_candidates():
    # 无候选时不要求点教练名（否则会陷入「永远不达标」）
    assert _reason_quality_issue("暂无合适教练", []) is None


# ---------------------------------------------------------------------------
# refine 放宽逻辑（确定性放宽硬过滤条件）
# ---------------------------------------------------------------------------
def _intent_with_hard_filters() -> dict:
    return {
        "city_name": "北京市",
        "district": "望京",
        "specialization": "产后恢复",
        "specialization_tags": ["产后恢复"],
        "level": 4,
        "min_rating": 4.9,
        "max_price": 200.0,
        "time_slot": "周末上午",
        "male_only": True,
        "user_goal": "产后恢复",
    }


def test_relax_first_round_clears_sex_and_rating():
    out = asyncio.run(relax_filters({"intent": _intent_with_hard_filters()}))
    assert out["refine_count"] == 1
    assert out["intent"]["male_only"] is None
    assert out["intent"]["min_rating"] is None
    assert out["intent"]["level"] == 4  # 还没放
    assert out["intent"]["city_name"] == "北京市"


def test_relax_second_round_clears_level():
    out = asyncio.run(relax_filters({"intent": _intent_with_hard_filters(), "refine_count": 1}))
    assert out["refine_count"] == 2
    assert out["intent"]["level"] is None
    assert out["intent"]["city_name"] == "北京市"


def test_relax_third_round_clears_city():
    out = asyncio.run(relax_filters({"intent": _intent_with_hard_filters(), "refine_count": 2}))
    assert out["refine_count"] == 3
    assert out["intent"]["city_name"] is None


# ---------------------------------------------------------------------------
# Node2 refine 路由
# ---------------------------------------------------------------------------
def test_retrieve_returns_refine_on_empty():
    # 城市无匹配教练 → 应触发 refine（而不是直接塞全量教练）
    out = asyncio.run(retrieve_and_rank({"intent": {"city_name": "不存在市"}, "top_n": 3}))
    assert out["route"] == "refine"
    assert out["candidates"] == []


def test_retrieve_fallback_after_exhaust():
    # 放宽耗尽（refine_count 到上限）→ 回退全量候选，正常走理由生成
    out = asyncio.run(
        retrieve_and_rank(
            {"intent": {"city_name": "不存在市"}, "top_n": 3, "refine_count": MAX_REFINE}
        )
    )
    assert out["route"] == "reason"
    assert out["candidates"]


# ---------------------------------------------------------------------------
# 图终止（mock 模式端到端）
# ---------------------------------------------------------------------------
def test_graph_runs_to_end_in_mock_mode():
    state_out = asyncio.run(
        RECOMMEND_GRAPH.ainvoke(
            {"user_query": "想找个教练上门上课", "top_n": 3},
            config={"configurable": {"thread_id": "loop-test"}},
        )
    )
    assert state_out["route"] == "done"
    assert state_out["used_mock"] is True
    result = RecommendResult.model_validate(state_out["result"])
    assert result.candidates
    assert result.coach_ids == [c.coach_id for c in result.candidates]


def test_graph_terminates_with_pre_exhausted_refine():
    # 预置 refine_count 到上限：验证有界循环不会因空结果无限循环
    state_out = asyncio.run(
        RECOMMEND_GRAPH.ainvoke(
            {"user_query": "想找个教练上门上课", "top_n": 3, "refine_count": MAX_REFINE},
            config={"configurable": {"thread_id": "loop-test-exhausted"}},
        )
    )
    assert state_out["route"] == "done"
    assert RecommendResult.model_validate(state_out["result"])

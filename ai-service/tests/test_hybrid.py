"""混合检索（#04 RAG 升级）单元测试：RRF 融合 + 相关度转换 + 降级路径。

不依赖真实 LLM / MySQL。BM25 依赖 MySQL 建索引，mock 模式下自动降级为子串匹配，
所以这里重点测「纯函数」和「降级路径」，端到端回归复用 test_loop.py。

运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_hybrid.py -q
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_MOCK", "1")

from app.clients.hybrid import _rank_to_relevance, _rrf_fuse, hybrid_match_scores  # noqa: E402
from app.config import settings  # noqa: E402


# ---------------------------------------------------------------------------
# RRF 融合（纯函数）
# ---------------------------------------------------------------------------
def test_rrf_fuse_rewards_multi_list_hit():
    """同一 coach 出现在多路召回时，RRF 分数累加、排名更靠前。"""
    fused = _rrf_fuse(
        [
            [(1, 10.0), (2, 9.0), (3, 8.0)],  # BM25 路
            [(2, 0.9)],  # 向量路：只命中 coach 2
        ],
        k=60,
        top_k=30,
    )
    ids = [cid for cid, _ in fused]
    assert ids[0] == 2  # 双路命中 → 第一
    assert ids[1] == 1  # 单路 rank1 → 第二
    assert ids[2] == 3  # 单路 rank3 → 第三


def test_rrf_fuse_top_k_cutoff():
    fused = _rrf_fuse([[(1, 1.0), (2, 0.9), (3, 0.8)]], k=60, top_k=2)
    assert [cid for cid, _ in fused] == [1, 2]


# ---------------------------------------------------------------------------
# 排名 → 相关度
# ---------------------------------------------------------------------------
def test_rank_to_relevance_monotonic_decay():
    rel = _rank_to_relevance([2, 1, 3])
    assert rel[2] == pytest.approx(1.0)
    assert rel[1] == pytest.approx(2 / 3)
    assert rel[3] == pytest.approx(1 / 3)
    assert rel[2] > rel[1] > rel[3]


def test_rank_to_relevance_empty():
    assert _rank_to_relevance([]) == {}


# ---------------------------------------------------------------------------
# 降级路径（mock 模式无 MySQL → BM25 空 → 退回子串匹配）
# ---------------------------------------------------------------------------
def test_hybrid_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "hybrid_retrieval_enabled", False)
    assert (
        hybrid_match_scores(
            "减脂", [{"coach_id": 1, "name": "李", "bio": "减脂", "city_name": "北京"}]
        )
        == {}
    )


def test_hybrid_empty_query_returns_empty():
    assert hybrid_match_scores("  ", [{"coach_id": 1}]) == {}


def test_hybrid_graceful_when_no_index():
    """mock 模式下 MySQL 不可用，BM25 索引为空，应返回 {} 而非抛异常。"""
    result = hybrid_match_scores(
        "减脂塑形",
        [
            {"coach_id": 1, "name": "李教练", "bio": "专注减脂", "city_name": "北京市"},
            {"coach_id": 2, "name": "王教练", "bio": "擅长增肌", "city_name": "北京市"},
        ],
    )
    assert result == {}

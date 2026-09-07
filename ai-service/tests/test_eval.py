"""Eval 指标 + Prompt 加载单元测试（#06 Harness 工程）。

纯函数，离线可跑，不依赖 LLM/DB。

运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_eval.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.metrics import (  # noqa: E402
    intent_field_accuracy,
    reason_quality_score,
    topk_hit_ratio,
)
from app.prompts.loader import load_prompt  # noqa: E402


# ---------------------------------------------------------------------------
# Prompt 加载
# ---------------------------------------------------------------------------
def test_load_prompt_returns_template():
    assert "意图抽取" in load_prompt("recommend_node1_intent")
    assert "健身顾问" in load_prompt("recommend_node3_reason")


def test_load_prompt_missing_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_prompt")


# ---------------------------------------------------------------------------
# Intent 字段准确率
# ---------------------------------------------------------------------------
def test_intent_field_accuracy_full_match():
    pred = {"city_name": "北京市", "specialization": "减脂塑形", "level": 4}
    exp = {"city_name": "北京市", "specialization": "减脂塑形", "level": 4}
    assert intent_field_accuracy(pred, exp) == 1.0


def test_intent_field_accuracy_skips_none_expected():
    # expected 为 None 的字段不参与打分
    pred = {"city_name": "北京市", "specialization": "减脂塑形"}
    exp = {"city_name": "北京市", "level": None}
    assert intent_field_accuracy(pred, exp) == 1.0


def test_intent_field_accuracy_partial():
    pred = {"city_name": "北京市", "specialization": "减脂塑形"}
    exp = {"city_name": "北京市", "specialization": "增肌训练"}
    assert intent_field_accuracy(pred, exp) == 0.5


def test_intent_time_slot_fuzzy():
    # 时段用模糊包含："周末" 命中 "周末上午"
    pred = {"time_slot": "周末上午"}
    exp = {"time_slot": "周末"}
    assert intent_field_accuracy(pred, exp) == 1.0


# ---------------------------------------------------------------------------
# Top-K 命中率
# ---------------------------------------------------------------------------
def test_topk_hit_ratio_hit():
    assert topk_hit_ratio([1, 3, 2], [3]) == 1.0


def test_topk_hit_ratio_miss():
    assert topk_hit_ratio([1, 3, 2], [5]) == 0.0


def test_topk_hit_ratio_empty_subset():
    assert topk_hit_ratio([1, 2, 3], []) == 1.0


# ---------------------------------------------------------------------------
# 推荐理由质量分
# ---------------------------------------------------------------------------
def test_reason_quality_good_reason_scores_high():
    candidates = [{"name": "李教练", "rating": 4.9, "price": 199}]
    reason = "针对减脂目标，推荐李教练，评分4.9专注减脂8年，参考课199元"
    score = reason_quality_score(reason, candidates)["score"]
    assert score >= 80


def test_reason_quality_empty_reason_scores_low():
    score = reason_quality_score("", [{"name": "李教练"}])["score"]
    assert score < 60

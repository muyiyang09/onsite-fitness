"""指标 + 评价工具测试（可观测性 + 数据侧落地）。

运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_metrics.py -q
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_MOCK", "1")
os.environ.setdefault("AI_MOCK_DB", "1")

from app.core import metrics  # noqa: E402
from app.tools.review_cert_tools import fetch_reviews  # noqa: E402


def test_metrics_incr_and_render():
    metrics.incr("test_counter", 3)
    assert "test_counter 3" in metrics.render()


def test_metrics_observe_latency():
    metrics.observe("test_latency", 100.5)
    out = metrics.render()
    assert "test_latency_count 1" in out
    assert "test_latency_sum 100.50" in out


def test_fetch_reviews_mock_fallback():
    reviews = asyncio.run(fetch_reviews(1, limit=10))
    assert len(reviews) == 6  # mock 库 6 条
    assert "content" in reviews[0] and "rating" in reviews[0]

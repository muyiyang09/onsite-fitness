"""多 Agent 测试（#08）：评价摘要 + 证书审核 + Supervisor 路由。

运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_agents.py -q
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

from app.graphs.cert_review import CERT_REVIEW_GRAPH  # noqa: E402
from app.graphs.review_summary import REVIEW_SUMMARY_GRAPH  # noqa: E402
from app.graphs.supervisor import route_query  # noqa: E402
from app.schemas.cert_review import CertReviewResult  # noqa: E402
from app.schemas.review_summary import ReviewSummaryResult  # noqa: E402


def test_review_summary_graph_runs():
    state_out = asyncio.run(
        REVIEW_SUMMARY_GRAPH.ainvoke(
            {"coach_id": 1, "limit": 10},
            config={"configurable": {"thread_id": "review-test"}},
        )
    )
    result = ReviewSummaryResult.model_validate(state_out["result"])
    assert result.coach_id == 1
    assert result.summary
    assert result.sentiment.get("positive", 0) + result.sentiment.get("negative", 0) >= 1


def test_cert_review_good_cert_approves():
    state_out = asyncio.run(
        CERT_REVIEW_GRAPH.ainvoke(
            {
                "coach_id": 1,
                "cert_type": "国职",
                "cert_number": "GZ20240001",
                "holder_name": "李教练",
            },
            config={"configurable": {"thread_id": "cert-good"}},
        )
    )
    result = CertReviewResult.model_validate(state_out["result"])
    assert result.risk_level == "low"
    assert result.suggestion == "approve"


def test_cert_review_bad_number_rejects():
    state_out = asyncio.run(
        CERT_REVIEW_GRAPH.ainvoke(
            {
                "coach_id": 1,
                "cert_type": "国职",
                "cert_number": "bad-number",
                "holder_name": "李教练",
            },
            config={"configurable": {"thread_id": "cert-bad"}},
        )
    )
    result = CertReviewResult.model_validate(state_out["result"])
    assert result.risk_level == "high"
    assert result.suggestion == "reject"


def test_supervisor_routing_mock():
    assert asyncio.run(route_query("这家教练评价怎么样")) == "review_summary"
    assert asyncio.run(route_query("帮我审核教练证书资质")) == "cert_review"
    assert asyncio.run(route_query("想找教练上门减脂")) == "recommend_coach"


def test_audit_four_actions_insert(monkeypatch):
    """§6.20 四端点审计：四种 action 各至少写一条 INSERT（spawn_audit 强引用不丢任务）。"""
    import app.core.audit as audit_module

    inserts: list[dict] = []

    async def fake_aexecute(sql, params=None, **kw):
        inserts.append(params or {})
        return None

    monkeypatch.setattr(audit_module, "aexecute", fake_aexecute)

    async def run():
        for action in ("cert_review", "cert_review_resume", "review_summary", "chat_supervisor"):
            audit_module.spawn_audit(user_id="u", request_id="r", action=action)
        # 排空后台任务
        while audit_module._bg_tasks:
            await asyncio.sleep(0)
        return inserts

    inserts = asyncio.run(run())
    assert len(inserts) >= 4
    actions = {p["action"] for p in inserts}
    assert {"cert_review", "cert_review_resume", "review_summary", "chat_supervisor"} <= actions

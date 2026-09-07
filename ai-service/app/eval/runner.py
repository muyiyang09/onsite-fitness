"""Eval 运行器（#06 Harness 工程）：跑标注数据集 → 算 3 类指标 → 出报告。

用法：
    cd ai-service
    set AI_MOCK=1                                    # 离线冒烟（推荐，0 成本）
    python -m app.eval.runner                        # 跑 mock 模式

    去掉 AI_MOCK 则走真实 LLM（真实评估，会花钱，建议小批量）

基线（baseline）思维：Eval 不是「断言全过」，而是记一个分数，改 prompt/模型后对比——
分数涨了 = 改对了。通过阈值：intent_acc≥0.6 且 topk_hit≥1.0 且 reason_score≥60。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from app.eval.metrics import intent_field_accuracy, reason_quality_score, topk_hit_ratio
from app.graphs.recommend_coach import RECOMMEND_GRAPH
from app.schemas.coach_recommend import RecommendResult

console = Console()

# 通过阈值（#06 §5.1）
_INTENT_MIN = 0.6
_REASON_MIN = 60


async def run_eval(dataset_path: str) -> dict:
    cases = yaml.safe_load(Path(dataset_path).read_text(encoding="utf-8"))
    results: list[dict] = []
    for case in cases:
        try:
            state_out = await RECOMMEND_GRAPH.ainvoke(
                {"user_query": case["query"], "top_n": 3},
                config={"configurable": {"thread_id": f"eval-{case['id']}"}},
            )
            result = RecommendResult.model_validate(state_out["result"])
        except Exception as exc:  # noqa: BLE001
            results.append(
                {"id": case["id"], "name": case["name"], "error": str(exc), "pass": False}
            )
            continue

        intent_acc = intent_field_accuracy(
            result.intent.model_dump(), case.get("expected_intent", {})
        )
        hit = topk_hit_ratio(result.coach_ids, case.get("expected_coach_ids_subset", []))
        rq = reason_quality_score(
            result.recommend_reason, [c.model_dump() for c in result.candidates]
        )
        passed = intent_acc >= _INTENT_MIN and hit >= 1.0 and rq["score"] >= _REASON_MIN
        results.append(
            {
                "id": case["id"],
                "name": case["name"],
                "intent_acc": intent_acc,
                "topk_hit": hit,
                "reason_score": rq["score"],
                "pass": passed,
            }
        )

    total = len(results)
    passed = sum(1 for r in results if r.get("pass"))
    avg_intent = sum(r.get("intent_acc", 0) for r in results) / total if total else 0.0
    avg_reason = sum(r.get("reason_score", 0) for r in results) / total if total else 0.0
    return {
        "passed": passed,
        "total": total,
        "pass_rate": passed / total if total else 0.0,
        "avg_intent_acc": avg_intent,
        "avg_reason_score": avg_reason,
        "details": results,
    }


def print_report(report: dict) -> None:
    tbl = Table("ID", "Name", "Intent", "TopK", "Reason", "Pass", title="教练推荐 Eval 报告")
    for r in report["details"]:
        tbl.add_row(
            str(r.get("id", "-")),
            r.get("name", "-"),
            f"{r.get('intent_acc', 0):.2f}",
            f"{r.get('topk_hit', 0):.0f}",
            f"{r.get('reason_score', 0):.0f}",
            "✓" if r.get("pass") else "✗",
        )
    console.print(tbl)
    console.print(
        f"\n[bold]通过率：{report['passed']}/{report['total']} "
        f"({report['pass_rate']:.0%})[/]  "
        f"平均 Intent 准确率 {report['avg_intent_acc']:.2f}  "
        f"平均理由质量分 {report['avg_reason_score']:.0f}"
    )


def main(dataset_path: str = "tests/eval/dataset.yaml") -> int:
    # 默认完全离线（mock LLM + mock DB），确定性、0 成本；要真实评估就显式 AI_MOCK=0 AI_MOCK_DB=0
    os.environ.setdefault("AI_MOCK", "1")
    os.environ.setdefault("AI_MOCK_DB", "1")
    # Windows GBK 控制台输出中文会炸，强制 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report = asyncio.run(run_eval(dataset_path))
    print_report(report)
    # 通过率 < 阈值返回非 0，便于 CI 集成
    return 0 if report["pass_rate"] >= 0.8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
